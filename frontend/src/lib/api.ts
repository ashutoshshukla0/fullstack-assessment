import type { TripPlanResponse } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "";
const REQUEST_TIMEOUT_MS = 30_000;

export interface PlanTripInput {
  origin: string;
  destination: string;
  departure: string;
  load_lbs: number;
  interval_miles?: number;
}

export interface LocationSuggestion {
  display_name: string;
  lat: number;
  lon: number;
}

/** Typed error carrying the HTTP status for the UI to render. */
export class ApiError extends Error {
  readonly status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), REQUEST_TIMEOUT_MS);
  // Allow callers (e.g. autocomplete) to cancel; otherwise use our timeout.
  const signal = init?.signal ?? ctrl.signal;
  try {
    const res = await fetch(url, { ...init, signal });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const detail = (body as { detail?: string }).detail;
      throw new ApiError(detail ?? `Request failed (${res.status})`, res.status);
    }
    return (await res.json()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new ApiError("Request timed out or was cancelled");
    }
    throw e instanceof Error ? e : new ApiError("Request failed");
  } finally {
    clearTimeout(timer);
  }
}

export function planTrip(input: PlanTripInput): Promise<TripPlanResponse> {
  return requestJson<TripPlanResponse>(`${BASE}/api/trips/plan/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function buildAutocompleteUrl(query: string, limit = 5): string {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return `${BASE}/api/geocode/autocomplete/?${params.toString()}`;
}

export async function searchLocations(
  query: string,
  limit = 5,
  signal?: AbortSignal
): Promise<LocationSuggestion[]> {
  try {
    const body = await requestJson<{ suggestions?: LocationSuggestion[] }>(
      buildAutocompleteUrl(query, limit),
      { signal }
    );
    return body.suggestions ?? [];
  } catch (e) {
    // Swallow caller-side aborts (stale keystrokes); surface real failures.
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    if (e instanceof ApiError && e.message.includes("cancelled")) throw e;
    throw e instanceof ApiError
      ? new ApiError(`Location search failed${e.status ? ` (${e.status})` : ""}: ${e.message}`, e.status)
      : e;
  }
}
