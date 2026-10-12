import { memo, useMemo } from "react";
import type { Checkpoint, TripRoute } from "../lib/types";
import { RISK_COLORS } from "../lib/types";
import { Badge, Card } from "./ui/primitives";

function Row({
  cp,
  forecastRisk,
  etaText,
}: {
  cp: Checkpoint;
  forecastRisk: string;
  etaText: string;
}) {
  return (
    <tr className="border-b last:border-0">
      <td className="px-3 py-1.5 font-medium">{cp.miles_from_origin}</td>
      <td className="px-3 py-1.5">{etaText}</td>
      <td className="px-3 py-1.5">{cp.wind_mph} mph</td>
      <td className="px-3 py-1.5">{cp.rain_in_hr} in/hr</td>
      <td className="px-3 py-1.5">{cp.snow_in_hr} in/hr</td>
      <td className="px-3 py-1.5">{cp.precip_prob_pct ?? 0}%</td>
      <td className="px-3 py-1.5">
        <Badge color={RISK_COLORS[cp.risk]}>{cp.risk}</Badge>
      </td>
      <td className="px-3 py-1.5">
        <Badge color={RISK_COLORS[forecastRisk as keyof typeof RISK_COLORS] ?? "#64748b"}>{forecastRisk}</Badge>
      </td>
    </tr>
  );
}
const MemoRow = memo(Row);

function CheckpointTableInner({
  checkpoints,
  corridor,
  forecastHour,
}: {
  checkpoints: Checkpoint[];
  corridor: TripRoute["corridor_forecast"];
  forecastHour: number;
}) {
  const lookup = useMemo(() => {
    const m = new Map<number, TripRoute["corridor_forecast"][number]["hourly"]>();
    for (const c of corridor) m.set(c.checkpoint_index, c.hourly);
    return m;
  }, [corridor]);

  const rows = useMemo(
    () =>
      checkpoints.map((cp) => {
        const hourly = lookup.get(cp.index) ?? [];
        const forecastRisk = hourly.length
          ? hourly[Math.max(0, Math.min(forecastHour, hourly.length - 1))].risk
          : cp.risk;
        return { cp, forecastRisk, etaText: new Date(cp.eta).toLocaleString() };
      }),
    [checkpoints, lookup, forecastHour]
  );

  if (!checkpoints.length) {
    return (
      <Card className="p-4 text-sm text-slate-500">
        No checkpoints for this route.
      </Card>
    );
  }
  return (
    <Card className="p-0">
      <div className="max-h-[480px] overflow-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">
            Checkpoints with mileage, ETA, weather and risk level
          </caption>
          <thead className="sticky top-0 z-10">
            <tr className="border-b bg-slate-50 text-left text-xs uppercase text-slate-500">
              <th scope="col" className="px-3 py-2">Mi</th>
              <th scope="col" className="px-3 py-2">ETA</th>
              <th scope="col" className="px-3 py-2">Wind</th>
              <th scope="col" className="px-3 py-2">Rain</th>
              <th scope="col" className="px-3 py-2">Snow</th>
              <th scope="col" className="px-3 py-2">Precip</th>
              <th scope="col" className="px-3 py-2">Risk</th>
              <th scope="col" className="px-3 py-2">+{forecastHour}h Risk</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ cp, forecastRisk, etaText }) => (
              <MemoRow key={cp.index} cp={cp} forecastRisk={forecastRisk} etaText={etaText} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export const CheckpointTable = memo(CheckpointTableInner);
