import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { planTrip } from "./lib/api";
import { suggestForHour } from "./lib/forecast";
import type { TripPlanResponse } from "./lib/types";
import { TripForm, type TripFormValues } from "./components/TripForm";
import { RouteMap } from "./components/RouteMap";
import { RouteSummary } from "./components/RouteSummary";
import { CheckpointTable } from "./components/CheckpointTable";
import { ResultsSkeleton } from "./components/ResultsSkeleton";
import { Button, Card, Slider } from "./components/ui/primitives";

export default function App() {
  const [plan, setPlan] = useState<TripPlanResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Slider draft auto-applies after a short debounce so dragging feels live
  // without recoloring the map on every input tick.
  const [draftHour, setDraftHour] = useState(0);
  const [appliedHour, setAppliedHour] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const isDirty = draftHour !== appliedHour;

  useEffect(() => {
    if (!isDirty) return;
    const t = setTimeout(() => setAppliedHour(draftHour), 150);
    return () => clearTimeout(t);
  }, [draftHour, isDirty]);

  const handleSubmit = useCallback(async (v: TripFormValues) => {
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const data = (await planTrip({
        origin: v.origin,
        destination: v.destination,
        departure: v.departure,
        load_lbs: v.load_lbs,
        ...(v.interval_miles ? { interval_miles: v.interval_miles } : {}),
      })) as TripPlanResponse;
      if (id !== requestId.current) return; // stale response; a newer plan won
      if (!data.routes?.length) {
        throw new Error("No routes found for this origin/destination.");
      }
      setPlan(data);
      setSelectedId(data.recommended_route_id ?? data.routes[0]?.id ?? null);
      setDraftHour(0);
      setAppliedHour(0);
    } catch (e) {
      if (id !== requestId.current) return;
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, []);

  const handleSelect = useCallback((id: string) => setSelectedId(id), []);
  const handleHour = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setDraftHour(Number(e.target.value));
  }, []);
  const handleApplyHour = useCallback(() => setAppliedHour(draftHour), [draftHour]);

  const selected = useMemo(
    () => plan?.routes.find((r) => r.id === selectedId) ?? plan?.routes[0],
    [plan, selectedId]
  );

  // Forecast-aware suggestion: re-rank routes at the applied corridor hour.
  // Only shown once the user applies an hour > 0; +0h stays ETA-based.
  const forecastBest = useMemo(
    () => (plan && appliedHour > 0 ? suggestForHour(plan.routes, appliedHour) : null),
    [plan, appliedHour]
  );
  const forecastBestLabel = useMemo(
    () => plan?.routes.find((r) => r.id === forecastBest)?.label ?? null,
    [plan, forecastBest]
  );

  const blockedAll = plan && !plan.recommended_route_id;

  return (
    <div className="min-h-screen bg-background">
      <header className="bg-primary px-6 py-4 text-white">
        <h1 className="text-xl font-bold">Weather-Aware Truck Routing</h1>
        <p className="text-sm text-teal-100">Safest route by weather risk, load weight & travel time · 0–48h corridor heatmap</p>
      </header>
      <main className="mx-auto grid max-w-7xl gap-4 p-4 pb-12 lg:grid-cols-[360px_1fr]">
        <div>
          <TripForm loading={loading} onSubmit={handleSubmit} />
          {error && (
            <Card className="mt-3 border-red-300 p-3 text-sm text-red-700" role="alert">
              {error}
            </Card>
          )}
          {plan && (
            <div className="mt-4">
              <RouteSummary
                routes={plan.routes}
                selectedId={selectedId}
                onSelect={handleSelect}
                suggestId={forecastBest}
                suggestHour={appliedHour}
              />
            </div>
          )}
        </div>
        <div className="grid gap-4">
          {loading && !plan ? (
            <ResultsSkeleton />
          ) : (
            <>
              {blockedAll && (
                <Card className="border-red-300 bg-red-50 p-3 text-sm text-red-800" role="alert">
                  All routes have No-Travel conditions. No route is recommended — delay travel or choose a later departure.
                </Card>
              )}
              {plan && (
                <Card className="p-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <label htmlFor="forecast-slider" className="font-semibold">
                  Weather heatmap — forecast slider: +{draftHour}h
                </label>
                <div className="text-xs text-slate-500">
                  Checkpoint color = corridor risk at +{appliedHour}h · ring tooltip shows ETA risk
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Slider
                  id="forecast-slider"
                  min={0}
                  max={48}
                  step={1}
                  value={draftHour}
                  onChange={handleHour}
                  aria-label={`Corridor forecast offset, ${draftHour} hours`}
                  aria-valuetext={`plus ${draftHour} hours`}
                />
                {isDirty && (
                  <Button
                    type="button"
                    onClick={handleApplyHour}
                    aria-live="polite"
                    className="w-28 shrink-0"
                  >
                    Apply +{draftHour}h
                  </Button>
                )}
              </div>
              <div aria-live="polite" className="mt-1 text-xs text-slate-500">
                {isDirty
                  ? `Previewing +${draftHour}h — applying shortly (showing +${appliedHour}h).`
                  : `Showing +${appliedHour}h forecast.`}
                {forecastBestLabel && ` Suggested for +${appliedHour}h: ${forecastBestLabel}.`}
              </div>
            </Card>
          )}
          {plan && (
            <div className="relative">
              {loading && (
                <div className="absolute inset-0 z-20 flex items-center justify-center rounded-xl bg-white/60 text-sm text-slate-600" aria-busy="true">
                  Re-planning…
                </div>
              )}
              <RouteMap routes={plan.routes} selectedId={selectedId} forecastHour={appliedHour} onSelect={handleSelect} />
            </div>
          )}
          {selected ? (
            <>
              <h2 className="font-semibold">{selected.label} — checkpoints, risk levels & ETAs</h2>
              <CheckpointTable
                checkpoints={selected.checkpoints}
                corridor={selected.corridor_forecast}
                forecastHour={appliedHour}
              />
            </>
          ) : (
            plan && <p className="text-sm text-slate-500">No route data to display.</p>
          )}
            </>
          )}
        </div>
      </main>
      <footer className="border-t border-slate-200 bg-white px-6 py-4 text-center text-xs text-slate-500">
        Routing: OSRM · Geocoding: Nominatim (© OpenStreetMap contributors) · Weather: Open-Meteo
      </footer>
    </div>
  );
}
