"use client";
import { cn } from "@/lib/utils";

const tones = {
  default: "border-neutral-200/80 bg-white",
  success: "border-success-200/80 bg-success-50/50",
  danger: "border-danger-200/80 bg-danger-50/50",
  warning: "border-warning-200/80 bg-warning-50/50",
  info: "border-info-200/80 bg-info-50/50",
  brand: "border-brand-200/80 bg-brand-50/40",
};

export default function Stat({
  label,
  value,
  hint,
  tone = "default",
  className,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: keyof typeof tones;
  className?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className={cn("surface-card p-5", tones[tone], className)}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-eyebrow">{label}</p>
        {icon && <span className="text-brand-600">{icon}</span>}
      </div>
      <p className="mt-2 text-3xl font-bold tabular-nums tracking-tight text-neutral-900">{value}</p>
      {hint && <div className="mt-2 text-hint">{hint}</div>}
    </div>
  );
}
