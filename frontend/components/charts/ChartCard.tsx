"use client";

import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const SPRING = { type: "spring" as const, stiffness: 300, damping: 30 };

/**
 * Frame for a single visualization: title, optional subtitle and action, then
 * the plot. Keeping the frame in one place is what makes a dashboard read as a
 * grid of comparable panels rather than a pile of cards.
 */
export default function ChartCard({
  title,
  subtitle,
  action,
  children,
  className,
  delay = 0,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const reduce = useReducedMotion();

  return (
    <motion.section
      initial={reduce ? false : { opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ ...SPRING, delay }}
      className={cn("glass-card flex flex-col p-6", className)}
    >
      <div className="mb-5 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base font-extrabold tracking-tight text-slate-900">{title}</h3>
          {subtitle && <p className="mt-1 text-xs font-medium text-slate-500">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className="flex-1">{children}</div>
    </motion.section>
  );
}
