"use client";

import { useId, useMemo } from "react";

import { cn } from "@/lib/utils";

/**
 * Guilloche — the engine-turned lattice used on banknotes, share certificates
 * and legal instruments. Here it carries the "contract paper" idea without
 * resorting to literal ornament.
 *
 * The curves are generated as true spirograph (hypotrochoid) paths rather than
 * faked with overlapping circles, which is what gives the pattern its
 * characteristic self-intersecting rosette. Everything is stroked at a very low
 * opacity so it reads as texture, never as content.
 *
 * Rotationally symmetric, so it needs no RTL variant.
 */
type Props = {
  className?: string;
  /** Rosette count across the band. */
  petals?: number;
  /** Stroke colour; inherits currentColor by default. */
  opacity?: number;
  variant?: "band" | "rosette";
};

function hypotrochoid(R: number, r: number, d: number, turns = 24, steps = 720) {
  const pts: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * Math.PI * 2 * turns;
    const x = (R - r) * Math.cos(t) + d * Math.cos(((R - r) / r) * t);
    const y = (R - r) * Math.sin(t) - d * Math.sin(((R - r) / r) * t);
    pts.push(`${x.toFixed(2)},${y.toFixed(2)}`);
  }
  return `M${pts.join("L")}`;
}

export default function Guilloche({
  className,
  petals = 7,
  opacity = 0.16,
  variant = "rosette",
}: Props) {
  const id = useId().replace(/:/g, "");

  const paths = useMemo(() => {
    if (variant === "band") {
      return [
        hypotrochoid(90, 90 / petals, 42, petals, 900),
        hypotrochoid(78, 78 / (petals + 2), 34, petals + 2, 900),
      ];
    }
    return [
      hypotrochoid(96, 96 / petals, 48, petals, 1000),
      hypotrochoid(82, 82 / (petals + 3), 38, petals + 3, 1000),
      hypotrochoid(64, 64 / (petals + 5), 28, petals + 5, 1000),
    ];
  }, [petals, variant]);

  return (
    <svg
      viewBox="-110 -110 220 220"
      className={cn("pointer-events-none select-none", className)}
      aria-hidden
      focusable="false"
    >
      <defs>
        {/* Fades the lattice out at the rim so it never ends on a hard edge. */}
        <radialGradient id={`g-${id}`}>
          <stop offset="0%" stopColor="currentColor" stopOpacity={opacity} />
          <stop offset="62%" stopColor="currentColor" stopOpacity={opacity * 0.75} />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </radialGradient>
        <mask id={`m-${id}`}>
          <rect x="-110" y="-110" width="220" height="220" fill={`url(#g-${id})`} />
        </mask>
      </defs>
      <g mask={`url(#m-${id})`} fill="none" stroke="currentColor" strokeWidth="0.4">
        {paths.map((d, i) => (
          <path key={i} d={d} strokeOpacity={1 - i * 0.18} />
        ))}
      </g>
    </svg>
  );
}
