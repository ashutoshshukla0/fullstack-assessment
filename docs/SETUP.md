# Setup & Deployment

## Prerequisites

- Python 3.12 with `pip` (Docker images use `3.12-slim`)
- Node 20 with `npm` (Docker images use `node:20-slim`)
- No API keys needed (Nominatim, OSRM, Open-Meteo are all free)

## Local

```bash
# backend - Django + DRF (sqlite, no migrations needed: no models)
pip install -r backend/requirements.txt
PYTHONPATH=backend python backend/manage.py runserver 8000

# frontend - React + TS + Tailwind + Leaflet
cd frontend && npm ci && npm run dev   # http://localhost:5173
```

Then open `http://localhost:5173` (app) and `http://localhost:8000/api/docs/` (Swagger UI).

Vite proxies `/api` → `http://localhost:8000` (see `vite.config.ts`; override with `VITE_PROXY_TARGET=http://api:8000` inside Docker). For production builds set `VITE_API_BASE=https://<api-host>` then `npm run build` (outputs `dist/`).

Copy `.env.sample` to `.env` to override any defaults locally (`cp .env.sample .env`); `.env` is git-ignored and loaded by `docker-compose.yml`.

## Env vars (backend)

| Var | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev-only | prod secret |
| `DJANGO_DEBUG` | `1` | `0` in prod |
| `DJANGO_ALLOWED_HOSTS` | `*` | prod host list |
| `DJANGO_CORS_ALLOW_ALL` | `1` | `0` in prod behind a fixed frontend |
| `OSRM_BASE_URL` | `https://router.project-osrm.org` | self-hostable; point at own OSRM for SLA |
| `NOMINATIM_BASE_URL` | `https://nominatim.openstreetmap.org` | comply with usage policy (1 req/s, User-Agent) for heavy use |
| `OPEN_METEO_BASE_URL` | `https://api.open-meteo.com` | commercial fallback exists |
| `NOMINATIM_USER_AGENT` | `weather-truck-routing/1.0` | identify your deployment |
| `API_THROTTLE_RATE` | `60/min` | anonymous API rate limit |
| `LOG_LEVEL` | `INFO` | `DEBUG` for troubleshooting |

## Tests

```bash
PYTHONPATH=backend python -m pytest backend/apps -q   # ~64 tests (parametrized)
cd frontend && npx vitest run                          # 13 tests across 3 files
npx tsc --noEmit                                       # frontend type gate
ruff check backend/apps                                # backend lint
```

CI (`.github/workflows/ci.yml`) runs all four on push/PR.

## Deploy pointers

- **Backend:** image defaults to `gunicorn config.wsgi` (3 workers); `docker-compose.yml` overrides to `runserver` for local dev. Any PaaS with `PYTHONPATH=backend` works.
- **Frontend:** static `dist/` to Netlify/Vercel/S3 with `VITE_API_BASE` pointing at the API.
- **3 routes guaranteed:** OSRM free tier often returns 1 native alternate; the provider auto-builds via-point detours on real roads until 3 distinct routes (see Architecture §1). Optionally add a `MapboxProvider`/`ORSProvider` (key-based, true alternatives) implementing `IRoutingProvider` and rewire `apps/trips/views.py` — 1 file, no other changes.

## One-command run

```bash
docker compose up --build   # api :8000, web :5173
```

## Troubleshooting

- `departure must include a timezone offset`: the API requires tz-aware ISO (e.g. `2026-01-01T08:00:00Z`). The form always sends `toISOString()` (UTC).
- `departure must be within 2d past / 4d future`: Open-Meteo only serves `past_days=1` + `forecast_days=3`. Pick a nearer departure.
- Only 1 route returned: the road network genuinely allows no more distinct corridors; the log notes `Only N distinct route(s) found`.
- `Upstream provider error; please retry shortly` (502): OSRM demo server rate-limits; wait and retry, or self-host OSRM and set `OSRM_BASE_URL`.
- `auth/contenttypes` migration warning on first `runserver`: harmless (no models); run `manage.py migrate` to silence.
- CORS errors in prod: set `DJANGO_CORS_ALLOW_ALL=0` and configure `CORS_ALLOWED_ORIGINS` for the frontend host.
