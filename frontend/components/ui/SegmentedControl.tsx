"use client";
import { cn } from "@/lib/utils";

export default function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
  className,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-flex rounded-lg border border-gray-200 bg-muted-50 p-1 text-sm font-semibold",
        className
      )}
      role="group"
    >
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            "min-w-[4.5rem] rounded-md px-4 py-2 motion-safe:transition-colors",
            value === opt.value ? "bg-white text-brand-700 shadow-sm" : "text-gray-600 hover:text-gray-900"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
