export type RiskLabel = "Low" | "Moderate" | "High" | "Severe" | "No Travel";

const RISK_LABELS: RiskLabel[] = ["Low", "Moderate", "High", "Severe", "No Travel"];

/** Narrow an unknown string to a RiskLabel (backend values are the source of truth). */
export function isRiskLabel(value: unknown): value is RiskLabel {
  return typeof value === "string" && (RISK_LABELS as string[]).includes(value);
}

export interface Checkpoint {
  index: number;
  lat: number;
  lon: number;
  miles_from_origin: number;
  eta: string;
  wind_mph: number;
  rain_in_hr: number;
  snow_in_hr: number;
  precip_prob_pct: number;
  risk: RiskLabel;
  risk_value: number;
  risks: Record<string, string>;
  weather_degraded?: boolean;
}

export interface CorridorHour {
  hour_offset: number;
  time: string;
  wind_mph: number;
  rain_in_hr: number;
  snow_in_hr: number;
  precip_prob_pct: number;
  risk: RiskLabel;
}

export interface TripRoute {
  id: string;
  label: string;
  rank: number;
  recommended: boolean;
  blocked?: boolean;
  coordinates: [number, number][];
  summary: {
    total_miles: number;
    duration_s: number;
    avg_risk: number;
    miles_by_risk: Record<string, number>;
  };
  checkpoints: Checkpoint[];
  corridor_forecast: { checkpoint_index: number; hourly: CorridorHour[] }[];
  corridor_degraded?: boolean;
}

export interface TripPlanResponse {
  recommended_route_id: string | null;
  blocked?: boolean;
  routes: TripRoute[];
}

export const RISK_COLORS: Record<RiskLabel, string> = {
  Low: "#22c55e",
  Moderate: "#eab308",
  High: "#f97316",
  Severe: "#ef4444",
  "No Travel": "#7f1d1d",
};

/** Numeric rank mirroring the backend RiskLevel enum (Low 0 … No Travel 4). */
export const RISK_VALUES: Record<RiskLabel, number> = {
  Low: 0,
  Moderate: 1,
  High: 2,
  Severe: 3,
  "No Travel": 4,
};

export function formatDuration(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.round((totalSeconds % 3600) / 60);
  return `${h}h ${m}m`;
}
