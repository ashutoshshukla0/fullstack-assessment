"""OSRM provider returns 3 routes via detour fallback when alternates run short."""

from apps.routing.interfaces import LatLon
from apps.routing.providers import OSRMProvider

ORIGIN = LatLon(41.88, -87.62)
DEST = LatLon(39.77, -86.16)


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _route_payload(geometries, dist=300_000.0, dur=12_000.0):
    return {
        "code": "Ok",
        "routes": [
            {"geometry": {"coordinates": g}, "distance": dist, "duration": dur} for g in geometries
        ],
    }


class _StubSession:
    """First call serves the alternatives payload, later calls pop via payloads."""

    def __init__(self, first, rest):
        self._first = first
        self._rest = list(rest)
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return _Resp(self._first)
        return _Resp(self._rest.pop(0))


def _line(lon0=0.0, lon1=1.0, lat=0.0, n=11):
    return [[lon0 + (lon1 - lon0) * i / (n - 1), lat] for i in range(n)]


def test_pads_to_three_with_detours():
    base = _line()
    alt = _route_payload([base])
    # Two clearly separated detour geometries (far apart in latitude).
    via1 = _route_payload([[[x, 0.5] for x, _ in base]])
    via2 = _route_payload([[[x, -0.5] for x, _ in base]])
    provider = OSRMProvider(session=_StubSession(alt, [via1, via2]))
    routes = provider.get_routes(ORIGIN, DEST)
    assert len(routes) == 3
    assert len({tuple(r.coordinates[0]) for r in routes}) == 3


def test_skips_duplicate_and_failed_vias():
    base = _line()
    alt = _route_payload([base])
    dup = _route_payload([base])  # identical corridor -> skipped
    noroute = {"code": "NoRoute", "message": "No route found"}
    good = _route_payload([[[x, 0.5] for x, _ in base]])
    good2 = _route_payload([[[x, -0.5] for x, _ in base]])
    provider = OSRMProvider(session=_StubSession(alt, [dup, noroute, good, good2]))
    routes = provider.get_routes(ORIGIN, DEST)
    assert len(routes) == 3
    assert sorted(r.coordinates[0][1] for r in routes) == [-0.5, 0.0, 0.5]


def test_three_native_alternates_need_no_extra_calls():
    base = _line()
    alt = _route_payload([base, [[x, 0.5] for x, _ in base], [[x, -0.5] for x, _ in base]])
    session = _StubSession(alt, [])
    provider = OSRMProvider(session=session)
    assert len(provider.get_routes(ORIGIN, DEST)) == 3
    assert session.calls == 1


def test_no_routes_still_raises():
    from apps.routing.providers import UpstreamError

    provider = OSRMProvider(session=_StubSession({"code": "NoRoute", "message": "No route"}, []))
    import pytest

    with pytest.raises(UpstreamError):
        provider.get_routes(ORIGIN, DEST)
