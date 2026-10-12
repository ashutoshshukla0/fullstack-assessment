import json
from datetime import datetime, timedelta, timezone

import pytest
from django.test import Client

from apps.trips import views as trip_views


@pytest.mark.django_db
def test_plan_validation_rejects_bad_input():
    c = Client()
    resp = c.post("/api/trips/plan/", data=json.dumps({}), content_type="application/json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_plan_success_with_stubbed_service(monkeypatch):
    from apps.trips.services import TripPlan

    fake = TripPlan(routes=[{"id": "route-1", "recommended": True}], recommended_route_id="route-1")

    class Stub:
        def plan(self, req):
            assert req.origin and req.destination
            return fake

    monkeypatch.setattr(trip_views, "build_service", lambda: Stub())
    c = Client()
    dep = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    resp = c.post(
        "/api/trips/plan/",
        data=json.dumps(
            {
                "origin": "Chicago, IL",
                "destination": "Detroit, MI",
                "departure": dep,
                "load_lbs": 30000,
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json()["recommended_route_id"] == "route-1"


@pytest.mark.django_db
def test_plan_rejects_naive_departure():
    c = Client()
    resp = c.post(
        "/api/trips/plan/",
        data=json.dumps(
            {
                "origin": "Chicago, IL",
                "destination": "Detroit, MI",
                "departure": "2026-01-01T08:00:00",
                "load_lbs": 30000,
            }
        ),
        content_type="application/json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_health():
    assert Client().get("/api/health/").json() == {"status": "ok"}
