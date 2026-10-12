"""Corridor forecast passthrough (used by heatmap slider independently if needed)."""

import logging
from datetime import datetime, timezone

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.risk.classifier import CheckpointWeather, WeatherRiskClassifier
from apps.weather.providers import OpenMeteoProvider

logger = logging.getLogger(__name__)

DEFAULT_HOURS = 48
MAX_HOURS = 72
MAX_LOAD_LBS = 200_000

_classifier = WeatherRiskClassifier()
_weather = OpenMeteoProvider()


class CorridorForecastView(APIView):
    @extend_schema(
        tags=["forecast"],
        summary="Hourly risk series for one point",
        parameters=[
            OpenApiParameter(name="lat", required=True, type=float),
            OpenApiParameter(name="lon", required=True, type=float),
            OpenApiParameter(
                name="hours",
                required=False,
                type=int,
                description="Hours ahead, ≤72 (default 48).",
            ),
            OpenApiParameter(
                name="load_lbs",
                required=False,
                type=float,
                description="Load weight for wind-load rules.",
            ),
        ],
        responses={
            200: {
                "description": "{lat, lon, hourly: [{hour_offset, time, wind_mph, rain_in_hr, snow_in_hr, precip_prob_pct, risk}]}"
            }
        },
    )
    def get(self, request: Request) -> Response:
        try:
            lat = float(request.query_params["lat"])
            lon = float(request.query_params["lon"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("lat/lon out of range")
            raw_hours = request.query_params.get("hours", DEFAULT_HOURS)
            hours = int(float(raw_hours))
            if hours < 0 or hours > MAX_HOURS:
                raise ValueError("hours must be 0..72")
            load_lbs = float(request.query_params.get("load_lbs", 0))
            if load_lbs < 0 or load_lbs > MAX_LOAD_LBS:
                raise ValueError("load_lbs out of range")
        except (KeyError, TypeError, ValueError):
            return Response(
                {
                    "detail": "Provide lat (-90..90), lon (-180..180), optional hours 0..72, load_lbs 0..200000"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            start = datetime.now(timezone.utc)
            hourlies = _weather.get_hourly_range(lat, lon, start, hours)
        except Exception:
            logger.warning("Corridor forecast fetch failed", exc_info=True)
            return Response(
                {"detail": "Weather provider error; please retry shortly."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        out = []
        for i, h in enumerate(hourlies):
            risk = _classifier.classify_checkpoint(
                CheckpointWeather(h.wind_mph, h.rain_in_hr, h.snow_in_hr), load_lbs
            )["overall"]
            out.append(
                {
                    "hour_offset": i,
                    "time": h.time.isoformat(),
                    "wind_mph": round(h.wind_mph, 1),
                    "rain_in_hr": round(h.rain_in_hr, 3),
                    "snow_in_hr": round(h.snow_in_hr, 3),
                    "precip_prob_pct": round(h.precip_prob_pct),
                    "risk": risk.label,
                }
            )
        return Response({"lat": lat, "lon": lon, "hourly": out})
