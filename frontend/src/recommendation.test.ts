import { describe, expect, it } from "vitest";
import { suggestForHour } from "./lib/forecast";
import type { TripRoute } from "./lib/types";

function makeRoute(id: string, risks: string[], rank = 1, duration = 100): TripRoute {
  return {
    id,
    label: id,
    rank,
    recommended: false,
    coordinates: [[0, 0]],
    summary: { total_miles: 10, duration_s: duration, avg_risk: 0, miles_by_risk: {} },
    checkpoints: risks.map((risk, i) => ({
      index: i,
      lat: 0,
      lon: i,
      miles_from_origin: i * 10,
      eta: new Date().toISOString(),
      wind_mph: 10,
      rain_in_hr: 0,
      snow_in_hr: 0,
      precip_prob_pct: 0,
      risk: risk as TripRoute["checkpoints"][number]["risk"],
      risk_value: 0,
      risks: {},
    })),
    corridor_forecast: risks.map((risk, i) => ({
      checkpoint_index: i,
      hourly: [
        {
          hour_offset: 0,
          time: new Date().toISOString(),
          wind_mph: 10,
          rain_in_hr: 0,
          snow_in_hr: 0,
          precip_prob_pct: 0,
          risk: risk as TripRoute["checkpoints"][number]["risk"],
        },
      ],
    })),
  };
}

describe("route recommendation (production suggestForHour)", () => {
  it("prefers fewest severe segments", () => {
    const a = makeRoute("a", ["Severe", "Severe"]);
    const b = makeRoute("b", ["Low", "Low"]);
    expect(suggestForHour([a, b], 0)).toBe("b");
  });

  it("compares numerically, not lexicographically (50 vs 5)", async () => {
    const { formatDuration } = await import("./lib/types");
    expect(formatDuration(5400)).toBe("1h 30m");
    const many = makeRoute("many", Array(50).fill("High"));
    const few = makeRoute("few", Array(5).fill("High"));
    // Fewer High segments must win regardless of string ordering.
    expect(suggestForHour([many, few], 0)).toBe("few");
  });
});
