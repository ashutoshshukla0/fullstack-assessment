import * as React from "react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: (string | undefined | false)[]) {
  return twMerge(clsx(inputs));
}

export function Button({ className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-[#15525f] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-700 focus-visible:ring-offset-2",
        className
      )}
      {...props}
    />
  );
}

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border bg-white shadow-sm", className)} {...props} />;
}

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-600 focus:ring-1 focus:ring-teal-600 focus-visible:ring-1 focus-visible:ring-teal-600",
        className
      )}
      {...props}
    />
  );
}

export function Label({ className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={cn("mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500", className)} {...props} />;
}

// Text color adapts for contrast: dark text on yellow (Moderate), white elsewhere.
const LIGHT_BG = new Set(["#eab308", "#22c55e", "#f97316"]);

export function Badge({ color, children }: { color: string; children: React.ReactNode }) {
  const fg = LIGHT_BG.has(color) ? "#0f172a" : "#ffffff";
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold"
      style={{ backgroundColor: color, color: fg }}
    >
      {children}
    </span>
  );
}

export function Slider({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="range"
      className={cn("h-8 w-full cursor-pointer accent-teal-700", className)}
      {...props}
    />
  );
}
