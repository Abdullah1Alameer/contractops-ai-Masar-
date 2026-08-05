"use client";
import { cn } from "@/lib/utils";

/**
 * Tactile action surfaces. Primary and danger carry a coloured lift shadow
 * that deepens on hover; secondary is a glass pane. All three raise by 0.5
 * on hover so a click feels like pressing something physical.
 */
const variants = {
  primary:
    "bg-emerald-600 text-white shadow-[0_4px_14px_0_rgb(5,150,105,0.39)] hover:bg-emerald-700 hover:shadow-[0_6px_20px_rgba(5,150,105,0.23)] motion-safe:hover:-translate-y-0.5 active:translate-y-0 disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none",
  secondary:
    "border border-white bg-white/70 text-slate-700 shadow-[0_4px_14px_0_rgb(0,0,0,0.04)] backdrop-blur-2xl hover:text-emerald-700 hover:shadow-[0_6px_20px_rgba(0,0,0,0.07)] motion-safe:hover:-translate-y-0.5 active:translate-y-0 disabled:text-slate-400 disabled:shadow-none",
  danger:
    "bg-rose-600 text-white shadow-[0_4px_14px_0_rgb(225,29,72,0.35)] hover:bg-rose-700 hover:shadow-[0_6px_20px_rgba(225,29,72,0.22)] motion-safe:hover:-translate-y-0.5 active:translate-y-0 disabled:bg-slate-200 disabled:text-slate-400 disabled:shadow-none",
  ghost:
    "text-slate-600 hover:bg-white/70 hover:text-emerald-700 hover:backdrop-blur-2xl disabled:text-slate-400",
};

const sizes = {
  sm: "px-3 py-1.5 text-xs gap-1.5",
  md: "px-4.5 py-2.5 text-sm gap-2",
  lg: "px-6 py-3 text-base gap-2.5",
};

export default function Button({
  variant = "primary",
  size = "md",
  loading,
  disabled,
  className,
  children,
  type = "button",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
  loading?: boolean;
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "focus-ring inline-flex items-center justify-center rounded-full font-bold tracking-tight transition-all duration-200",
        variants[variant],
        sizes[size],
        loading && "cursor-wait opacity-90",
        className,
      )}
      {...props}
    >
      {loading && (
        <span
          className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:animate-none"
          aria-hidden
        />
      )}
      {children}
    </button>
  );
}
