"""Nominatim geocoder and OSRM routing provider."""

import logging
import math

import requests
from django.conf import settings

from .interfaces import (
    IGeocoder,
    ILocationSuggester,
    IRoutingProvider,
    LatLon,
    RouteGeometry,
    Suggestion,
)
from .sampling import haversine_miles

logger = logging.getLogger(__name__)

GEOCODE_TIMEOUT_S = 15
ROUTE_TIMEOUT_S = 20
MIN_ROUTES = 3
MAX_ROUTES = 3
MAX_SUGGESTIONS = 10

# Via-point detour generation (used when OSRM returns < 3 alternates).
VIA_FRACTIONS = (1 / 3, 2 / 3)
VIA_SIDES = (1.0, -1.0)
VIA_OFFSET_RATIO = 0.08
VIA_OFFSET_MIN_MI = 3.0
VIA_OFFSET_MAX_MI = 25.0
MAX_VIA_REQUESTS = 4
DUP_TOL_MI = 1.0
DUP_OVERLAP_RATIO = 0.8
DUP_SAMPLE_POINTS = 40
DUP_EXISTING_CAP = 500
MI_PER_DEG_LAT = 69.0


class UpstreamError(Exception):
    """Upstream provider failure (OSRM/Nominatim/Open-Meteo). Maps to HTTP 502."""


def _subsample(
    coordinates: list[tuple[float, float]], max_points: int
) -> list[tuple[float, float]]:
    """Evenly thin a polyline to at most `max_points` points (keeps endpoints)."""
    if len(coordinates) <= max_points or max_points <= 0:
        return list(coordinates)
    if max_points == 1:
        return [coordinates[0]]
    # Linspace inclusive of tail so the destination is always represented.
    n = len(coordinates)
    return [
        coordinates[min(n - 1, round(i * (n - 1) / (max_points - 1)))] for i in range(max_points)
    ]


class NominatimGeocoder(IGeocoder, ILocationSuggester):
    def __init__(
        self,
        base_url: str | None = None,
        user_agent: str | None = None,
        session: requests.Session | None = None,
    ):
        self.base_url = (base_url or settings.NOMINATIM_BASE_URL).rstrip("/")
        self.user_agent = user_agent or settings.NOMINATIM_USER_AGENT
        self.session = session or requests.Session()

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent}

    def geocode(self, query: str) -> LatLon:
        """Resolve an address to coordinates. Raises ValueError if unresolvable."""
        resp = self.session.get(
            f"{self.base_url}/search",
            params={"q": query, "format": "json", "limit": 1},
            headers=self._headers(),
            timeout=GEOCODE_TIMEOUT_S,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            raise ValueError(f"Could not geocode address: {query!r}")
        try:
            return LatLon(lat=float(data[0]["lat"]), lon=float(data[0]["lon"]))
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"Could not geocode address: {query!r}") from exc

    def suggest(self, query: str, limit: int = 5) -> list[Suggestion]:
        """Up to ``limit`` location matches for a partial query."""
        limit = max(1, min(limit, MAX_SUGGESTIONS))
        resp = self.session.get(
            f"{self.base_url}/search",
            params={
                "q": query,
                "format": "json",
                "addressdetails": 1,
                "limit": limit,
            },
            headers=self._headers(),
            timeout=GEOCODE_TIMEOUT_S,
        )
        resp.raise_for_status()
        out = []
        for item in resp.json():
            try:
                out.append(
                    Suggestion(
                        display_name=str(item["display_name"]),
                        lat=float(item["lat"]),
                        lon=float(item["lon"]),
                    )
                )
            except (KeyError, ValueError, TypeError):
                logger.debug("Skipping malformed Nominatim entry", exc_info=True)
                continue
        return out


