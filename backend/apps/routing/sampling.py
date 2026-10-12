"""Sample checkpoints every N miles along a route polyline.

ETAs assume a constant average speed (total duration / total distance).
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

EARTH_MILES = 3958.8
METERS_PER_MILE = 1609.344
FALLBACK_SPEED_MPH = 50.0
DEST_DEDUP_TOL_MI = 1e-9


def haversine_miles(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in miles between two (lon, lat) points."""
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_MILES * math.asin(math.sqrt(h))


@dataclass(frozen=True)
class Checkpoint:
    index: int
    lon: float
    lat: float
    miles_from_origin: float
    eta: datetime


def default_interval_miles(total_miles: float) -> float:
    """Interval rule: up to 150 mi -> 10, up to 500 mi -> 25, otherwise 50."""
    if total_miles <= 150:
        return 10.0
    if total_miles <= 500:
        return 25.0
    return 50.0


def _resolve_interval(total_miles: float, interval_miles: float | None) -> float:
    if interval_miles is None:
        return default_interval_miles(total_miles)
    if not interval_miles > 0:
        raise ValueError(f"interval_miles must be > 0, got {interval_miles!r}")
    return float(interval_miles)


def _cumulative_miles(coordinates: list[tuple[float, float]]) -> list[float]:
    cum = [0.0]
    for i in range(1, len(coordinates)):
        cum.append(cum[-1] + haversine_miles(coordinates[i - 1], coordinates[i]))
    return cum


def _targets(total_miles: float, interval: float) -> list[float]:
    targets = []
    d = 0.0
    while d < total_miles:
        targets.append(d)
        d += interval
    # Always include the destination, without duplicating it when the total
    # falls exactly on an interval boundary.
    if not targets or abs(targets[-1] - total_miles) > DEST_DEDUP_TOL_MI:
        targets.append(total_miles)
    return targets


def sample_checkpoints(
    coordinates: list[tuple[float, float]],
    total_distance_m: float,
    total_duration_s: float,
    departure: datetime,
    interval_miles: float | None = None,
) -> list[Checkpoint]:
    """Sample checkpoints along a GeoJSON-ordered polyline.

    Args:
        coordinates: [(lon, lat), ...] route geometry.
        total_distance_m: OSRM route distance in meters.
        total_duration_s: OSRM route duration in seconds.
        departure: Trip departure (tz-aware preferred; naive is used as-is).
        interval_miles: Checkpoint spacing; defaults via
            :func:`default_interval_miles`.

    Raises:
        ValueError: If geometry has < 2 points or ``interval_miles <= 0``.
    """
    if len(coordinates) < 2:
        raise ValueError("Route geometry needs at least 2 coordinates")
    total_miles = total_distance_m / METERS_PER_MILE
    interval = _resolve_interval(total_miles, interval_miles)
    avg_mph = (
        total_miles / (total_duration_s / 3600) if total_duration_s > 0 else FALLBACK_SPEED_MPH
    )

    cum = _cumulative_miles(coordinates)
    # Haversine underestimates road distance; rescale to the OSRM total.
    scale = total_miles / cum[-1] if cum[-1] > 0 else 1.0

    checkpoints: list[Checkpoint] = []
    seg = 0
    for idx, t in enumerate(_targets(total_miles, interval)):
        scaled_t = t / scale if scale else t
        while seg < len(cum) - 2 and cum[seg + 1] < scaled_t:
            seg += 1
        c0, c1 = cum[seg], cum[seg + 1]
        frac = 0.0 if c1 == c0 else (scaled_t - c0) / (c1 - c0)
        frac = max(0.0, min(1.0, frac))
        lon = coordinates[seg][0] + frac * (coordinates[seg + 1][0] - coordinates[seg][0])
        lat = coordinates[seg][1] + frac * (coordinates[seg + 1][1] - coordinates[seg][1])
        eta = departure + timedelta(hours=t / avg_mph) if avg_mph > 0 else departure
        checkpoints.append(Checkpoint(index=idx, lon=lon, lat=lat, miles_from_origin=t, eta=eta))
    return checkpoints
