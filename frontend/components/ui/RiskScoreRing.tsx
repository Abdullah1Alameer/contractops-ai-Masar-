"use client";
import { cn } from "@/lib/utils";

export default function RiskScoreRing({
  score,
  size = 88,
  className,
  label,
}: {
  score: number;
  size?: number;
  className?: string;
  label?: string;
}) {
  const clamped = Math.min(100, Math.max(0, score));
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (clamped / 100) * c;
  const tone =
    clamped >= 70 ? "text-danger-600" : clamped >= 40 ? "text-warning-600" : "text-success-600";
  const stroke =
    clamped >= 70 ? "#dc2626" : clamped >= 40 ? "#d97706" : "#059669";

  return (
    <div className={cn("relative inline-flex flex-col items-center gap-1", className)}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90" aria-hidden>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e4e4e7" strokeWidth={6} />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={stroke}
            strokeWidth={6}
            strokeDasharray={c}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="motion-safe:transition-all duration-500"
          />
        </svg>
        <span
          className={cn("absolute inset-0 flex items-center justify-center text-xl font-bold tabular-nums", tone)}
          aria-live="polite"
        >
          {Math.round(clamped)}
        </span>
      </div>
      {label && <span className="text-xs font-medium text-neutral-500">{label}</span>}
    </div>
  );
}
