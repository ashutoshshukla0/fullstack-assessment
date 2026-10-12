import { describe, expect, it } from "vitest";
import { forecastRiskAt, suggestForHour } from "./lib/forecast";
import type { RiskLabel, TripRoute } from "./lib/types";

function makeRoute(
  id: string,
  hourlyRisks: RiskLabel[][],
  opts?: { rank?: number; duration?: number; etaRisk?: RiskLabel }
): TripRoute {
  const rank = opts?.rank ?? 1;
  const duration = opts?.duration ?? 3600;
  const etaRisk = opts?.etaRisk ?? "Low";
  return {
    id,
    label: id,
    rank,
    recommended: false,
    coordinates: [[0, 0]],
    summary: { total_miles: 100, duration_s: duration, avg_risk: 0, miles_by_risk: {} },
    checkpoints: hourlyRisks.map((_, i) => ({
      index: i,
      lat: 0,
      lon: i,
      miles_from_origin: i * 10,
      eta: "2026-01-01T08:00:00+00:00",
      wind_mph: 10,
      rain_in_hr: 0,
      snow_in_hr: 0,
      precip_prob_pct: 0,
      risk: etaRisk,
      risk_value: 0,
      risks: {},
    })),
    corridor_forecast: hourlyRisks.map((hourly, i) => ({
      checkpoint_index: i,
      hourly: hourly.map((risk, h) => ({
        hour_offset: h,
        time: "2026-01-01T08:00:00+00:00",
        wind_mph: 10,
        rain_in_hr: 0,
        snow_in_hr: 0,
        precip_prob_pct: 0,
        risk,
      })),
    })),
  };
}

describe("suggestForHour", () => {
  it("prefers the route calmer at the applied hour", () => {
    const stormy = makeRoute("a", [["Low", "Severe", "Low"]]);
    const calm = makeRoute("b", [["Low", "Low", "Low"]]);
    expect(suggestForHour([stormy, calm], 1)).toBe("b");
    // At hour 0 both are calm; shorter duration wins.
    const slow = makeRoute("c", [["Low", "Low", "Low"]], { duration: 7200 });
    expect(suggestForHour([calm, slow], 0)).toBe("b");
  });

  it("weights No Travel above Severe", () => {
    const noTravel = makeRoute("a", [["No Travel"]]);
    const severe = makeRoute("b", [["Severe", "Severe", "Severe"]]);
    expect(suggestForHour([severe, noTravel], 0)).toBe("b");
  });

  it("clamps hours beyond the series length", () => {
    const a = makeRoute("a", [["Low", "Severe"]]);
    const b = makeRoute("b", [["Low", "Low"]]);
    expect(suggestForHour([a, b], 48)).toBe("b");
  });

  it("falls back to ETA risk when the corridor series is empty", () => {
    const a = makeRoute("a", [[]], { etaRisk: "Severe" });
    const b = makeRoute("b", [[]], { etaRisk: "Low" });
    expect(suggestForHour([a, b], 5)).toBe("b");
  });

  it("breaks ties by ETA rank, then returns null when empty", () => {
    const a = makeRoute("a", [["Low"]], { rank: 2 });
    const b = makeRoute("b", [["Low"]], { rank: 1 });
    expect(suggestForHour([a, b], 0)).toBe("b");
    expect(suggestForHour([], 0)).toBeNull();
  });
});

describe("forecastRiskAt", () => {
  const corridor = makeRoute("a", [["Low", "High", "Severe"]]).corridor_forecast;

  it("reads the risk at the requested hour", () => {
    expect(forecastRiskAt(corridor, 0, 1, "Low")).toBe("High");
  });

  it("clamps hours beyond the series length", () => {
    expect(forecastRiskAt(corridor, 0, 48, "Low")).toBe("Severe");
  });

  it("falls back for missing or empty series", () => {
    expect(forecastRiskAt([], 0, 3, "Moderate")).toBe("Moderate");
    expect(forecastRiskAt(makeRoute("b", [[]]).corridor_forecast, 0, 3, "High")).toBe(
      "High"
    );
  });
});
