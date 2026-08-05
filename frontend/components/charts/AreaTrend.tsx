"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useId, useState } from "react";

import { INK, STATUS } from "@/components/charts/palette";
import { useI18n } from "@/lib/i18n";
import { cn, formatNum } from "@/lib/utils";

export type TrendPoint = { label: string; value: number };

/**
 * Single-series trend.
 *
 * One series, so it takes the brand hue and needs no legend — the panel title
 * names it. A crosshair plus tooltip is the default interaction for a line, so
 * it ships with one rather than leaving the reader to estimate against the
 * grid. Grid and axis are recessive; only the marks carry weight.
 *
 * The plot is drawn left-to-right in SVG user space but the whole figure is
 * flipped under RTL, so time still reads from the start edge of the writing
 * direction.
 */
export default function AreaTrend({
  points,
  className,
  height = 180,
}: {
  points: TrendPoint[];
  className?: string;
  height?: number;
}) {
  const { lang } = useI18n();
  const reduce = useReducedMotion();
  const gradId = useId().replace(/:/g, "");
  const [hover, setHover] = useState<number | null>(null);

  const W = 320;
  const H = 120;
  const PAD = 8;

  const max = Math.max(...points.map((p) => p.value), 1);
  const stepX = points.length > 1 ? (W - PAD * 2) / (points.length - 1) : 0;
  const x = (i: number) => PAD + i * stepX;
  const y = (v: number) => H - PAD - (v / max) * (H - PAD * 2);

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
  const area = `${line} L${x(points.length - 1).toFixed(1)},${H - PAD} L${x(0).toFixed(1)},${H - PAD} Z`;

  return (
    <div className={cn("w-full", className)}>
      <div className="relative" style={{ height }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          className="h-full w-full rtl:-scale-x-100"
          onMouseLeave={() => setHover(null)}
        >
          <defs>
            <linearGradient id={`area-${gradId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={STATUS.good} stopOpacity="0.28" />
              <stop offset="100%" stopColor={STATUS.good} stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Recessive grid. */}
          {[0.25, 0.5, 0.75].map((f) => (
            <line
              key={f}
              x1={PAD}
              x2={W - PAD}
              y1={PAD + f * (H - PAD * 2)}
              y2={PAD + f * (H - PAD * 2)}
              stroke={INK.grid}
              strokeWidth="0.6"
            />
          ))}

          <motion.path
            d={area}
            fill={`url(#area-${gradId})`}
            initial={reduce ? false : { opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, delay: 0.15 }}
          />
          <motion.path
            d={line}
            fill="none"
            stroke={STATUS.good}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={reduce ? false : { pathLength: 0 }}
            whileInView={{ pathLength: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
            vectorEffect="non-scaling-stroke"
          />

          {/* Crosshair + markers. Hit targets are wider than the marks. */}
          {points.map((p, i) => (
            <g key={p.label}>
              {hover === i && (
                <line x1={x(i)} x2={x(i)} y1={PAD} y2={H - PAD} stroke={INK.axis} strokeWidth="0.8" strokeDasharray="3 3" />
              )}
              <circle
                cx={x(i)}
                cy={y(p.value)}
                r={hover === i ? 4 : 2.5}
                fill={INK.surface}
                stroke={STATUS.good}
                strokeWidth="2"
                vectorEffect="non-scaling-stroke"
                className="transition-[r] duration-150"
              />
              <rect
                x={x(i) - stepX / 2}
                y={0}
                width={Math.max(stepX, 12)}
                height={H}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                className="cursor-pointer"
              />
            </g>
          ))}
        </svg>
      </div>

      {/* Axis labels + readout. Text wears ink tokens, never the series colour. */}
      <div className="mt-2 flex items-center justify-between gap-2 text-[10.5px] font-medium text-slate-400">
        <span>{points[0]?.label}</span>
        {hover != null ? (
          <span className="tnum rounded-full bg-slate-100 px-2 py-0.5 font-bold text-slate-700">
            {points[hover].label} · {formatNum(points[hover].value, lang)}
          </span>
        ) : null}
        <span>{points[points.length - 1]?.label}</span>
      </div>
    </div>
  );
}
