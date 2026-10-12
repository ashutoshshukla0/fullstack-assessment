"""Routing interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LatLon:
    lat: float
    lon: float


@dataclass(frozen=True)
class RouteGeometry:
    coordinates: list[tuple[float, float]]  # [(lon, lat), ...] GeoJSON order
    distance_m: float
    duration_s: float


class IGeocoder(ABC):
    @abstractmethod
    def geocode(self, query: str) -> LatLon:
        """Raise ValueError when the address cannot be resolved."""


@dataclass(frozen=True)
class Suggestion:
    display_name: str
    lat: float
    lon: float


class ILocationSuggester(ABC):
    """Partial-query location suggestions for autocomplete inputs."""

    @abstractmethod
    def suggest(self, query: str, limit: int = 5) -> list[Suggestion]:
        """Up to `limit` matches for a partial query."""


class IRoutingProvider(ABC):
    @abstractmethod
    def get_routes(self, origin: LatLon, destination: LatLon) -> list[RouteGeometry]:
        """Return up to 3 route options, fastest first."""
