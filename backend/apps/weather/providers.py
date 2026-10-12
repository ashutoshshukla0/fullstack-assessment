"""Open-Meteo weather provider."""

import logging
import math
import threading
import time
from bisect import bisect_left
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings

from .interfaces import HourlyWeather, IWeatherProvider

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 15
PAST_DAYS = 1
FORECAST_DAYS = 3
CACHE_ROUND_DIGITS = 3
CACHE_TTL_S = 1800
SNOW_CM_TO_IN = 0.393701
WINDOW_TOLERANCE_H = 1


class UpstreamError(Exception):
    """Upstream weather provider failure. Maps to HTTP 502."""


class OpenMeteoProvider(IWeatherProvider):
    """Thin client over the Open-Meteo forecast API.

    Instances hold a small coordinate-keyed cache so the two reads
    :meth:`get_at` and :meth:`get_hourly_range` perform per checkpoint
    share a single HTTP fetch.
    """

    def __init__(self, base_url: str | None = None, session: requests.Session | None = None):
        self.base_url = (base_url or settings.OPEN_METEO_BASE_URL).rstrip("/")
        self.session = session or requests.Session()
        self._cache: dict[tuple[float, float], tuple[float, list[HourlyWeather]]] = {}
        self._lock = threading.Lock()

    def clear_cache(self) -> None:
        """Drop cached hourly series (useful in tests and long-lived processes)."""
        with self._lock:
            self._cache.clear()

    def _fetch(self, lat: float, lon: float) -> dict:
        resp = self.session.get(
            f"{self.base_url}/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "wind_speed_10m,precipitation,rain,snowfall,precipitation_probability",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "temperature_unit": "fahrenheit",
                "timezone": "UTC",
                "past_days": PAST_DAYS,
                "forecast_days": FORECAST_DAYS,
            },
            timeout=REQUEST_TIMEOUT_S,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError as exc:
            raise UpstreamError("Weather provider returned invalid JSON") from exc

    @staticmethod
    def _num(value, default: float = 0.0) -> float:
        # Missing/None -> default with a debug log; NaN/inf -> raise so a
        # missing sensor never classifies as calm "Low".
        if value is None:
            return default
        try:
            f = float(value)
        except (TypeError, ValueError):
            logger.debug("Non-numeric weather value %r; using default %s", value, default)
            return default
        if not math.isfinite(f):
            raise UpstreamError(f"Weather provider returned non-finite value: {value!r}")
        return f

    @staticmethod
    def _parse(payload: dict) -> list[HourlyWeather]:
        try:
            h = payload["hourly"]
            times = h["time"]
            winds = h["wind_speed_10m"]
        except (KeyError, TypeError) as exc:
            raise UpstreamError("Weather provider response missing hourly/time/wind") from exc
        if not isinstance(times, list) or not isinstance(winds, list):
            raise UpstreamError("Weather provider returned malformed hourly series")
        n = len(times)
        if len(winds) != n:
            raise UpstreamError("Weather provider returned ragged hourly columns")

        def _col(key: str) -> list:
            vals = h.get(key)
            if vals is None:
                logger.debug("Weather column %s missing; filling zeros", key)
                return [0] * n
            if not isinstance(vals, list) or len(vals) != n:
                logger.debug("Weather column %s ragged; filling zeros", key)
                return [0] * n
            return vals

        rain = _col("rain")
        snow = _col("snowfall")
        prob = _col("precipitation_probability")
        out = []
        for i, t in enumerate(times):
            try:
                dt = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
            except ValueError as exc:
                raise UpstreamError(f"Weather provider returned bad timestamp: {t!r}") from exc
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            out.append(
                HourlyWeather(
                    time=dt,
                    wind_mph=OpenMeteoProvider._num(winds[i]),
                    rain_in_hr=OpenMeteoProvider._num(rain[i]) if i < len(rain) else 0.0,
                    snow_in_hr=OpenMeteoProvider._num(snow[i]) if i < len(snow) else 0.0,
                    precip_prob_pct=OpenMeteoProvider._num(prob[i]) if i < len(prob) else 0.0,
                )
            )
        return out

    def _hourlies(self, lat: float, lon: float) -> list[HourlyWeather]:
        key = (round(lat, CACHE_ROUND_DIGITS), round(lon, CACHE_ROUND_DIGITS))
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None and now - hit[0] < CACHE_TTL_S:
                return hit[1]
        try:
            raw = self._fetch(lat, lon)
            hourlies = self._parse(raw)
        except requests.RequestException as exc:
            raise UpstreamError(f"Weather fetch failed: {exc}") from exc
        # Open-Meteo reports snowfall in cm; wind/rain already arrive in
        # mph/inches via the request params. Classify on raw values —
        # rounding happens only at display time.
        fixed = [
            HourlyWeather(
                time=h.time,
                wind_mph=h.wind_mph,
                rain_in_hr=h.rain_in_hr,
                snow_in_hr=h.snow_in_hr * SNOW_CM_TO_IN,
                precip_prob_pct=h.precip_prob_pct,
            )
            for h in hourlies
        ]
        if not fixed:
            raise UpstreamError("Weather provider returned no hourly data")
        with self._lock:
            # Bound growth: evict oldest entries past 512 keys.
            if len(self._cache) >= 512:
                oldest = min(self._cache.items(), key=lambda kv: kv[1][0])[0]
                del self._cache[oldest]
            self._cache[key] = (now, fixed)
        return fixed

    @staticmethod
    def _ensure_aware(when: datetime) -> datetime:
        return when if when.tzinfo is not None else when.replace(tzinfo=timezone.utc)

    def get_at(self, lat: float, lon: float, when: datetime) -> HourlyWeather:
        """Nearest hourly observation to ``when``.

        Raises:
            ValueError: If ``when`` lies outside the fetched window or the
                provider returns no data.
        """
        hourlies = self._hourlies(lat, lon)
        when = self._ensure_aware(when)
        first, last = hourlies[0].time, hourlies[-1].time
        if when < first - timedelta(hours=WINDOW_TOLERANCE_H) or when > last + timedelta(
            hours=WINDOW_TOLERANCE_H
        ):
            raise UpstreamError(
                f"ETA {when.isoformat()} outside weather window "
                f"{first.isoformat()}..{last.isoformat()}"
            )
        times = [h.time for h in hourlies]
        idx = bisect_left(times, when)
        candidates = [i for i in (idx - 1, idx, idx + 1) if 0 <= i < len(hourlies)]
        best = min(candidates, key=lambda i: abs((hourlies[i].time - when).total_seconds()))
        return hourlies[best]

    def get_hourly_range(
        self, lat: float, lon: float, start: datetime, hours: int = 48
    ) -> list[HourlyWeather]:
        """Hourly series starting at ``start`` (up to ``hours`` + 1 entries)."""
        hourlies = self._hourlies(lat, lon)
        start = self._ensure_aware(start)
        times = [h.time for h in hourlies]
        idx = bisect_left(times, start)
        return hourlies[idx : idx + hours + 1]
