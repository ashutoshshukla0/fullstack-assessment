from datetime import datetime, timedelta, timezone

from apps.routing.interfaces import LatLon, RouteGeometry
from apps.trips.services import TripRequest, TripService
from apps.weather.interfaces import HourlyWeather

DEP = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)


class FakeGeocoder:
    def geocode(self, q):
        return {"A": LatLon(0, 0), "B": LatLon(0, 2.0)}[q]


class FakeRouting:
    def get_routes(self, o, d):
        # Two geographically distinct routes so weather can be deterministic
        # regardless of thread scheduling (parallel fetch).
        calm = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
        stormy = [(0.0, 5.0), (1.0, 5.0), (2.0, 5.0)]
        return [
            RouteGeometry(calm, distance_m=138 * 1609.344, duration_s=7200),  # fast
            RouteGeometry(stormy, distance_m=138 * 1609.344, duration_s=9000),  # slow
        ]


class FakeWeather:
    def get_at(self, lat, lon, when):
        stormy = lat > 1.0
        return HourlyWeather(
            time=when, wind_mph=60.0 if stormy else 10.0, rain_in_hr=0.0, snow_in_hr=0.0
        )

    def get_hourly_range(self, lat, lon, start, hours=48):
        return [
            HourlyWeather(
                time=start + timedelta(hours=i),
                wind_mph=10.0,
                rain_in_hr=0.0,
                snow_in_hr=0.0,
            )
            for i in range(hours + 1)
        ]


def test_plan_recommends_calmer_route_and_sorts_best_first():
    svc = TripService(FakeGeocoder(), FakeRouting(), FakeWeather())
    plan = svc.plan(
        TripRequest(
            origin="A",
            destination="B",
            departure=DEP,
            load_lbs=10_000,
            interval_miles=50,
        )
    )
    assert len(plan.routes) == 2
    assert plan.recommended_route_id == "route-1"
    assert plan.routes[0]["id"] == "route-1"
    assert plan.routes[0]["recommended"] is True
    assert plan.routes[1]["checkpoints"][0]["risk"] == "No Travel"
    assert len(plan.routes[0]["corridor_forecast"][0]["hourly"]) == 49


def test_plan_empty_routes_raises():
    class Empty:
        def get_routes(self, o, d):
            return []

    svc = TripService(FakeGeocoder(), Empty(), FakeWeather())
    import pytest

    with pytest.raises(ValueError):
        svc.plan(TripRequest(origin="A", destination="B", departure=DEP, load_lbs=0))


def test_plan_degrades_on_weather_failure():
    class BadWeather(FakeWeather):
        def get_at(self, lat, lon, when):
            raise ValueError("boom")

    svc = TripService(FakeGeocoder(), FakeRouting(), BadWeather())
    plan = svc.plan(TripRequest(origin="A", destination="B", departure=DEP, load_lbs=0))
    assert len(plan.routes) == 2
    assert plan.routes[0]["checkpoints"][0]["weather_degraded"] is True


def test_plan_all_no_travel_recommends_none():
    class Storm(FakeWeather):
        def get_at(self, lat, lon, when):
            return HourlyWeather(time=when, wind_mph=80.0, rain_in_hr=0.0, snow_in_hr=0.0)

    svc = TripService(FakeGeocoder(), FakeRouting(), Storm())
    plan = svc.plan(TripRequest(origin="A", destination="B", departure=DEP, load_lbs=0))
    assert plan.recommended_route_id is None
    assert plan.blocked is True
