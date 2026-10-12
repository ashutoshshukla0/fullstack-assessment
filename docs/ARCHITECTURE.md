# Architecture

## Data flow

```
TripForm → POST /api/trips/plan/
  → TripPlanSerializer (validate)
  → TripService.plan (works against IGeocoder / IRoutingProvider / IWeatherProvider)
      1. geocode ×2 (Nominatim)
      2. get_routes (OSRM, alternatives=3, geojson)
      3. sample_checkpoints per route (10/25/50 auto rule, ETA ∝ distance)
      4. get_at per checkpoint (Open-Meteo, nearest hour)
         + get_hourly_range per checkpoint (49 pts, 0–48h heatmap)
      5. WeatherRiskClassifier per checkpoint (+ load escalation)
      6. RouteRecommender ranks (NoTravel → Severe → High → avg → time)
  → JSON { recommended_route_id, routes[] }
  → React: RouteSummary (rank cards) + RouteMap (Leaflet) + slider + CheckpointTable

LocationAutocomplete → GET /api/geocode/autocomplete/?q=… (Nominatim proxied)
API docs → GET /api/docs/ (Swagger UI), /api/schema/ (OpenAPI), /api/redoc/
```

## Modules

| Path | Responsibility |
|---|---|
| `apps/risk/levels.py` | `RiskLevel` enum (0–4) + colors, single source of truth |
| `apps/risk/classifier.py` | Pure thresholds + load rules. No I/O |
| `apps/risk/recommendation.py` | `RouteScore` + sort key. No I/O |
| `apps/routing/interfaces.py` | `IGeocoder`, `ILocationSuggester`, `IRoutingProvider`, `LatLon`, `RouteGeometry`, `Suggestion` |
| `apps/routing/providers.py` | `NominatimGeocoder`, `OSRMProvider` |
| `apps/routing/sampling.py` | Haversine walk + interpolation + ETA model |
| `apps/routing/views.py` + `urls.py` | `GET /api/geocode/autocomplete/` (location dropdown) |
| `apps/weather/interfaces.py` | `HourlyWeather`, `IWeatherProvider` |
| `apps/weather/providers.py` | `OpenMeteoProvider` (mph/inch params, snowfall cm→in fix, nearest-hour + range) |
| `apps/trips/services.py` | `TripService` orchestrator + `TripRequest`/`TripPlan` |
| `apps/trips/views.py` | `POST /api/trips/plan/`, `GET /api/health/` |
| `config/urls.py` | Route table incl. `/api/docs/`, `/api/schema/`, `/api/redoc/` (drf-spectacular) |
| `frontend/src/lib/*` | `types.ts` (shared contract), `api.ts` (fetch client incl. location search) |
| `frontend/src/components/LocationAutocomplete.tsx` | Debounced dropdown for origin/destination |

## Key decisions

1. **Free APIs, no keys** — Nominatim + OSRM + Open-Meteo so the app runs immediately. Trade-off: OSRM demo server rate-limits and often returns **1** native alternate. `OSRMProvider.get_routes` compensates with via-point detours (offset perpendicular to the base route at 1/3 and 2/3, both sides, corridor-overlap dedupe, max 4 extra fetches) so the app serves 3 distinct routes; the recommender, UI, and tests handle 1–3 regardless. For premium alternatives, plug a `MapboxProvider implements IRoutingProvider` (one new file, rewire `views.py`) — no other code changes (OCP/DIP).
2. **ETA model: constant average speed** per route (`duration/distance`). Documented in code + UI. Good enough for checkpoint weather lookup; a traffic-aware ETA would be the next iteration.
3. **Boundary convention: lower-bound inclusive** (spec ranges overlap at 0.25/0.50/1.0/2.0 etc.). E.g. rain 0.25 → High, 0.50 → Severe; snow 1.0 → High, 2.0 → Severe. Tests pin this.
4. **No-Travel sorts before Severe.** Spec ranks Severe first; No-Travel is strictly worse, so the key is `(no_travel, severe, high, avg, duration)` - a documented superset preserving spec order elsewhere.
5. **Snowfall unit fix.** Open-Meteo returns snowfall in cm even with `precipitation_unit=inch`; provider converts cm→in (×0.3937). Covered by test.
6. **Heatmap = corridor markers recolored by slider**, not a raster overlay - smooth, no extra tile dependency, tooltips show ETA-risk vs +Nh-risk. A true raster/contour heat layer can be added later.
7. **No DB models.** The app is a stateless planner over third-party APIs; persistence would add nothing for the assessment. Adding trip history = one model + one view, no refactor needed.
8. **API docs from code.** drf-spectacular generates the OpenAPI schema from the serializers and `@extend_schema` annotations, so `/api/docs/` never drifts from the implementation. `test_docs.py` fails the build if an endpoint drops out of the schema.
