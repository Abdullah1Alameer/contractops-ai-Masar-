"use client";

import { cn } from "@/lib/utils";

export default function RefreshingDot({ className }: { className?: string }) {
  return (
    <span
      className={cn("inline-block h-2 w-2 animate-pulse rounded-full bg-brand-500", className)}
      role="status"
      aria-label="Refreshing"
    />
  );
}
