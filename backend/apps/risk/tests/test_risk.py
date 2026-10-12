import pytest

from apps.risk.classifier import CheckpointWeather, WeatherRiskClassifier
from apps.risk.levels import RiskLevel

C = WeatherRiskClassifier()


@pytest.mark.parametrize(
    "mph,expected",
    [
        (0, "Low"),
        (24.9, "Low"),
        (25, "Moderate"),
        (34, "Moderate"),
        (35, "High"),
        (44, "High"),
        (45, "Severe"),
        (54, "Severe"),
        (55, "No Travel"),
        (80, "No Travel"),
    ],
)
def test_wind_thresholds(mph, expected):
    assert C.classify_wind(mph).label == expected


@pytest.mark.parametrize(
    "inch,expected",
    [
        (0, "Low"),
        (0.09, "Low"),
        (0.10, "Moderate"),
        (0.24, "Moderate"),
        (0.25, "High"),
        (0.49, "High"),
        (0.50, "Severe"),
        (0.51, "Severe"),
        (1.00, "Severe"),
        (1.01, "No Travel"),
    ],
)
def test_rain_thresholds(inch, expected):
    assert C.classify_rain(inch).label == expected


@pytest.mark.parametrize(
    "inch,expected",
    [
        (0, "Low"),
        (0.49, "Low"),
        (0.5, "Moderate"),
        (0.99, "Moderate"),
        (1.0, "High"),
        (1.99, "High"),
        (2.0, "Severe"),
        (2.01, "Severe"),
        (3.0, "Severe"),
        (3.01, "No Travel"),
    ],
)
def test_snow_thresholds(inch, expected):
    assert C.classify_snow(inch).label == expected


def test_overall_is_max_of_conditions():
    w = CheckpointWeather(wind_mph=10, rain_in_hr=0.6, snow_in_hr=0)
    assert C.classify_checkpoint(w, load_lbs=10_000)["overall"] == RiskLevel.SEVERE


def test_load_rule_55mph_always_no_travel():
    w = CheckpointWeather(wind_mph=60, rain_in_hr=0, snow_in_hr=0)
    assert C.classify_checkpoint(w, load_lbs=1)["overall"] == RiskLevel.NO_TRAVEL


def test_load_rule_45_54_over_30k_no_travel():
    w = CheckpointWeather(wind_mph=50, rain_in_hr=0, snow_in_hr=0)
    assert C.classify_checkpoint(w, load_lbs=30_001)["overall"] == RiskLevel.NO_TRAVEL
    assert C.classify_checkpoint(w, load_lbs=30_000)["overall"] == RiskLevel.SEVERE


def test_load_rule_35_44_over_40k_escalates_to_severe():
    w = CheckpointWeather(wind_mph=40, rain_in_hr=0, snow_in_hr=0)
    assert C.classify_checkpoint(w, load_lbs=40_001)["overall"] == RiskLevel.SEVERE
    assert C.classify_checkpoint(w, load_lbs=40_000)["overall"] == RiskLevel.HIGH
