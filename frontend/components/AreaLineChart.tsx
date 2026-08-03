"use client";
// Single-series time series (area + line). A single series needs no legend —
// the card title already names it. The line draws itself in left-to-right on
// mount; hover snaps a crosshair to the nearest month and lifts that point.
// Kept LTR internally (dir="ltr") so time still reads left-to-right inside an
// RTL page, the same convention as formatSAR/DualDate for numeric content.
import { useEffect, useId, useState } from "react";

import { niceCeil } from "@/lib/chartMath";

export interface TimeSeriesPoint {
  key: string;
  label: string;
  value: number;
}

const W = 620;
const H = 240;
const PAD_L = 34;
const PAD_R = 14;
const PAD_T = 22;
const PAD_B = 28;
const INNER_W = W - PAD_L - PAD_R;
const INNER_H = H - PAD_T - PAD_B;

export default function AreaLineChart({ data, color }: { data: TimeSeriesPoint[]; color: string }) {
  const [grown, setGrown] = useState(false);
  const [active, setActive] = useState<number | null>(null);
  const clipId = useId();
  const gradId = useId();

  useEffect(() => {
    const id = requestAnimationFrame(() => setGrown(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const n = data.length;
  const yMax = niceCeil(Math.max(...data.map((d) => d.value)));
  const x = (i: number) => (n <= 1 ? PAD_L + INNER_W / 2 : PAD_L + (INNER_W * i) / (n - 1));
  const y = (v: number) => PAD_T + INNER_H * (1 - v / yMax);
  const baseline = PAD_T + INNER_H;

  const line = data.map((d, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(d.value)}`).join(" ");
  const area = `${line} L ${x(n - 1)} ${baseline} L ${x(0)} ${baseline} Z`;
  const ticks = [0, yMax / 2, yMax];
  const activePoint = active != null ? data[active] : null;

  return (
    <div dir="ltr" className="relative">
      {activePoint && (
        <div className="pointer-events-none absolute end-0 top-0 rounded-sm bg-oceanic px-2 py-1 text-xs font-medium text-white shadow">
          <span className="font-semibold">{activePoint.value}</span> · {activePoint.label}
        </div>
      )}

      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto" }}>
        <defs>
          <clipPath id={clipId}>
            <rect
              x={0}
              y={0}
              height={H}
              width={grown ? W : 0}
              style={{ transition: "width 1200ms cubic-bezier(0.33,1,0.68,1)" }}
            />
          </clipPath>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.28} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>

        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD_L} x2={W - PAD_R} y1={y(t)} y2={y(t)} stroke="#EAEFEC" strokeWidth={1} />
            <text x={PAD_L - 8} y={y(t)} textAnchor="end" dominantBaseline="middle" className="fill-gray-400 text-[10px]">
              {Math.round(t)}
            </text>
          </g>
        ))}

        {active != null && (
          <line x1={x(active)} x2={x(active)} y1={PAD_T} y2={baseline} stroke="#C3CFC9" strokeWidth={1} />
        )}

        <g clipPath={`url(#${clipId})`}>
          <path d={area} fill={`url(#${gradId})`} />
          <path d={line} fill="none" stroke={color} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" />
          {data.map((d, i) => (
            <circle
              key={d.key}
              cx={x(i)}
              cy={y(d.value)}
              r={active === i ? 6 : 3.5}
              fill={active === i ? color : "#fff"}
              stroke={color}
              strokeWidth={2}
              style={{ transition: "r 160ms ease-out, fill 160ms" }}
            />
          ))}
        </g>

        {activePoint && (
          <text
            x={x(active!)}
            y={y(activePoint.value) - 14}
            textAnchor="middle"
            className="fill-oceanic text-[10px] font-bold"
          >
            {activePoint.value}
          </text>
        )}

        <line x1={PAD_L} x2={W - PAD_R} y1={baseline} y2={baseline} stroke="#C3CFC9" strokeWidth={1} />

        {data.map((d, i) => (
          <text key={d.key} x={x(i)} y={H - 8} textAnchor="middle" className="fill-gray-400 text-[10px]">
            {d.label}
          </text>
        ))}

        {data.map((d, i) => (
          <rect
            key={d.key}
            x={x(i) - INNER_W / n / 2}
            y={0}
            width={INNER_W / n}
            height={H}
            fill="transparent"
            tabIndex={0}
            role="img"
            aria-label={`${d.label}: ${d.value}`}
            className="cursor-pointer outline-none"
            onMouseEnter={() => setActive(i)}
            onMouseLeave={() => setActive(null)}
            onFocus={() => setActive(i)}
            onBlur={() => setActive(null)}
          />
        ))}
      </svg>
    </div>
  );
}
