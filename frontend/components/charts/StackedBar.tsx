"use client";

import { motion, useReducedMotion } from "framer-motion";

import { CATEGORICAL } from "@/components/charts/palette";
import { useI18n } from "@/lib/i18n";
import { cn, formatNum } from "@/lib/utils";

export type Segment = { label: string; value: number };

/**
 * Part-to-whole for a single total, laid out as one horizontal bar.
 *
 * A 2px surface gap sits between segments rather than a stroke, so adjacent
 * fills stay distinct without an outline. Segments are legended and valued
 * below, so a reader never has to decode a colour to get a number.
 */
export default function StackedBar({
  segments,
  className,
}: {
  segments: Segment[];
  className?: string;
}) {
  const { lang } = useI18n();
  const reduce = useReducedMotion();

  const total = segments.reduce((s, d) => s + d.value, 0);

  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex h-3.5 gap-0.5 overflow-hidden rounded-full bg-slate-100">
        {total === 0 ? (
          <div className="h-full w-full rounded-full bg-slate-100" />
        ) : (
          segments.map((s, i) =>
            s.value > 0 ? (
              <motion.div
                key={s.label}
                initial={reduce ? false : { width: 0 }}
                whileInView={{ width: `${(s.value / total) * 100}%` }}
                viewport={{ once: true }}
                transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.1 + i * 0.08 }}
                className="h-full first:rounded-s-full last:rounded-e-full"
                style={{ backgroundColor: CATEGORICAL[i % CATEGORICAL.length] }}
              />
            ) : null,
          )
        )}
      </div>

      <ul className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
        {segments.map((s, i) => (
          <li key={s.label} className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: CATEGORICAL[i % CATEGORICAL.length] }}
              aria-hidden
            />
            <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-slate-600">{s.label}</span>
            <span className="tnum text-[11px] font-bold text-slate-900">{formatNum(s.value, lang)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
