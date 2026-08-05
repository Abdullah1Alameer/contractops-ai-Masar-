"use client";
import { cn } from "@/lib/utils";

export default function ProgressBar({
  value,
  max = 100,
  tone = "brand",
  className,
  label,
}: {
  value: number;
  max?: number;
  tone?: "brand" | "success" | "warning" | "danger";
  className?: string;
  label?: string;
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const bar = {
    brand: "bg-brand-600",
    success: "bg-success-600",
    warning: "bg-warning-500",
    danger: "bg-danger-600",
  }[tone];

  return (
    <div className={cn("w-full", className)}>
      {label && (
        <div className="mb-1 flex justify-between text-xs text-neutral-500">
          <span>{label}</span>
          <span className="tabular-nums">{Math.round(pct)}%</span>
        </div>
      )}
      <div className="h-2 overflow-hidden rounded-full bg-neutral-100" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}>
        <div className={cn("h-full rounded-full motion-safe:transition-all duration-300", bar)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
