"""Trip planning endpoints."""

import logging

import requests
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.routing.providers import (
    NominatimGeocoder,
    OSRMProvider,
)
from apps.routing.providers import (
    UpstreamError as RoutingUpstreamError,
)
from apps.trips.serializers import TripPlanSerializer
from apps.trips.services import TripRequest, TripService
from apps.weather.providers import OpenMeteoProvider
from apps.weather.providers import UpstreamError as WeatherUpstreamError

logger = logging.getLogger(__name__)


def build_service() -> TripService:
    """Factory for a per-request service (no shared Session/cache across threads)."""
    return TripService(
        geocoder=NominatimGeocoder(),
        routing=OSRMProvider(),
        weather=OpenMeteoProvider(),
    )


class TripPlanView(APIView):
    serializer_class = TripPlanSerializer

    @extend_schema(
        tags=["trips"],
        summary="Plan weather-aware routes",
        description=(
            "Geocode origin/destination, fetch up to 3 OSRM routes, sample Open-Meteo "
            "weather at each checkpoint ETA, score risk (wind/rain/snow + load rules), "
            "and return routes ranked best-first with a 0-48h corridor forecast."
        ),
        request=TripPlanSerializer,
        responses={200: {"description": "Ranked routes with checkpoints and corridor forecast."}},
    )
    def post(self, request: Request) -> Response:
        ser = TripPlanSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        try:
            plan = build_service().plan(
                TripRequest(
                    origin=v["origin"],
                    destination=v["destination"],
                    departure=v["departure"],
                    load_lbs=v["load_lbs"],
                    interval_miles=v.get("interval_miles"),
                )
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except (RoutingUpstreamError, WeatherUpstreamError, requests.RequestException):
            logger.warning("Upstream provider error", exc_info=True)
            return Response(
                {"detail": "Upstream provider error; please retry shortly."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("Unexpected trip planning failure")
            return Response(
                {"detail": "Internal planning error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                "recommended_route_id": plan.recommended_route_id,
                "blocked": plan.blocked,
                "routes": plan.routes,
            }
        )


class HealthView(APIView):
    @extend_schema(
        tags=["health"],
        summary="Liveness probe",
        responses={200: {"description": '{"status": "ok"}'}},
    )
    def get(self, _request: Request) -> Response:
        return Response({"status": "ok"})
