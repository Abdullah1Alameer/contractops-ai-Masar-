"use client";
import { cn } from "@/lib/utils";

/**
 * The house surface: frosted glass over the shell's ambient light field.
 * Every page inherits this, so upgrading it here lifts the whole app rather
 * than requiring per-page edits.
 */
export function Card({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("glass-card glass-card-hover", className)} {...props}>
      {children}
    </div>
  );
}

export function CardHeader({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("border-b border-white/80 px-6 py-5", className)}>{children}</div>;
}

export function CardBody({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("p-6", className)}>{children}</div>;
}
