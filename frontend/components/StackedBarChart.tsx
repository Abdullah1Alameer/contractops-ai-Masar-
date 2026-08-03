"use client";
// Monthly stacked-bar histogram — part-to-whole over time gets a stacked bar,
// categorical color for the distinct series. Thin bars, 2px surface gaps
// between segments, rounded only on the topmost segment's outer edge.
// Grows from the baseline on mount, stagger per bucket, and the hovered
// column lifts while its neighbours recede.
// Kept LTR (dir="ltr") so months read left-to-right inside an RTL page.
import { useEffect, useState } from "react";

import { niceCeil } from "@/lib/chartMath";

export interface HistogramSeries {
  key: string;
  label: string;
  color: string;
}

export interface HistogramBucket {
  key: string;
  label: string;
  values: Record<string, number>;
}

const W = 620;
const H = 240;
const PAD_L = 34;
const PAD_R = 12;
const PAD_T = 22;
const PAD_B = 28;
const INNER_W = W - PAD_L - PAD_R;
const INNER_H = H - PAD_T - PAD_B;
const GAP = 2;
const BAR_MAX = 26;

export default function StackedBarChart({ buckets, series }: { buckets: HistogramBucket[]; series: HistogramSeries[] }) {
  const [grown, setGrown] = useState(false);
  const [activeBucket, setActiveBucket] = useState<string | null>(null);
  const [activeSeries, setActiveSeries] = useState<string | null>(null);

  useEffect(() => {
    const id = requestAnimationFrame(() => setGrown(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const n = buckets.length;
  const totals = buckets.map((b) => series.reduce((s, ser) => s + (b.values[ser.key] ?? 0), 0));
  const yMax = niceCeil(Math.max(...totals));
  const slot = INNER_W / n;
  const barW = Math.min(BAR_MAX, slot * 0.5);
  const baseline = PAD_T + INNER_H;
  const ticks = [0, yMax / 2, yMax];

  const hovered = buckets.find((b) => b.key === activeBucket);
  const hoveredTotal = hovered ? series.reduce((s, ser) => s + (hovered.values[ser.key] ?? 0), 0) : 0;

  return (
    <div dir="ltr">
      <div className="mb-1 flex flex-wrap items-center gap-x-4 gap-y-1">
        {series.map((s) => (
          <span
            key={s.key}
            className={`inline-flex cursor-pointer items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-xs transition-colors ${
              activeSeries === s.key ? "bg-arctic text-oceanic" : "text-gray-600"
            }`}
            onMouseEnter={() => setActiveSeries(s.key)}
            onMouseLeave={() => setActiveSeries(null)}
          >
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: s.color }} />
            {s.label}
          </span>
        ))}
      </div>

      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto" }}>
          {ticks.map((t) => {
            const ty = PAD_T + INNER_H * (1 - t / yMax);
            return (
              <g key={t}>
                <line x1={PAD_L} x2={W - PAD_R} y1={ty} y2={ty} stroke="#EAEFEC" strokeWidth={1} />
                <text x={PAD_L - 8} y={ty} textAnchor="end" dominantBaseline="middle" className="fill-gray-400 text-[10px]">
                  {Math.round(t)}
                </text>
              </g>
            );
          })}

          {buckets.map((b, bi) => {
            const cx = PAD_L + slot * bi + slot / 2;
            const bucketDim = activeBucket !== null && activeBucket !== b.key;
            const nonZero = series.filter((s) => (b.values[s.key] ?? 0) > 0);
            const bucketTotal = series.reduce((s, ser) => s + (b.values[ser.key] ?? 0), 0);
            let cursor = baseline;

            return (
              <g key={b.key}>
                {activeBucket === b.key && (
                  <rect
                    x={cx - slot / 2}
                    y={PAD_T}
                    width={slot}
                    height={INNER_H}
                    fill="#F1F6F4"
                    style={{ transition: "opacity 150ms" }}
                  />
                )}

                {nonZero.map((s, si) => {
                  const v = b.values[s.key] ?? 0;
                  const hFinal = Math.max((v / yMax) * INNER_H - (si > 0 ? GAP : 0), 0);
                  const yFinal = cursor - hFinal;
                  cursor = yFinal - GAP;
                  const isTop = si === nonZero.length - 1;
                  const seriesDim = activeSeries !== null && activeSeries !== s.key;

                  return (
                    <rect
                      key={s.key}
                      x={cx - barW / 2}
                      y={grown ? yFinal : baseline}
                      width={barW}
                      height={grown ? hFinal : 0}
                      rx={isTop ? 3 : 0}
                      fill={s.color}
                      opacity={bucketDim || seriesDim ? 0.4 : 1}
                      style={{
                        transition:
                          "height 750ms cubic-bezier(0.22,1,0.36,1), y 750ms cubic-bezier(0.22,1,0.36,1), opacity 180ms",
                        transitionDelay: grown ? `${bi * 55}ms` : "0ms",
                      }}
                      tabIndex={0}
                      role="img"
                      aria-label={`${s.label} ${b.label}: ${v}`}
                      className="cursor-pointer outline-none"
                      onMouseEnter={() => {
                        setActiveBucket(b.key);
                        setActiveSeries(s.key);
                      }}
                      onMouseLeave={() => {
                        setActiveBucket(null);
                        setActiveSeries(null);
                      }}
                      onFocus={() => setActiveBucket(b.key)}
                      onBlur={() => setActiveBucket(null)}
                    />
                  );
                })}

                {bucketTotal > 0 && (
                  <text
                    x={cx}
                    y={baseline - (bucketTotal / yMax) * INNER_H - 6}
                    textAnchor="middle"
                    className="fill-oceanic text-[10px] font-bold"
                    style={{
                      opacity: activeBucket === b.key ? 1 : 0,
                      transition: "opacity 180ms",
                    }}
                  >
                    {bucketTotal}
                  </text>
                )}

                <text x={cx} y={H - 8} textAnchor="middle" className="fill-gray-400 text-[10px]">
                  {b.label}
                </text>
              </g>
            );
          })}

          <line x1={PAD_L} x2={W - PAD_R} y1={baseline} y2={baseline} stroke="#C3CFC9" strokeWidth={1} />
        </svg>

        {hovered && (
          <div className="pointer-events-none absolute end-0 top-0 rounded-sm bg-oceanic px-2 py-1 text-xs font-medium text-white shadow">
            <span className="font-semibold">{hoveredTotal}</span> · {hovered.label}
          </div>
        )}
      </div>
    </div>
  );
}
