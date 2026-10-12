# Weather-Aware Truck Routing

React (TS + Tailwind + Leaflet) + Django REST Framework. Helps a truck driver choose the **safest route** from origin → destination given departure time, load weight, and live weather.

## What was built (maps 1:1 to the assessment)

| Requirement | Implementation |
|---|---|
| Origin, destination, departure datetime, load weight | `TripForm.tsx` → `POST /api/trips/plan/` · origin/destination are autocomplete dropdowns (`LocationAutocomplete.tsx` → `GET /api/geocode/autocomplete/`, open-source Nominatim via backend proxy) |
| 3 route options via routing API | OSRM `alternatives=3` + via-point detour fallback (`apps/routing/providers.py`): native alternates first, then origin → offset-via → destination variants on real roads (deduped by corridor overlap) until 3 distinct routes. |
| Sample weather every 10/25/50 mi at ETA | `apps/routing/sampling.py` - auto rule ≤150mi→10, ≤500mi→25, else 50; overridable via `interval_miles`. ETA = departure + distance-proportional time |
| Risk via risk/load rules | `apps/risk/classifier.py` - pure, fully TDD-tested boundary table |
| Recommend best route | `apps/risk/recommendation.py` - No-Travel → Severe → High → avg risk → time (`null` when all routes impassable) |
| Map: routes, checkpoints, risks, ETAs, summaries | `RouteMap.tsx` (Leaflet, fitBounds + canvas) + `RouteSummary.tsx` + `CheckpointTable.tsx` |
| Heatmap + 0–48h slider | Corridor forecast per checkpoint (`corridor_forecast`, anchored at checkpoint ETA) + debounced slider recolors markers via persistent heat layer; tooltip shows ETA risk vs +Nh risk |

**Live APIs (all free, no keys):** Nominatim (geocode) · OSRM demo server (routing) · Open-Meteo (weather, mph+inch).

## Tests

64 backend + 13 frontend, all passing:

```bash
# backend (from repo root)
pip install -r backend/requirements.txt
PYTHONPATH=backend python -m pytest backend/apps -q   # 64 passed
ruff check backend/apps

# frontend
cd frontend && npm ci && npx vitest run                # 13 passed (3 files)
npx tsc --noEmit
```

Key suites: `apps/risk/tests/test_risk.py` (every wind/rain/snow boundary + 3 load rules + NaN/negative guards), `test_recommendation.py` (priority order, all-No-Travel → None), `routing/tests/test_sampling.py` (interval rule, ETA math), `routing/tests/test_autocomplete.py` (suggest parsing + view 200/400/502/500), `routing/tests/test_routes_fallback.py` (detour pad/dup/no-extra-calls/UpstreamError), `trips/tests/test_trip_service.py` (orchestration with fakes, degradation, blocked), `test_api.py` (validation incl. naive-departure rejection), `test_docs.py` (OpenAPI schema covers all endpoints). CI runs all four gates on push/PR.

## Quickstart

```bash
# backend
pip install -r backend/requirements.txt
PYTHONPATH=backend python backend/manage.py runserver 8000  # :8000/api/health/

# frontend (new terminal)
cd frontend && npm ci && npm run dev                  # :5173 (proxies /api → :8000)
```

Try: Origin `Chicago, IL` → Destination `Indianapolis, IN`, departure = now+1h, load 35,000 lb. Then open `http://localhost:5173` (app) and `http://localhost:8000/api/docs/` (Swagger UI).

`docker compose up --build` runs both (api :8000, web :5173).

## API

`POST /api/trips/plan/` `{origin, destination, departure (tz-aware ISO), load_lbs, interval_miles?}` → `{recommended_route_id, blocked, routes[]}` where each route has `coordinates` (≤500 pts), `summary {total_miles, duration_s, avg_risk, miles_by_risk}`, `checkpoints[]` (weather + risk + ETA + `weather_degraded`), `corridor_forecast[]` (49 hourly risks per checkpoint for the slider), `blocked`, `corridor_degraded`. Full contract with example payloads: `docs/API.md`. Interactive Swagger UI at `GET /api/docs/` (schema: `/api/schema/`, ReDoc: `/api/redoc/`).

## Docs

- `docs/ARCHITECTURE.md` - modules, data flow, key decisions
- `docs/API.md` - endpoint contract with example payloads
- `docs/SETUP.md` - local/dev/prod, env vars, deployment pointers, troubleshooting
- `docker-compose.yml` - one-command run

## Repo layout

```
backend/{config/{settings,urls,wsgi},apps/{routing/{providers,sampling,views},weather/{providers,views},risk/{classifier,recommendation,levels},trips/{services,serializers,views}},Dockerfile,requirements.txt,pytest.ini,pyproject.toml}
frontend/src/{components/{RouteMap,TripForm,LocationAutocomplete,RouteSummary,CheckpointTable,ResultsSkeleton,ui/primitives},lib/{api,types,forecast},hooks/App/main}  # React + TS + Tailwind + Leaflet
docs/{ARCHITECTURE,API,SETUP}  # architecture, api, setup
docker-compose.yml  # api (gunicorn in prod image, runserver override for dev) + web
```
