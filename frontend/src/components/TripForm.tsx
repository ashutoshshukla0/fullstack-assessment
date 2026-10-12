import { memo, useMemo, useState } from "react";
import { Button, Card, Input, Label } from "./ui/primitives";
import { LocationAutocomplete } from "./LocationAutocomplete";

export interface TripFormValues {
  origin: string;
  destination: string;
  departure: string;
  load_lbs: number;
  interval_miles: number | undefined;
}

export const TripForm = memo(function TripForm({
  loading,
  onSubmit,
}: {
  loading: boolean;
  onSubmit: (v: TripFormValues) => void;
}) {
  const [origin, setOrigin] = useState("Chicago, IL");
  const [destination, setDestination] = useState("Indianapolis, IN");
  const [departure, setDeparture] = useState(() => new Date(Date.now() + 3600e3).toISOString().slice(0, 16));
  const [load, setLoad] = useState(35000);
  const [interval, setInterval] = useState<string>("auto");
  const [formError, setFormError] = useState<string | null>(null);
  const departureId = "trip-departure";
  const loadId = "trip-load";
  const intervalId = "trip-interval";

  const validation = useMemo(() => {
    if (!origin.trim() || !destination.trim()) return "Origin and destination are required.";
    if (origin.trim().toLowerCase() === destination.trim().toLowerCase())
      return "Origin and destination must differ.";
    if (!departure) return "Departure is required.";
    const d = new Date(departure);
    if (Number.isNaN(d.getTime())) return "Departure is invalid.";
    if (d.getTime() < Date.now() - 24 * 3600e3) return "Departure cannot be in the past.";
    if (!Number.isFinite(load)) return "Load weight is required.";
    if (load < 0 || load > 200000) return "Load must be 0–200,000 lbs.";
    return null;
  }, [origin, destination, departure, load]);

  return (
    <Card className="p-4">
      <form
        className="grid gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (validation) {
            setFormError(validation);
            return;
          }
          setFormError(null);
          const d = new Date(departure);
          onSubmit({
            origin: origin.trim(),
            destination: destination.trim(),
            departure: d.toISOString(),
            load_lbs: Number(load),
            interval_miles: interval === "auto" ? undefined : Number(interval),
          });
        }}
      >
        <LocationAutocomplete label="Origin" value={origin} onChange={setOrigin} placeholder="Chicago, IL" />
        <LocationAutocomplete
          label="Destination"
          value={destination}
          onChange={setDestination}
          placeholder="Detroit, MI"
        />
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label htmlFor={departureId}>Departure (local)</Label>
            <Input id={departureId} type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} required />
          </div>
          <div>
            <Label htmlFor={loadId}>Load weight (lbs)</Label>
            <Input
              id={loadId}
              type="number"
              min={0}
              max={200000}
              value={Number.isFinite(load) ? load : ""}
              onChange={(e) => {
                const v = e.target.value;
                setLoad(v === "" ? NaN : Number(v));
              }}
              required
            />
          </div>
        </div>
        <div>
          <Label htmlFor={intervalId}>Checkpoint spacing - 10 / 25 / 50 mi</Label>
          <select id={intervalId} value={interval} onChange={(e) => setInterval(e.target.value)} className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600">
            <option value="auto">Auto (≤150mi→10, ≤500mi→25, else 50)</option>
            <option value="10">Every 10 miles</option>
            <option value="25">Every 25 miles</option>
            <option value="50">Every 50 miles</option>
          </select>
        </div>
        {(formError ?? validation) && (
          <p role="alert" className="text-xs text-red-700">
            {formError ?? validation}
          </p>
        )}
        <Button disabled={loading || !!validation}>{loading ? "Planning…" : "Find safest route"}</Button>
        <p className="text-xs text-slate-500">Routing: OSRM · Geocoding: Nominatim · Weather: Open-Meteo (free, no key).</p>
      </form>
    </Card>
  );
});