class OSRMProvider(IRoutingProvider):
    """Free public OSRM demo server. Requests 3 alternatives; returns whatever is available."""

    USER_AGENT = "weather-truck-routing/1.0"

    def __init__(self, base_url: str | None = None, session: requests.Session | None = None):
        self.base_url = (base_url or settings.OSRM_BASE_URL).rstrip("/")
        self.session = session or requests.Session()

    @staticmethod
    def _validate_latlon(p: LatLon, name: str) -> None:
        if not (-90 <= p.lat <= 90 and -180 <= p.lon <= 180):
            raise ValueError(f"{name} out of range: lat={p.lat}, lon={p.lon}")

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.USER_AGENT}

    def get_routes(self, origin: LatLon, destination: LatLon) -> list[RouteGeometry]:
        """Return at least 3 routes whenever the road network allows it.

        OSRM `alternatives=3` only emits genuinely distinct alternates (often
        just 1). When it falls short, detour variants are built by routing
        origin → offset via-point → destination on real roads until 3
        distinct routes are collected.
        """
        routes = self._alternatives(origin, destination)
        if len(routes) >= MIN_ROUTES:
            return routes[:MAX_ROUTES]
        base_coords = routes[0].coordinates if routes else None
        extras = 0
        for via in self._via_candidates(base_coords or []):
            if len(routes) >= MIN_ROUTES or extras >= MAX_VIA_REQUESTS:
                break
            extras += 1
            try:
                cand = self._via_route(origin, via, destination)
            except Exception as exc:  # detour is best-effort; never fail the trip
                logger.debug("Via-point route failed, skipping: %s", exc)
                continue
            if self._is_duplicate(cand.coordinates, [r.coordinates for r in routes]):
                continue
            routes.append(cand)
        if len(routes) < MIN_ROUTES:
            logger.warning(
                "Only %d distinct route(s) found; road network allows no more.",
                len(routes),
            )
        return routes[:MAX_ROUTES]

    def _alternatives(self, origin: LatLon, destination: LatLon) -> list[RouteGeometry]:
        self._validate_latlon(origin, "Origin")
        self._validate_latlon(destination, "Destination")
        coords = f"{origin.lon},{origin.lat};{destination.lon},{destination.lat}"
        resp = self.session.get(
            f"{self.base_url}/route/v1/driving/{coords}",
            params={
                "alternatives": "3",
                "overview": "full",
                "geometries": "geojson",
                "continue_straight": "false",
            },
            headers=self._headers(),
            timeout=ROUTE_TIMEOUT_S,
        )
        resp.raise_for_status()
        return self._parse_routes(resp.json())

    def _via_route(
        self, origin: LatLon, via: tuple[float, float], destination: LatLon
    ) -> RouteGeometry:
        if not (-90 <= via[1] <= 90 and -180 <= via[0] <= 180):
            raise ValueError(f"Via-point out of range: {via!r}")
        coords = f"{origin.lon},{origin.lat};{via[0]},{via[1]};{destination.lon},{destination.lat}"
        resp = self.session.get(
            f"{self.base_url}/route/v1/driving/{coords}",
            params={"overview": "full", "geometries": "geojson"},
            headers=self._headers(),
            timeout=ROUTE_TIMEOUT_S,
        )
        resp.raise_for_status()
        parsed = self._parse_routes(resp.json())
        if not parsed:
            raise UpstreamError("Via-point routing returned no routes")
        return parsed[0]

    def _parse_routes(self, payload: dict) -> list[RouteGeometry]:
        if payload.get("code") != "Ok" or not payload.get("routes"):
            raise UpstreamError(f"Routing failed: {payload.get('message', payload.get('code'))}")
        out = []
        for r in payload["routes"][:MAX_ROUTES]:
            try:
                raw = r["geometry"]["coordinates"]
                coords_list = [(float(c[0]), float(c[1])) for c in raw]
                dist = float(r["distance"])
                dur = float(r["duration"])
            except (KeyError, ValueError, TypeError, IndexError) as exc:
                raise UpstreamError("Routing failed: malformed route geometry") from exc
            out.append(
                RouteGeometry(
                    coordinates=coords_list,
                    distance_m=dist,
                    duration_s=dur,
                )
            )
        return out

    @staticmethod
    def _via_candidates(
        coordinates: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        """Offset points perpendicular to the base route for detour routing."""
        if len(coordinates) < 2:
            return []
        cum = [0.0]
        for i in range(1, len(coordinates)):
            cum.append(cum[-1] + haversine_miles(coordinates[i - 1], coordinates[i]))
        total = cum[-1]
        if total <= 0:
            return []
        offset_mi = min(max(total * VIA_OFFSET_RATIO, VIA_OFFSET_MIN_MI), VIA_OFFSET_MAX_MI)
        cands = []
        for frac in VIA_FRACTIONS:
            target = frac * total
            seg = next((i for i in range(len(cum) - 1) if cum[i + 1] >= target), len(cum) - 2)
            (lon0, lat0), (lon1, lat1) = coordinates[seg], coordinates[seg + 1]
            # Interpolate along the segment to the exact target distance
            # (previously anchored to the segment start, off by a full segment
            # on long straightaways), then offset perpendicular to the road.
            c0, c1 = cum[seg], cum[seg + 1]
            frac_seg = 0.0 if c1 == c0 else (target - c0) / (c1 - c0)
            frac_seg = max(0.0, min(1.0, frac_seg))
            base_lon = lon0 + frac_seg * (lon1 - lon0)
            base_lat = lat0 + frac_seg * (lat1 - lat0)
            dx = (lon1 - lon0) * math.cos(math.radians(lat0))
            dy = lat1 - lat0
            norm = math.hypot(dx, dy)
            if norm == 0:
                continue
            px, py = -dy / norm, dx / norm
            cos_lat = max(math.cos(math.radians(base_lat)), 0.2)
            for side in VIA_SIDES:
                cands.append(
                    (
                        base_lon + side * px * offset_mi / (MI_PER_DEG_LAT * cos_lat),
                        base_lat + side * py * offset_mi / MI_PER_DEG_LAT,
                    )
                )
        return cands

    @staticmethod
    def _is_duplicate(
        candidate: list[tuple[float, float]],
        existing: list[list[tuple[float, float]]],
    ) -> bool:
        """True when the candidate overlaps an existing route's corridor."""
        samples = _subsample(candidate, DUP_SAMPLE_POINTS)
        if not samples:
            return True
        needed = math.ceil(len(samples) * DUP_OVERLAP_RATIO)
        for ex in existing:
            ex_pts = _subsample(ex, DUP_EXISTING_CAP)
            if not ex_pts:
                continue
            # Early exit: stop counting once the outcome is decided, and skip
            # distant points with a cheap lat/lon box pre-check.
            near = 0
            remaining = len(samples)
            for s in samples:
                remaining -= 1
                close = any(
                    abs(s[0] - e[0]) * MI_PER_DEG_LAT < DUP_TOL_MI + 1
                    and haversine_miles(s, e) <= DUP_TOL_MI
                    for e in ex_pts
                )
                if close:
                    near += 1
                    if near >= needed:
                        return True
                if near + remaining < needed:
                    break
        return False
