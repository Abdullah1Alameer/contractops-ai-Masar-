"use client";

import { motion, useReducedMotion } from "framer-motion";

import { SEQUENTIAL } from "@/components/charts/palette";
import { useI18n } from "@/lib/i18n";
import { cn, formatNum } from "@/lib/utils";

export type BarRow = { label: string; value: number; hint?: string };

/**
 * Horizontal magnitude comparison.
 *
 * Horizontal because the category names are long Arabic phrases — rotated or
 * truncated column labels are the most common way a bar chart becomes
 * unreadable. Sequential single hue (more is darker), because the job here is
 * magnitude, not identity: the bars are one measure, not five series.
 *
 * The track and fill both start at the inline-start edge, so the chart grows
 * from the correct side under RTL with no mirrored variant.
 */
export default function BarList({
  rows,
  className,
  maxRows,
}: {
  rows: BarRow[];
  className?: string;
  maxRows?: number;
}) {
  const { lang } = useI18n();
  const reduce = useReducedMotion();

  const shown = maxRows ? rows.slice(0, maxRows) : rows;
  const max = Math.max(...shown.map((r) => r.value), 1);

  return (
    <ul className={cn("space-y-3.5", className)}>
      {shown.map((r, i) => {
        const frac = r.value / max;
        // Darker with magnitude; the floor keeps an empty-ish bar visible.
        const step = SEQUENTIAL[Math.min(SEQUENTIAL.length - 1, Math.max(1, Math.round(frac * (SEQUENTIAL.length - 1))))];

        return (
          <li key={r.label}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate text-xs font-semibold text-slate-600">{r.label}</span>
              <span className="tnum shrink-0 text-xs font-bold text-slate-900">
                {formatNum(r.value, lang)}
                {r.hint ? <span className="ms-1.5 font-medium text-slate-400">{r.hint}</span> : null}
              </span>
            </div>
            <div className="mt-1.5 h-2.5 overflow-hidden rounded-full bg-slate-100">
              <motion.div
                initial={reduce ? false : { width: 0 }}
                whileInView={{ width: `${Math.max(frac * 100, r.value > 0 ? 4 : 0)}%` }}
                viewport={{ once: true }}
                transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.05 + i * 0.05 }}
                // 4px rounded data-end, anchored flat against the baseline.
                className="h-full rounded-e-[4px]"
                style={{ backgroundColor: step }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
