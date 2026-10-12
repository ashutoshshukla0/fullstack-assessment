import { memo } from "react";
import type { TripRoute } from "../lib/types";
import { RISK_COLORS, formatDuration } from "../lib/types";
import { Badge, Card } from "./ui/primitives";
import { cn } from "./ui/primitives";

function RouteSummaryInner({
  routes,
  selectedId,
  onSelect,
  suggestId,
  suggestHour,
}: {
  routes: TripRoute[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  suggestId: string | null;
  suggestHour: number;
}) {
  return (
    <div className="grid gap-3">
      {routes.map((r) => {
        const selected = r.id === selectedId;
        return (
          <button
            key={r.id}
            onClick={() => onSelect(r.id)}
            aria-pressed={selected}
            aria-current={selected ? "true" : undefined}
            className="rounded-xl text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700"
          >
            <Card
              className={cn(
                "p-4 transition",
                selected ? "ring-2 ring-teal-700" : "hover:shadow",
                r.recommended ? "border-teal-700" : ""
              )}
            >
              <div className="flex items-center justify-between">
                <div className="font-semibold">
                  {r.rank}. {r.label}{" "}
                  {r.recommended && <Badge color="#0d9488">Recommended</Badge>}{" "}
                  {suggestId && r.id === suggestId && (
                    <Badge color="#7c3aed">Suggested for +{suggestHour}h</Badge>
                  )}
                </div>
                <div className="text-sm text-slate-600">
                  {r.summary.total_miles} mi · {formatDuration(r.summary.duration_s)} · avg risk {r.summary.avg_risk}
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {Object.entries(r.summary.miles_by_risk).map(([level, miles]) => (
                  <Badge key={level} color={RISK_COLORS[level as keyof typeof RISK_COLORS]}>
                    {level}: {miles} mi
                  </Badge>
                ))}
              </div>
            </Card>
          </button>
        );
      })}
    </div>
  );
}

export const RouteSummary = memo(RouteSummaryInner);
