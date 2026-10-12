"""Location autocomplete endpoint."""

import logging

import requests
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.routing.providers import NominatimGeocoder

logger = logging.getLogger(__name__)

MIN_QUERY_CHARS = 2
DEFAULT_LIMIT = 5
MAX_LIMIT = 10

_suggester = NominatimGeocoder()


class AutocompleteView(APIView):
    @extend_schema(
        tags=["geocode"],
        summary="Location autocomplete (OpenStreetMap Nominatim)",
        description="Up to `limit` matches for a partial query; powers the origin/destination dropdowns.",
        parameters=[
            OpenApiParameter(
                name="q",
                required=True,
                type=str,
                description="Partial location text (min 2 chars).",
            ),
            OpenApiParameter(
                name="limit",
                required=False,
                type=int,
                description="Max suggestions, 1-10 (default 5).",
            ),
        ],
        responses={200: {"description": "{query, suggestions: [{display_name, lat, lon}]}"}},
    )
    def get(self, request: Request) -> Response:
        q = (request.query_params.get("q") or "").strip()
        if len(q) < MIN_QUERY_CHARS:
            return Response(
                {"detail": "Provide ?q= with at least 2 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            limit = int(request.query_params.get("limit", DEFAULT_LIMIT))
        except (TypeError, ValueError):
            return Response(
                {"detail": "limit must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        limit = max(1, min(limit, MAX_LIMIT))
        try:
            suggestions = _suggester.suggest(q, limit=limit)
        except requests.RequestException:
            logger.warning("Nominatim suggest failed", exc_info=True)
            return Response(
                {"detail": "Geocoding provider error; please retry shortly."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("Unexpected autocomplete failure")
            return Response(
                {"detail": "Internal geocoding error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                "query": q,
                "suggestions": [
                    {"display_name": s.display_name, "lat": s.lat, "lon": s.lon}
                    for s in suggestions
                ],
            }
        )
