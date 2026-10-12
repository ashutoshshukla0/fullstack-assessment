import pytest
from django.test import Client

from apps.routing import views as routing_views
from apps.routing.interfaces import Suggestion
from apps.routing.providers import NominatimGeocoder


class _StubSession:
    def __init__(self, payload):
        self.payload = payload
        self.last_params = None

    def get(self, url, params=None, headers=None, timeout=None):
        self.last_params = params

        class _Resp:
            def raise_for_status(self_inner):
                pass

            def json(self_inner):
                return self.payload

        return _Resp()


def test_suggest_parses_nominatim_and_skips_malformed():
    session = _StubSession(
        [
            {"display_name": "Chicago, Illinois, USA", "lat": "41.88", "lon": "-87.62"},
            {"display_name": "Broken entry"},  # missing lat/lon -> skipped
        ]
    )
    g = NominatimGeocoder(base_url="http://x", user_agent="test", session=session)
    out = g.suggest("Chica", limit=5)
    assert out == [Suggestion("Chicago, Illinois, USA", 41.88, -87.62)]
    assert session.last_params["q"] == "Chica"
    assert session.last_params["addressdetails"] == 1


def test_suggest_clamps_limit():
    session = _StubSession([])
    g = NominatimGeocoder(base_url="http://x", user_agent="test", session=session)
    g.suggest("Chicago", limit=99)
    assert session.last_params["limit"] == 10


@pytest.mark.django_db
def test_autocomplete_view_success(monkeypatch):
    class Stub:
        def suggest(self, q, limit=5):
            assert q == "Chica"
            return [Suggestion("Chicago, Illinois, USA", 41.88, -87.62)]

    monkeypatch.setattr(routing_views, "_suggester", Stub())
    resp = Client().get("/api/geocode/autocomplete/", {"q": "Chica"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "Chica"
    assert body["suggestions"][0]["display_name"] == "Chicago, Illinois, USA"


@pytest.mark.django_db
def test_autocomplete_view_rejects_short_or_missing_q():
    c = Client()
    assert c.get("/api/geocode/autocomplete/").status_code == 400
    assert c.get("/api/geocode/autocomplete/", {"q": "x"}).status_code == 400


@pytest.mark.django_db
def test_autocomplete_view_502_on_provider_error(monkeypatch):
    import requests

    class Boom:
        def suggest(self, q, limit=5):
            raise requests.ConnectionError("nominatim down")

    monkeypatch.setattr(routing_views, "_suggester", Boom())
    assert Client().get("/api/geocode/autocomplete/", {"q": "Chicago"}).status_code == 502


@pytest.mark.django_db
def test_autocomplete_view_500_on_unexpected_error(monkeypatch):
    class Boom:
        def suggest(self, q, limit=5):
            raise RuntimeError("nominatim down")

    monkeypatch.setattr(routing_views, "_suggester", Boom())
    assert Client().get("/api/geocode/autocomplete/", {"q": "Chicago"}).status_code == 500
