"""Weather provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class HourlyWeather:
    time: datetime
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float
    precip_prob_pct: float = 0.0


class IWeatherProvider(ABC):
    @abstractmethod
    def get_at(self, lat: float, lon: float, when: datetime) -> HourlyWeather:
        """Weather interpolated to the truck's ETA at a checkpoint."""

    @abstractmethod
    def get_hourly_range(
        self, lat: float, lon: float, start: datetime, hours: int = 48
    ) -> list[HourlyWeather]:
        """48h corridor forecast for the heatmap slider."""
