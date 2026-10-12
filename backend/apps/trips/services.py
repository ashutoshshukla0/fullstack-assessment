"""Trip planning: geocode, route, sample checkpoints, score weather risk, rank."""

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TypedDict

from apps.risk.classifier import CheckpointWeather, WeatherRiskClassifier
from apps.risk.levels import RiskLevel
from apps.risk.recommendation import RouteRecommender, RouteScore
from apps.routing.interfaces import IGeocoder, IRoutingProvider, LatLon, RouteGeometry
from apps.routing.sampling import Checkpoint, sample_checkpoints
from apps.weather.interfaces import HourlyWeather, IWeatherProvider

logger = logging.getLogger(__name__)

METERS_PER_MILE = 1609.344
COORD_PRECISION = 5
CORRIDOR_HOURS = 48
MAX_COORD_POINTS = 500
WEATHER_WORKERS = 8


class CheckpointOut(TypedDict):
    index: int
    lat: float
    lon: float
    miles_from_origin: float
    eta: str
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float
    precip_prob_pct: int
    risks: dict[str, str]
    risk: str
    risk_value: int
    weather_degraded: bool


class RouteSummaryOut(TypedDict):
    total_miles: float
    duration_s: int
    avg_risk: float
    miles_by_risk: dict[str, float]


class RouteOut(TypedDict):
    id: str
    label: str
    rank: int
    recommended: bool
    blocked: bool
    origin: dict[str, float]
    destination: dict[str, float]
    coordinates: list[list[float]]
    summary: RouteSummaryOut
    checkpoints: list[CheckpointOut]
    corridor_forecast: list[dict]
    corridor_degraded: bool


@dataclass
class TripRequest:
    origin: str
    destination: str
    departure: datetime
    load_lbs: float
    interval_miles: float | None = None


@dataclass
class TripPlan:
    routes: list[dict] = field(default_factory=list)
    recommended_route_id: str | None = None
    blocked: bool = False


def simplify_coordinates(
    coordinates: list[tuple[float, float]], max_points: int = MAX_COORD_POINTS
) -> list[tuple[float, float]]:
    """Evenly decimate geometry for the API payload (keeps endpoints)."""
    if len(coordinates) <= max_points or max_points < 2:
        return list(coordinates)
    n = len(coordinates)
    idx = sorted({0, n - 1} | {round(i * (n - 1) / (max_points - 1)) for i in range(max_points)})
    return [coordinates[i] for i in idx]


