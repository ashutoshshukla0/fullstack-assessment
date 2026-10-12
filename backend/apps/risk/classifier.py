"""Weather risk classification.

Thresholds per checkpoint:
  Wind (mph):   <25 Low | 25-34 Moderate | 35-44 High | 45-54 Severe | >=55 No Travel
  Rain (in/hr): <0.10 Low | 0.10-0.25 Moderate | 0.25-0.50 High | 0.50-1.00 Severe | >1.00 No Travel
  Snow (in/hr): <0.5 Low | 0.5-1.0 Moderate | 1.0-2.0 High | 2.0-3.0 Severe | >3.0 No Travel

Load rules (wind only, applied after the base classification):
  - wind >= 55 mph -> No Travel for any load
  - wind >= 45 mph and load > 30,000 lb -> No Travel
  - wind >= 35 mph and load > 40,000 lb -> Severe

Checkpoint risk is the highest of wind, rain and snow risk.
"""

import math
from dataclasses import dataclass
from typing import TypedDict

from .levels import RiskLevel

# Wind thresholds (mph). Lower-bound inclusive.
WIND_NO_TRAVEL_MPH = 55.0
WIND_SEVERE_MPH = 45.0
WIND_HIGH_MPH = 35.0
WIND_MODERATE_MPH = 25.0

# Rain thresholds (in/hr). Severe and below are lower-bound inclusive;
# No Travel is strictly greater than the severe band.
RAIN_NO_TRAVEL_IN_HR = 1.00
RAIN_SEVERE_IN_HR = 0.50
RAIN_HIGH_IN_HR = 0.25
RAIN_MODERATE_IN_HR = 0.10

# Snow thresholds (in/hr), same inclusivity convention as rain.
SNOW_NO_TRAVEL_IN_HR = 3.0
SNOW_SEVERE_IN_HR = 2.0
SNOW_HIGH_IN_HR = 1.0
SNOW_MODERATE_IN_HR = 0.5

# Load escalation bands (lb).
HEAVY_LOAD_LBS = 30_000.0
VERY_HEAVY_LOAD_LBS = 40_000.0


@dataclass(frozen=True)
class CheckpointWeather:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float


class CheckpointRisk(TypedDict):
    wind_risk: RiskLevel
    rain_risk: RiskLevel
    snow_risk: RiskLevel
    overall: RiskLevel


class WeatherRiskClassifier:
    """Pure function object: no I/O, no state. Safe to share across threads."""

    @staticmethod
    def _require_finite(name: str, value: float) -> float:
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite, got {value!r}")
        return float(value)

    def classify_wind(self, mph: float) -> RiskLevel:
        mph = self._require_finite("wind_mph", mph)
        if mph >= WIND_NO_TRAVEL_MPH:
            return RiskLevel.NO_TRAVEL
        if mph >= WIND_SEVERE_MPH:
            return RiskLevel.SEVERE
        if mph >= WIND_HIGH_MPH:
            return RiskLevel.HIGH
        if mph >= WIND_MODERATE_MPH:
            return RiskLevel.MODERATE
        return RiskLevel.LOW

    def classify_rain(self, in_hr: float) -> RiskLevel:
        in_hr = self._require_finite("rain_in_hr", in_hr)
        if in_hr > RAIN_NO_TRAVEL_IN_HR:
            return RiskLevel.NO_TRAVEL
        if in_hr >= RAIN_SEVERE_IN_HR:
            return RiskLevel.SEVERE
        if in_hr >= RAIN_HIGH_IN_HR:
            return RiskLevel.HIGH
        if in_hr >= RAIN_MODERATE_IN_HR:
            return RiskLevel.MODERATE
        return RiskLevel.LOW

    def classify_snow(self, in_hr: float) -> RiskLevel:
        in_hr = self._require_finite("snow_in_hr", in_hr)
        if in_hr > SNOW_NO_TRAVEL_IN_HR:
            return RiskLevel.NO_TRAVEL
        if in_hr >= SNOW_SEVERE_IN_HR:
            return RiskLevel.SEVERE
        if in_hr >= SNOW_HIGH_IN_HR:
            return RiskLevel.HIGH
        if in_hr >= SNOW_MODERATE_IN_HR:
            return RiskLevel.MODERATE
        return RiskLevel.LOW

    def apply_load_rules(
        self, wind_mph: float, base_wind_risk: RiskLevel, load_lbs: float
    ) -> RiskLevel:
        """Escalate wind risk for heavy loads. Wind-only; rain/snow unaffected."""
        wind_mph = self._require_finite("wind_mph", wind_mph)
        load_lbs = self._require_finite("load_lbs", load_lbs)
        if load_lbs < 0:
            raise ValueError(f"load_lbs must be >= 0, got {load_lbs!r}")
        if wind_mph >= WIND_NO_TRAVEL_MPH:
            return RiskLevel.NO_TRAVEL
        if wind_mph >= WIND_SEVERE_MPH and load_lbs > HEAVY_LOAD_LBS:
            return RiskLevel.NO_TRAVEL
        if wind_mph >= WIND_HIGH_MPH and load_lbs > VERY_HEAVY_LOAD_LBS:
            return max(base_wind_risk, RiskLevel.SEVERE)
        return base_wind_risk

    def classify_checkpoint(self, weather: CheckpointWeather, load_lbs: float) -> CheckpointRisk:
        wind_risk = self.apply_load_rules(
            weather.wind_mph, self.classify_wind(weather.wind_mph), load_lbs
        )
        rain_risk = self.classify_rain(weather.rain_in_hr)
        snow_risk = self.classify_snow(weather.snow_in_hr)
        return {
            "wind_risk": wind_risk,
            "rain_risk": rain_risk,
            "snow_risk": snow_risk,
            "overall": max(wind_risk, rain_risk, snow_risk),
        }
