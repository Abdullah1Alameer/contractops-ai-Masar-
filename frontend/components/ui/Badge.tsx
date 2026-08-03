"use client";
import { cn } from "@/lib/utils";

const toneClasses = {
  success: "bg-success-100 text-success-700 ring-success-600/20",
  warning: "bg-warning-100 text-warning-700 ring-warning-600/20",
  danger: "bg-danger-100 text-danger-700 ring-danger-600/20",
  info: "bg-info-100 text-info-700 ring-info-600/20",
  neutral: "bg-gray-100 text-gray-700 ring-gray-500/10",
  purple: "bg-purple-100 text-purple-800 ring-purple-600/20",
  orange: "bg-orange-100 text-orange-800 ring-orange-600/20",
};

export default function Badge({
  tone = "neutral",
  size = "sm",
  dot,
  className,
  children,
  title,
}: {
  tone?: keyof typeof toneClasses;
  size?: "sm" | "md";
  dot?: boolean;
  className?: string;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium ring-1 ring-inset",
        toneClasses[tone],
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm",
        className
      )}
    >
      {dot && <span className={cn("h-1.5 w-1.5 rounded-full bg-current opacity-80")} />}
      {children}
    </span>
  );
}