class TripService:
    """Orchestrates geocoding, routing, weather scoring and ranking.

    Dependencies are injected as interfaces so tests can substitute fakes;
    the classifier/recommender default to the production pure functions.
    """

    def __init__(
        self,
        geocoder: IGeocoder,
        routing: IRoutingProvider,
        weather: IWeatherProvider,
        classifier: WeatherRiskClassifier | None = None,
        recommender: RouteRecommender | None = None,
    ):
        self.geocoder = geocoder
        self.routing = routing
        self.weather = weather
        self.classifier = classifier or WeatherRiskClassifier()
        self.recommender = recommender or RouteRecommender()

    @staticmethod
    def _miles(meters: float) -> float:
        return meters / METERS_PER_MILE

    @staticmethod
    def _normalize_departure(departure: datetime) -> datetime:
        if departure.tzinfo is None:
            logger.warning("Naive departure assumed UTC; prefer tz-aware ISO input.")
            return departure.replace(tzinfo=timezone.utc)
        return departure

    @staticmethod
    def _clean_place(value: str | None, field_name: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError(f"{field_name} must not be blank")
        return cleaned

    def _score_checkpoint(
        self, lat: float, lon: float, eta: datetime, load_lbs: float
    ) -> tuple[HourlyWeather, dict, RiskLevel, bool]:
        """Score one checkpoint; degrade (never abort) on weather failure."""
        try:
            w = self.weather.get_at(lat, lon, eta)
        except Exception:
            logger.warning(
                "Weather unavailable at (%s,%s); degrading checkpoint.", lat, lon, exc_info=True
            )
            w = HourlyWeather(
                time=eta, wind_mph=0.0, rain_in_hr=0.0, snow_in_hr=0.0, precip_prob_pct=0.0
            )
            res = self.classifier.classify_checkpoint(CheckpointWeather(0.0, 0.0, 0.0), load_lbs)
            return w, res, res["overall"], True
        res = self.classifier.classify_checkpoint(
            CheckpointWeather(w.wind_mph, w.rain_in_hr, w.snow_in_hr), load_lbs
        )
        return w, res, res["overall"], False

    def _corridor_for(self, cp: Checkpoint, load_lbs: float) -> tuple[dict, bool]:
        try:
            hourly = self.weather.get_hourly_range(cp.lat, cp.lon, cp.eta, CORRIDOR_HOURS)
        except Exception:
            logger.warning(
                "Corridor forecast unavailable for checkpoint %s; degrading to empty.",
                cp.index,
                exc_info=True,
            )
            return {"checkpoint_index": cp.index, "hourly": []}, True
        return {
            "checkpoint_index": cp.index,
            "hourly": [
                {
                    "hour_offset": hi,
                    "time": h.time.isoformat(),
                    "wind_mph": round(h.wind_mph, 1),
                    "rain_in_hr": round(h.rain_in_hr, 3),
                    "snow_in_hr": round(h.snow_in_hr, 3),
                    "precip_prob_pct": round(h.precip_prob_pct),
                    "risk": self.classifier.classify_checkpoint(
                        CheckpointWeather(h.wind_mph, h.rain_in_hr, h.snow_in_hr),
                        load_lbs,
                    )["overall"].label,
                }
                for hi, h in enumerate(hourly)
            ],
        }, False

    def _plan_single_route(
        self,
        route_id: str,
        label: str,
        geometry: RouteGeometry,
        origin_ll: LatLon,
        dest_ll: LatLon,
        departure: datetime,
        load_lbs: float,
        interval_miles: float | None,
    ) -> tuple[dict, RouteScore]:
        total_miles = self._miles(geometry.distance_m)
        checkpoints = sample_checkpoints(
            geometry.coordinates,
            geometry.distance_m,
            geometry.duration_s,
            departure,
            interval_miles,
        )
        # Parallel weather reads: get_at + corridor share the provider cache.
        with ThreadPoolExecutor(max_workers=WEATHER_WORKERS) as pool:
            scored = list(
                pool.map(
                    lambda cp: self._score_checkpoint(cp.lat, cp.lon, cp.eta, load_lbs), checkpoints
                )
            )
            corridors = list(pool.map(lambda cp: self._corridor_for(cp, load_lbs), checkpoints))

        cp_out: list[dict] = []
        corridor: list[dict] = []
        corridor_degraded = False
        counts = {lvl: 0.0 for lvl in RiskLevel}
        weighted_sum = 0.0
        weighted_miles = 0.0
        prev_miles = 0.0
        for cp, (w, res, overall, degraded), (corr, corr_bad) in zip(
            checkpoints, scored, corridors, strict=True
        ):
            seg_miles = max(0.0, cp.miles_from_origin - prev_miles)
            prev_miles = cp.miles_from_origin
            counts[overall] += seg_miles
            weighted_sum += overall.value * seg_miles
            weighted_miles += seg_miles
            corridor_degraded = corridor_degraded or corr_bad
            cp_out.append(
                {
                    "index": cp.index,
                    "lat": round(cp.lat, COORD_PRECISION),
                    "lon": round(cp.lon, COORD_PRECISION),
                    "miles_from_origin": round(cp.miles_from_origin, 2),
                    "eta": cp.eta.isoformat(),
                    "wind_mph": round(w.wind_mph, 1),
                    "rain_in_hr": round(w.rain_in_hr, 3),
                    "snow_in_hr": round(w.snow_in_hr, 3),
                    "precip_prob_pct": round(w.precip_prob_pct),
                    "risks": {k: v.label for k, v in res.items()},
                    "risk": overall.label,
                    "risk_value": overall.value,
                    "weather_degraded": degraded,
                }
            )
            corridor.append(corr)
        # Mileage-weighted mean: a short final segment must not count the
        # same as a full interval (miles_by_risk is already weighted).
        avg_risk = weighted_sum / weighted_miles if weighted_miles > 0 else 0.0
        counts_label = {lvl.label: round(m, 1) for lvl, m in counts.items()}
        blocked = counts.get(RiskLevel.NO_TRAVEL, 0.0) > 0
        route = {
            "id": route_id,
            "label": label,
            "origin": {"lat": origin_ll.lat, "lon": origin_ll.lon},
            "destination": {"lat": dest_ll.lat, "lon": dest_ll.lon},
            "coordinates": [[lon, lat] for lon, lat in simplify_coordinates(geometry.coordinates)],
            "summary": {
                "total_miles": round(total_miles, 1),
                "duration_s": round(geometry.duration_s),
                "avg_risk": round(avg_risk, 2),
                "miles_by_risk": counts_label,
            },
            "checkpoints": cp_out,
            "corridor_forecast": corridor,
            "corridor_degraded": corridor_degraded,
            "blocked": blocked,
        }
        score = RouteScore(
            route_id=route_id,
            no_travel_miles=round(counts.get(RiskLevel.NO_TRAVEL, 0.0), 1),
            severe_miles=round(counts.get(RiskLevel.SEVERE, 0.0), 1),
            high_miles=round(counts.get(RiskLevel.HIGH, 0.0), 1),
            avg_risk=round(avg_risk, 2),
            duration_s=geometry.duration_s,
        )
        return route, score

    def plan(self, req: TripRequest) -> TripPlan:
        """Plan and rank routes best-first. Raises ValueError on bad input."""
        departure = self._normalize_departure(req.departure)
        origin_q = self._clean_place(req.origin, "Origin")
        dest_q = self._clean_place(req.destination, "Destination")

        origin_ll = self.geocoder.geocode(origin_q)
        dest_ll = self.geocoder.geocode(dest_q)
        geometries = self.routing.get_routes(origin_ll, dest_ll)
        if not geometries:
            raise ValueError("No routes found")

        routes: list[dict] = []
        scores: list[RouteScore] = []
        for i, g in enumerate(geometries):
            route_id = f"route-{i + 1}"
            route, score = self._plan_single_route(
                route_id,
                f"Route {i + 1}",
                g,
                origin_ll,
                dest_ll,
                departure,
                req.load_lbs,
                req.interval_miles,
            )
            routes.append(route)
            scores.append(score)

        recommended = self.recommender.recommend(scores)
        order = {s.route_id: n for n, s in enumerate(self.recommender.rank(scores))}
        routes.sort(key=lambda r: order[r["id"]])
        blocked_all = recommended is None and len(scores) > 0
        for n, r in enumerate(routes):
            r["rank"] = n + 1
            r["recommended"] = r["id"] == recommended
        logger.info("Planned %d route(s); recommended=%s", len(routes), recommended)
        return TripPlan(routes=routes, recommended_route_id=recommended, blocked=blocked_all)
