from datetime import datetime, timezone

from apps.weather.providers import OpenMeteoProvider


def _payload():
    return {
        "hourly": {
            "time": ["2026-01-01T08:00", "2026-01-01T09:00"],
            "wind_speed_10m": [10.0, 60.0],
            "precipitation": [0.0, 0.0],
            "rain": [0.0, 0.071],
            "snowfall": [2.54, 0.0],  # 2.54cm == 1.0 inch
            "precipitation_probability": [5, 80],
        }
    }


def test_parse_reads_hourly_values():
    out = OpenMeteoProvider._parse(_payload())
    assert out[0].wind_mph == 10.0
    assert abs(out[0].snow_in_hr - 2.54) < 0.001
    assert out[0].rain_in_hr == 0.0
    assert out[1].rain_in_hr == 0.071
    assert out[0].precip_prob_pct == 5
    assert out[1].precip_prob_pct == 80


def test_parse_tolerates_missing_optional_columns():
    payload = _payload()
    del payload["hourly"]["rain"]
    del payload["hourly"]["precipitation_probability"]
    out = OpenMeteoProvider._parse(payload)
    assert out[0].rain_in_hr == 0.0
    assert out[0].precip_prob_pct == 0.0


def test_get_at_picks_nearest_hour(monkeypatch):
    p = OpenMeteoProvider.__new__(OpenMeteoProvider)
    fixed = OpenMeteoProvider._parse(_payload())
    from apps.weather.interfaces import HourlyWeather

    fixed = [
        HourlyWeather(
            time=h.time.replace(tzinfo=timezone.utc),
            wind_mph=h.wind_mph,
            rain_in_hr=h.rain_in_hr,
            snow_in_hr=h.snow_in_hr * 0.393701,
        )
        for h in fixed
    ]
    p._hourlies = lambda lat, lon: fixed  # type: ignore
    got = p.get_at(0, 0, datetime(2026, 1, 1, 8, 20, tzinfo=timezone.utc))
    assert got.wind_mph == 10.0
    assert abs(got.snow_in_hr - 1.0) < 0.01
    rng = p.get_hourly_range(0, 0, datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc), hours=1)
    assert len(rng) == 2
