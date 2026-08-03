"use client";
import { cn } from "@/lib/utils";

const tones = {
  default: "border-gray-200 bg-white",
  success: "border-success-200 bg-success-50/80",
  danger: "border-danger-200 bg-danger-50/80",
  warning: "border-warning-200 bg-warning-50/80",
  info: "border-info-200 bg-info-50/80",
};

export default function KPI({
  label,
  value,
  hint,
  tone = "default",
  className,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: keyof typeof tones;
  className?: string;
}) {
  return (
    <div className={cn("card-surface hover-lift p-5", tones[tone], className)}>
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className="mt-2 text-3xl font-bold tabular-nums text-gray-900 md:text-4xl">{value}</p>
      {hint && <div className="mt-1 text-xs text-gray-600">{hint}</div>}
    </div>
  );
}
