"use client";
// Part-to-whole donut (≤6 segments) with PowerBI-style callout labels.
// Colors are passed in per segment; the caller decides them from lib/chartColors.ts
// so the whole dashboard's palette lives in one swappable place.
//
// Label geometry note: arc angles are accumulated across EVERY visible segment
// and only filtered for rendering afterwards — filtering first would let a
// skipped sliver desync the angle of every label after it.
import { useEffect, useState } from "react";

import { useCountUp } from "@/lib/useCountUp";

export interface DonutSegment {
  key: string;
  label: string;
  value: number;
  color: string; // hex
}

const W = 330;
const H = 215;
const CX = W / 2;
const CY = H / 2;
const STROKE = 24;
const R = 60;
const OUTER = R + STROKE / 2; // where a leader line leaves the ring
const ELBOW = OUTER + 15; // where the leader line turns horizontal
const TAIL = 10; // horizontal run after the elbow
const CIRC = 2 * Math.PI * R;
const GAP = 3; // arc left empty between segments
const MIN_LABEL_FRAC = 0.04; // below this a callout is unreadable — legend carries it
const MIN_DY = 14; // minimum vertical gap between two callouts

interface Callout {
  key: string;
  text: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  y: number;
  right: boolean;
}

/** Pushes overlapping callouts apart vertically so labels never collide.
 * Each side is spaced independently — a left label can never overlap a right one. */
function declutter(items: Callout[]): Callout[] {
  const bySide = (right: boolean) => {
    const side = items.filter((c) => c.right === right).sort((a, b) => a.y - b.y);
    for (let i = 1; i < side.length; i++) {
      if (side[i].y - side[i - 1].y < MIN_DY) side[i].y = side[i - 1].y + MIN_DY;
    }
    const overflow = side.length ? side[side.length - 1].y - (H - 8) : 0;
    if (overflow > 0) side.forEach((c) => (c.y -= overflow));
    return side;
  };
  return [...bySide(true), ...bySide(false)];
}

export default function DonutChart({
  segments,
  centerLabel,
}: {
  segments: DonutSegment[];
  centerLabel?: string;
}) {
  const [active, setActive] = useState<string | null>(null);
  const [grown, setGrown] = useState(false);
  const [labelled, setLabelled] = useState(false);

  const total = segments.reduce((sum, s) => sum + s.value, 0);
  const shown = segments.filter((s) => s.value > 0);
  const activeSeg = shown.find((s) => s.key === active);
  const animatedTotal = useCountUp(total);

  useEffect(() => {
    const raf = requestAnimationFrame(() => setGrown(true));
    const timer = setTimeout(() => setLabelled(true), 850); // after the arcs finish drawing
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
    };
  }, []);

  // --- arc geometry: accumulate over every visible segment, filter later ---
  let acc = 0;
  const arcs = shown.map((s) => {
    const frac = total > 0 ? s.value / total : 0;
    const startFrac = acc;
    acc += frac;
    return { seg: s, frac, startFrac, midFrac: startFrac + frac / 2 };
  });

  const callouts = declutter(
    arcs
      .filter((a) => a.frac >= MIN_LABEL_FRAC)
      .map((a) => {
        const rad = ((-90 + a.midFrac * 360) * Math.PI) / 180;
        const cos = Math.cos(rad);
        const sin = Math.sin(rad);
        return {
          key: a.seg.key,
          text: `${a.seg.value} (${Math.round(a.frac * 100)}%)`,
          x0: CX + OUTER * cos,
          y0: CY + OUTER * sin,
          x1: CX + ELBOW * cos,
          y1: CY + ELBOW * sin,
          y: CY + ELBOW * sin,
          right: cos >= 0,
        };
      })
  );

  return (
    <div>
      <div className="relative">
        {activeSeg && (
          <div className="pointer-events-none absolute start-1/2 top-0 z-10 -translate-x-1/2 whitespace-nowrap rounded-sm bg-oceanic px-2 py-1 text-xs font-medium text-white shadow">
            <span className="font-semibold">{activeSeg.value}</span> {activeSeg.label}
          </div>
        )}
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto" }}>
          <circle cx={CX} cy={CY} r={R} fill="none" stroke="#EAEFEC" strokeWidth={STROKE} />

          <g transform={`rotate(-90 ${CX} ${CY})`}>
            {arcs.map((a, i) => {
              const raw = a.frac * CIRC;
              const len = Math.max(raw - GAP, 1);
              const dimmed = active !== null && active !== a.seg.key;
              const lifted = active === a.seg.key;
              return (
                <circle
                  key={a.seg.key}
                  cx={CX}
                  cy={CY}
                  r={R}
                  fill="none"
                  stroke={a.seg.color}
                  strokeWidth={lifted ? STROKE + 5 : dimmed ? STROKE - 3 : STROKE}
                  strokeDasharray={grown ? `${len} ${CIRC - len}` : `0 ${CIRC}`}
                  strokeDashoffset={-a.startFrac * CIRC}
                  opacity={dimmed ? 0.45 : 1}
                  style={{
                    transition:
                      "stroke-dasharray 850ms cubic-bezier(0.22,1,0.36,1), stroke-width 200ms ease-out, opacity 200ms",
                    transitionDelay: grown ? `${i * 90}ms` : "0ms",
                  }}
                  tabIndex={0}
                  role="img"
                  aria-label={`${a.seg.label}: ${a.seg.value}`}
                  className="cursor-pointer outline-none"
                  onMouseEnter={() => setActive(a.seg.key)}
                  onMouseLeave={() => setActive(null)}
                  onFocus={() => setActive(a.seg.key)}
                  onBlur={() => setActive(null)}
                />
              );
            })}
          </g>

          {callouts.map((c) => {
            const xEnd = c.x1 + (c.right ? TAIL : -TAIL);
            const dim = active !== null && active !== c.key;
            return (
              <g
                key={c.key}
                style={{
                  opacity: labelled ? (dim ? 0.35 : 1) : 0,
                  transition: "opacity 300ms ease-out",
                }}
              >
                <polyline
                  points={`${c.x0},${c.y0} ${c.x1},${c.y} ${xEnd},${c.y}`}
                  fill="none"
                  stroke="#B7C4BE"
                  strokeWidth={1}
                />
                <text
                  x={xEnd + (c.right ? 4 : -4)}
                  y={c.y}
                  textAnchor={c.right ? "start" : "end"}
                  dominantBaseline="middle"
                  className="fill-gray-600 text-[10px] font-semibold"
                >
                  {c.text}
                </text>
              </g>
            );
          })}

          <text
            x={CX}
            y={CY - 6}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-oceanic text-[26px] font-extrabold"
          >
            {Math.round(animatedTotal)}
          </text>
          {centerLabel && (
            <text x={CX} y={CY + 14} textAnchor="middle" dominantBaseline="middle" className="fill-gray-500 text-[10px]">
              {centerLabel}
            </text>
          )}
        </svg>
      </div>

      <div className="mt-1 flex flex-wrap justify-center gap-x-4 gap-y-1">
        {segments.map((s) => (
          <span
            key={s.key}
            className={`inline-flex cursor-pointer items-center gap-1.5 rounded-sm px-1.5 py-0.5 text-xs transition-colors ${
              active === s.key ? "bg-arctic text-oceanic" : "text-gray-600"
            }`}
            onMouseEnter={() => setActive(s.key)}
            onMouseLeave={() => setActive(null)}
          >
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: s.color }} />
            {s.label}
            <span className="font-semibold text-oceanic">{s.value}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
