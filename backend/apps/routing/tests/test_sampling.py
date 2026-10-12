from datetime import datetime, timezone

from apps.routing.sampling import default_interval_miles, sample_checkpoints

LINE = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
DEP = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


def test_default_interval_rule():
    assert default_interval_miles(100) == 10
    assert default_interval_miles(300) == 25
    assert default_interval_miles(900) == 50


def test_samples_include_origin_and_destination():
    cps = sample_checkpoints(
        LINE,
        total_distance_m=138 * 1609.344,
        total_duration_s=2 * 3600,
        departure=DEP,
        interval_miles=50,
    )
    assert cps[0].miles_from_origin == 0
    assert abs(cps[-1].miles_from_origin - 138) < 1.0
    assert cps[-1].eta > cps[0].eta


def test_eta_proportional_to_distance():
    cps = sample_checkpoints(
        LINE,
        total_distance_m=138 * 1609.344,
        total_duration_s=2 * 3600,
        departure=DEP,
        interval_miles=69,
    )
    # halfway checkpoint ~1h after departure
    assert abs((cps[1].eta - DEP).total_seconds() - 3600) < 600


def test_rejects_short_geometry():
    import pytest

    with pytest.raises(ValueError):
        sample_checkpoints([(0, 0)], 1000, 100, DEP)
