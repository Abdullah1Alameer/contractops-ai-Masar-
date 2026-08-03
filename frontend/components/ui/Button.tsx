"use client";
import { cn } from "@/lib/utils";

const variants = {
  primary:
    "bg-brand-600 text-white hover:bg-brand-700 active:bg-brand-800 focus-visible:focus-ring disabled:bg-gray-300 disabled:text-gray-500",
  secondary:
    "border-2 border-gray-300 bg-white text-gray-800 hover:bg-muted-50 active:bg-muted-100 focus-visible:focus-ring disabled:border-gray-200 disabled:text-gray-400",
  danger:
    "bg-danger-600 text-white hover:bg-danger-700 active:bg-danger-700 focus-visible:focus-ring disabled:bg-gray-300",
  ghost: "text-gray-700 hover:bg-muted-100 active:bg-muted-200 focus-visible:focus-ring disabled:text-gray-400",
};

const sizes = {
  sm: "px-2.5 py-1 text-xs gap-1",
  md: "px-4 py-2 text-sm gap-2",
  lg: "px-5 py-2.5 text-base gap-2",
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
      className={cn(
        "inline-flex items-center justify-center rounded-lg font-semibold motion-safe:transition-colors",
        variants[variant],
        sizes[size],
        loading && "cursor-wait opacity-90",
        className
      )}
      {...props}
    >
      {loading && (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:animate-none" />
      )}
      {children}
    </button>
  );
}
