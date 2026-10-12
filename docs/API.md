# API

Base: `http://localhost:8000`

> Interactive docs: Swagger UI at `GET /api/docs/`, raw OpenAPI schema at
> `GET /api/schema/`, ReDoc at `GET /api/redoc/` (via drf-spectacular).

## `GET /api/health/` → `{"status": "ok"}`

## `POST /api/trips/plan/`

Request:

```json
{
  "origin": "Chicago, IL",
  "destination": "Indianapolis, IN",
  "departure": "2026-01-01T08:00:00Z",
  "load_lbs": 35000,
  "interval_miles": 25
}
```

- `departure`: ISO 8601 with timezone required (e.g. `...+00:00` or `Z`); naive input is rejected with 400. Must fall within 2d past / 4d future (Open-Meteo `past_days=1` + `forecast_days=3` window).
- `interval_miles` (optional 1–200): checkpoint spacing. Omit → auto (≤150mi→10, ≤500mi→25, else 50; exact 150/500 take the lower band).

Response `200`:

```json
{
  "recommended_route_id": "route-1",
  "blocked": false,
  "routes": [
    {
      "id": "route-1",
      "label": "Route 1",
      "rank": 1,
      "recommended": true,
      "blocked": false,
      "origin": { "lat": 41.88, "lon": -87.62 },
      "destination": { "lat": 39.76, "lon": -86.15 },
      "coordinates": [[-87.62, 41.88], ["...", "..."]],
      "summary": {
        "total_miles": 180.7,
        "duration_s": 13007,
        "avg_risk": 0.0,
        "miles_by_risk": { "Low": 180.7, "Moderate": 0, "High": 0, "Severe": 0, "No Travel": 0 }
      },
      "checkpoints": [
        {
          "index": 0, "lat": 41.87556, "lon": -87.62435, "miles_from_origin": 0,
          "eta": "2026-01-01T08:00:00+00:00",
          "wind_mph": 8.3, "rain_in_hr": 0.0, "snow_in_hr": 0.0, "precip_prob_pct": 5,
          "risks": { "wind_risk": "Low", "rain_risk": "Low", "snow_risk": "Low", "overall": "Low" },
          "risk": "Low", "risk_value": 0, "weather_degraded": false
        }
      ],
      "corridor_forecast": [
        {
          "checkpoint_index": 0,
          "hourly": [
            { "hour_offset": 0, "time": "...", "wind_mph": 8.3, "rain_in_hr": 0, "snow_in_hr": 0, "precip_prob_pct": 5, "risk": "Low" }
          ]
        }
      ],
      "corridor_degraded": false
    }
  ]
}
```

Notes: `coordinates` are decimated to ≤500 points for payload size. `recommended_route_id` is `null` with `blocked: true` when every route has No-Travel miles. A checkpoint with `weather_degraded: true` fell back to calm zeros after a weather failure (trip still completes). Corridor hours start at each checkpoint's ETA (not departure).

Errors: `400` validation (incl. naive departure, out-of-window departure, origin==destination) · `422` ungeocodable/no routes · `502` upstream provider failure (`{detail}` generic) · `500` internal error.

## `GET /api/forecast/corridor/?lat=..&lon=..&hours=48&load_lbs=35000`

Standalone 0–72h risk series for one point (heatmap helper). Response `{lat, lon, hourly[]}` with same per-hour shape.

Errors: `400` on missing/invalid `lat` (-90..90), `lon` (-180..180), `hours` (0..72), `load_lbs` (0..200000) · `502` on upstream failure.

## `GET /api/geocode/autocomplete/?q=Chica&limit=5`

Open-source location autocomplete (OpenStreetMap Nominatim, proxied so the
server `User-Agent` satisfies usage policy). Used by the origin/destination
dropdowns - 300 ms debounced, keyboard navigable (↑/↓/Enter/Esc), free text kept submittable.

```json
{
  "query": "Chica",
  "suggestions": [{ "display_name": "Chicago, Illinois, USA", "lat": 41.88, "lon": -87.62 }]
}
```

Errors: `400` when `q` is missing/shorter than 2 chars · `502` on upstream failure · `500` on internal error.
