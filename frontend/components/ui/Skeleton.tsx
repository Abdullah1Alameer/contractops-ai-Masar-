"use client";
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton-shimmer rounded-md bg-muted-100", className)} aria-hidden />;
}

export function SkeletonKPI() {
  return (
    <div className="card-surface p-5">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="mt-3 h-10 w-20" />
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="flex gap-3 py-3">
      <Skeleton className="h-4 flex-1" />
      <Skeleton className="h-4 w-16" />
    </div>
  );
}

export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <div className="card-surface p-5">
      <Skeleton className="mb-4 h-5 w-40" />
      {Array.from({ length: rows }).map((_, i) => (
        <SkeletonRow key={i} />
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="card-surface overflow-hidden p-4">
      <Skeleton className="mb-4 h-8 w-full" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="mb-2 h-10 w-full" />
      ))}
    </div>
  );
}
