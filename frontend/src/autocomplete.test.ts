import { describe, expect, it, vi } from "vitest";
import { buildAutocompleteUrl, searchLocations } from "./lib/api";

describe("location autocomplete client", () => {
  it("builds the proxied Nominatim URL", () => {
    expect(buildAutocompleteUrl("Chica", 5)).toBe("/api/geocode/autocomplete/?q=Chica&limit=5");
  });

  it("returns suggestions from the API", async () => {
    const payload = { suggestions: [{ display_name: "Chicago, Illinois, USA", lat: 41.88, lon: -87.62 }] };
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => payload }) as Response));
    const out = await searchLocations("Chica");
    expect(out).toEqual(payload.suggestions);
    vi.unstubAllGlobals();
  });

  it("throws on API error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 502, json: async () => ({}) }) as Response));
    await expect(searchLocations("Chicago")).rejects.toThrow("502");
    vi.unstubAllGlobals();
  });
});
