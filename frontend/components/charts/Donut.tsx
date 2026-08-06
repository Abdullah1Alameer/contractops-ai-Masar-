"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useId, useState } from "react";

import { CATEGORICAL, INK } from "@/components/charts/palette";
import { useI18n } from "@/lib/i18n";
import { cn, formatNum, formatPercent } from "@/lib/utils";

export type Slice = { label: string; value: number };

/**
 * Part-to-whole donut with a hero figure in the hole.
 *
 * Segments are separated by a 2px surface gap rather than a stroke, so the ring
 * reads as discrete parts without a colour outline competing with the fills.
 * Every segment is also legended and labelled, so identity is never carried by
 * colour alone.
 */
export default function Donut({
  slices,
  centerLabel,
  className,
}: {
  slices: Slice[];
  centerLabel: string;
  className?: string;
}) {
  const { lang } = useI18n();
  const reduce = useReducedMotion();
  const [active, setActive] = useState<number | null>(null);
  const titleId = useId();

  const total = slices.reduce((s, d) => s + d.value, 0);
  const R = 62;
  const C = 2 * Math.PI * R;
  // 2px visual gap between segments, expressed in path length.
  const GAP = 3;

  let offset = 0;
  const arcs = slices.map((s, i) => {
    const frac = total > 0 ? s.value / total : 0;
    const len = Math.max(frac * C - GAP, 0);
    const arc = { ...s, i, len, dashOffset: -offset, frac };
    offset += frac * C;
    return arc;
  });

  return (
    <div className={cn("flex flex-col items-center gap-5 sm:flex-row sm:items-center", className)}>
      <div className="relative grid h-44 w-44 shrink-0 place-items-center">
        <svg viewBox="0 0 160 160" className="h-full w-full -rotate-90" role="img" aria-labelledby={titleId}>
          <title id={titleId}>{centerLabel}</title>
          <circle cx="80" cy="80" r={R} fill="none" stroke={INK.grid} strokeWidth="20" />
          {arcs.map((a) => (
            <motion.circle
              key={a.label}
              cx="80"
              cy="80"
              r={R}
              fill="none"
              stroke={CATEGORICAL[a.i % CATEGORICAL.length]}
              strokeWidth={active === a.i ? 24 : 20}
              strokeDasharray={`${a.len} ${C - a.len}`}
              strokeDashoffset={a.dashOffset}
              initial={reduce ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.1 + a.i * 0.08 }}
              onMouseEnter={() => setActive(a.i)}
              onMouseLeave={() => setActive(null)}
              className="cursor-pointer transition-[stroke-width] duration-200"
            />
          ))}
        </svg>

        {/* Hero figure: the total, or the hovered segment. */}
        <div className="pointer-events-none absolute grid place-items-center text-center">
          <span className="tnum text-3xl font-extrabold leading-none tracking-tight text-slate-900">
            {active == null ? formatNum(total, lang) : formatNum(slices[active].value, lang)}
          </span>
          <span className="mt-1.5 max-w-[6.5rem] text-[11px] font-semibold leading-tight text-slate-500">
            {active == null ? centerLabel : slices[active].label}
          </span>
        </div>
      </div>

      {/* Legend — always present, and it carries the values so the reader never
          has to decode a colour to get a number. */}
      <ul className="min-w-0 flex-1 space-y-2">
        {arcs.map((a) => (
          <li
            key={a.label}
            onMouseEnter={() => setActive(a.i)}
            onMouseLeave={() => setActive(null)}
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors duration-200",
              active === a.i && "bg-slate-50",
            )}
          >
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: CATEGORICAL[a.i % CATEGORICAL.length] }}
              aria-hidden
            />
            <span className="min-w-0 flex-1 truncate text-xs font-medium text-slate-600">{a.label}</span>
            <span className="tnum text-xs font-bold text-slate-900">{formatNum(a.value, lang)}</span>
            <span className="tnum w-10 shrink-0 text-end text-[11px] font-medium text-slate-400">
              {formatPercent(a.frac * 100, lang)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
