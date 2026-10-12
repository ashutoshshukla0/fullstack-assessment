import { memo, useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import {
  CircleMarker,
  MapContainer,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";
import "leaflet.heat";
import "leaflet/dist/leaflet.css";
import type { RiskLabel, TripRoute } from "../lib/types";
import { RISK_COLORS } from "../lib/types";

// Responsive height: smaller on phones, full on desktop.
export const MAP_HEIGHT_CLASS = "h-[50vh] md:h-[560px]";

const ROUTE_STYLES = ["#0e3a45", "#7c3aed", "#0d9488"];

const RISK_INTENSITY: Record<RiskLabel, number> = {
  Low: 0.15,
  Moderate: 0.4,
  High: 0.6,
  Severe: 0.85,
  "No Travel": 1.0,
};

const RISK_GRADIENT: Record<string, string> = {
  "0.0": "#22c55e",
  "0.4": "#eab308",
  "0.6": "#f97316",
  "0.85": "#ef4444",
  "1.0": "#7f1d1d",
};

function FitBounds({ routes, selectedId }: { routes: TripRoute[]; selectedId: string | null }) {
  const map = useMap();
  const key = useMemo(() => {
    const r = routes.find((x) => x.id === selectedId) ?? routes[0];
    if (!r) return "";
    return r.coordinates.map((c) => c.join(",")).join("|");
  }, [routes, selectedId]);
  useEffect(() => {
    const r = routes.find((x) => x.id === selectedId) ?? routes[0];
    if (!r || !r.coordinates.length) return;
    const bounds = L.latLngBounds(r.coordinates.map(([lon, lat]) => [lat, lon] as [number, number]));
    map.fitBounds(bounds.pad(0.1), { animate: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key]);
  return null;
}

function HeatLayer({ points }: { points: Array<[number, number, number]> }) {
  const map = useMap();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const layerRef = useRef<any | null>(null);
  useEffect(() => {
    if (!layerRef.current) {
      layerRef.current = L.heatLayer([], {
        radius: 28,
        blur: 22,
        maxZoom: 10,
        minOpacity: 0.35,
        gradient: RISK_GRADIENT,
      });
      layerRef.current.addTo(map);
    }
    layerRef.current.setLatLngs(points);
  }, [map, points]);
  useEffect(
    () => () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
    },
    [map]
  );
  return null;
}

function RouteMapInner({
  routes,
  selectedId,
  forecastHour,
  onSelect,
}: {
  routes: TripRoute[];
  selectedId: string | null;
  forecastHour: number;
  onSelect: (id: string) => void;
}) {
  // Lat/lon coords memoized so slider ticks don't reallocate geometries.
  const latLonRoutes = useMemo(
    () =>
      routes.map((r) => ({
        id: r.id,
        coords: r.coordinates.map(([lon, lat]) => [lat, lon] as [number, number]),
      })),
    [routes]
  );

  // O(1) corridor lookup per route: checkpoint_index -> hourly array.
  const corridorByRoute = useMemo(() => {
    const m = new Map<string, Map<number, TripRoute["corridor_forecast"][number]["hourly"]>>();
    for (const r of routes) {
      const inner = new Map<number, TripRoute["corridor_forecast"][number]["hourly"]>();
      for (const c of r.corridor_forecast) inner.set(c.checkpoint_index, c.hourly);
      m.set(r.id, inner);
    }
    return m;
  }, [routes]);

  const visibleRoutes = useMemo(
    () => routes.filter((r) => !selectedId || r.id === selectedId),
    [routes, selectedId]
  );

  const markers = useMemo(
    () =>
      visibleRoutes.flatMap((r) => {
        const lookup = corridorByRoute.get(r.id);
        return r.checkpoints.map((cp) => {
          const hourly = lookup?.get(cp.index) ?? [];
          const h =
            hourly.length > 0
              ? hourly[Math.max(0, Math.min(forecastHour, hourly.length - 1))]
              : undefined;
          const risk = h?.risk ?? cp.risk;
          const etaText = new Date(cp.eta).toLocaleString();
          return { route: r, cp, hourRisk: h, risk, fill: RISK_COLORS[risk], etaText };
        });
      }),
    [visibleRoutes, corridorByRoute, forecastHour]
  );

  const heatPoints = useMemo<Array<[number, number, number]>>(
    () =>
      markers.map((m) => [
        m.cp.lat,
        m.cp.lon,
        RISK_INTENSITY[m.risk as RiskLabel] ?? 0.3,
      ]),
    [markers]
  );

  const pathOptionsByRoute = useMemo(() => {
    const m = new Map<string, L.PathOptions>();
    routes.forEach((r, ri) => {
      const dimmed = !!selectedId && r.id !== selectedId;
      m.set(r.id, {
        color: ROUTE_STYLES[ri % ROUTE_STYLES.length],
        weight: r.recommended ? 6 : 4,
        opacity: dimmed ? 0.35 : 0.95,
      });
    });
    return m;
  }, [routes, selectedId]);

  const initialCenter = useMemo<[number, number]>(() => {
    const r = routes.find((x) => x.id === selectedId) ?? routes[0];
    if (!r || !r.coordinates.length) return [41.88, -87.62];
    const mid = r.coordinates[Math.floor(r.coordinates.length / 2)];
    return [mid[1], mid[0]];
  }, [routes, selectedId]);

  if (!routes.length) {
    return (
      <div
        className={`flex items-center justify-center rounded-xl border bg-white text-sm text-slate-500 ${MAP_HEIGHT_CLASS}`}
      >
        Plan a trip to see routes.
      </div>
    );
  }

  return (
    <MapContainer
      center={initialCenter}
      zoom={7}
      className={MAP_HEIGHT_CLASS}
      style={{ width: "100%" }}
      preferCanvas
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        maxZoom={19}
        detectRetina
      />
      <FitBounds routes={routes} selectedId={selectedId} />
      <HeatLayer points={heatPoints} />
      {latLonRoutes.map((r) => (
        <Polyline
          key={r.id}
          positions={r.coords}
          pathOptions={pathOptionsByRoute.get(r.id)}
          eventHandlers={{ click: () => onSelect(r.id) }}
        />
      ))}
      {markers.map(({ route, cp, hourRisk, risk, fill, etaText }) => (
        <CircleMarker
          key={`${route.id}-${cp.index}`}
          center={[cp.lat, cp.lon]}
          radius={risk === "No Travel" || risk === "Severe" ? 9 : 6}
          pathOptions={{ color: "#0f172a", weight: 1.5, fillColor: fill, fillOpacity: 0.9 }}
        >
          <Tooltip>
            <b>
              {route.label} · mi {cp.miles_from_origin}
            </b>
            <br />
            ETA: {etaText}
            <br />
            ETA risk: {cp.risk} · wind {cp.wind_mph} mph · rain {cp.rain_in_hr}{" "}
            in/hr · snow {cp.snow_in_hr} in/hr · precip {cp.precip_prob_pct ?? 0}%
            <br />+{forecastHour}h forecast: {hourRisk?.risk ?? "—"}
            {hourRisk && (
              <>
                {" "}· rain {hourRisk.rain_in_hr} in/hr · precip{" "}
                {hourRisk.precip_prob_pct ?? 0}%
              </>
            )}
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}

export const RouteMap = memo(RouteMapInner);
