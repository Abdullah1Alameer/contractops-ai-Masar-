"use client";
import { cn } from "@/lib/utils";

/**
 * Tone controls only the icon well and the value colour — never the card
 * surface. Tinting whole cards made every tile shout at equal volume; keeping
 * the glass neutral means a red figure actually reads as an exception.
 */
const tones = {
  default: { well: "bg-slate-100 text-slate-500", value: "text-slate-900" },
  brand: { well: "bg-gradient-to-br from-emerald-50 to-teal-50 text-emerald-600", value: "text-slate-900" },
  success: { well: "bg-gradient-to-br from-emerald-50 to-teal-50 text-emerald-600", value: "text-emerald-700" },
  danger: { well: "bg-gradient-to-br from-rose-50 to-amber-50 text-rose-600", value: "text-rose-600" },
  warning: { well: "bg-gradient-to-br from-amber-50 to-yellow-50 text-amber-600", value: "text-amber-700" },
  info: { well: "bg-gradient-to-br from-sky-50 to-blue-50 text-sky-600", value: "text-slate-900" },
};

export default function Stat({
  label,
  value,
  hint,
  tone = "default",
  className,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: keyof typeof tones;
  className?: string;
  icon?: React.ReactNode;
}) {
  const s = tones[tone];

  return (
    <div className={cn("glass-card glass-card-hover group relative overflow-hidden p-5", className)}>
      <span
        className="pointer-events-none absolute inset-0 bg-gradient-to-t from-emerald-50/70 to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"
        aria-hidden
      />
      <div className="relative flex items-start justify-between gap-2">
        <p className="text-xs font-semibold leading-snug text-slate-500">{label}</p>
        {icon && (
          <span
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl shadow-inner transition-transform duration-300 motion-safe:ease-emphasis group-hover:scale-110",
              s.well,
            )}
          >
            {icon}
          </span>
        )}
      </div>
      <p className={cn("tnum mt-3 text-3xl font-extrabold tracking-tight", s.value)}>{value}</p>
      {hint && <div className="relative mt-2 text-sm text-slate-500">{hint}</div>}
    </div>
  );
}
