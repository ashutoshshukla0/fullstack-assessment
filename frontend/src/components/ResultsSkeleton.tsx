import { memo } from "react";
import { MAP_HEIGHT_CLASS } from "./RouteMap";
import { Card } from "./ui/primitives";

const TABLE_ROWS = 6;

function ResultsSkeletonInner() {
  return (
    <div
      role="status"
      aria-busy="true"
      aria-label="Planning routes"
      className="grid animate-pulse gap-4"
    >
      <span className="sr-only">Planning routes…</span>
      {/* Forecast slider placeholder */}
      <Card className="p-4" aria-hidden="true">
        <div className="mb-3 h-5 w-2/3 rounded bg-slate-200" />
        <div className="h-2 w-full rounded-full bg-slate-200" />
      </Card>
      {/* Map placeholder */}
      <div
        className={`rounded-xl border bg-slate-100 ${MAP_HEIGHT_CLASS}`}
        aria-hidden="true"
      >
        <div className="flex h-full items-center justify-center">
          <div className="h-8 w-8 rounded-full border-4 border-slate-200 border-t-teal-700 [animation:spin_1s_linear_infinite]" />
        </div>
      </div>
      {/* Checkpoint table placeholder */}
      <div aria-hidden="true">
        <div className="mb-2 h-5 w-1/2 rounded bg-slate-200" />
        <Card className="overflow-hidden p-0">
          {Array.from({ length: TABLE_ROWS }, (_, i) => (
            <div
              key={i}
              className="h-9 border-b border-slate-100 bg-white last:border-0 odd:bg-slate-50"
            />
          ))}
        </Card>
      </div>
    </div>
  );
}

export const ResultsSkeleton = memo(ResultsSkeletonInner);
