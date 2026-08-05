"use client";
import { cn } from "@/lib/utils";

export type TimelineItem = {
  id: string;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  time?: React.ReactNode;
  tone?: "default" | "success" | "warning" | "danger";
};

export default function Timeline({ items, className }: { items: TimelineItem[]; className?: string }) {
  if (items.length === 0) return null;
  const toneDot = {
    default: "bg-gray-400",
    success: "bg-success-600",
    warning: "bg-warning-600",
    danger: "bg-danger-600",
  };
  return (
    <ul className={cn("space-y-0", className)}>
      {items.map((item, i) => (
        <li key={item.id} className="relative flex gap-3 pb-6 last:pb-0">
          {i < items.length - 1 && (
            <span className="absolute top-3 bottom-0 w-px bg-gray-200 start-[5px]" aria-hidden />
          )}
          <span
            className={cn("relative z-10 mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full", toneDot[item.tone ?? "default"])}
            aria-hidden
          />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-sm font-semibold text-gray-900">{item.title}</p>
              {item.time && <span className="text-xs tabular-nums text-gray-500">{item.time}</span>}
            </div>
            {item.subtitle && <p className="mt-0.5 text-sm text-gray-600">{item.subtitle}</p>}
          </div>
        </li>
      ))}
    </ul>
  );
}
