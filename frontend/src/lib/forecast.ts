import type { RiskLabel, TripRoute } from "./types";
import { RISK_VALUES } from "./types";

/**
 * Forecast risk for one checkpoint at `hour`, falling back to `fallback`
 * (the ETA risk) when its corridor series is missing or empty.
 */
export function forecastRiskAt(
  corridor: TripRoute["corridor_forecast"],
  checkpointIndex: number,
  hour: number,
  fallback: RiskLabel
): RiskLabel {
  const hourly =
    corridor.find((c) => c.checkpoint_index === checkpointIndex)?.hourly ?? [];
  if (!hourly.length) return fallback;
  return hourly[Math.max(0, Math.min(hour, hourly.length - 1))].risk;
}

/**
 * Pick the best route for a corridor-forecast hour offset.
 *
 * Mirrors the backend ranking (fewest No Travel → Severe → High → lowest
 * average → shortest duration → best ETA rank), but scores each checkpoint
 * at `hour` instead of at its ETA. Falls back to the checkpoint's ETA risk
 * when its corridor series is missing or empty.
 */
export function suggestForHour(routes: TripRoute[], hour: number): string | null {
  if (!routes.length) return null;
  const scored = routes.map((r) => {
    const lookup = new Map(
      r.corridor_forecast.map((c) => [c.checkpoint_index, c.hourly] as const)
    );
    let noTravel = 0;
    let severe = 0;
    let high = 0;
    let sum = 0;
    let n = 0;
    for (const cp of r.checkpoints) {
      const hourly = lookup.get(cp.index) ?? [];
      const risk: RiskLabel =
        hourly.length > 0
          ? hourly[Math.max(0, Math.min(hour, hourly.length - 1))].risk
          : cp.risk;
      if (risk === "No Travel") noTravel += 1;
      else if (risk === "Severe") severe += 1;
      else if (risk === "High") high += 1;
      sum += RISK_VALUES[risk] ?? 0;
      n += 1;
    }
    return {
      id: r.id,
      key: [
        noTravel,
        severe,
        high,
        n > 0 ? sum / n : 0,
        r.summary.duration_s,
        r.rank,
      ],
    };
  });
  scored.sort((a, b) => {
    for (let i = 0; i < a.key.length; i++) {
      if (a.key[i] !== b.key[i]) return a.key[i] - b.key[i];
    }
    return 0;
  });
  return scored[0].id;
}
