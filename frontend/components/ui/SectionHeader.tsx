"use client";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export default function SectionHeader({
  title,
  eyebrow,
  actions,
  className,
}: {
  title: string;
  eyebrow?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-4 flex flex-wrap items-end justify-between gap-3", className)}>
      <div>
        {eyebrow && <p className="text-eyebrow mb-1">{eyebrow}</p>}
        <h2 className="text-lg font-bold text-neutral-900 md:text-xl">{title}</h2>
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
