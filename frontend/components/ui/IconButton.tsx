"use client";
import { cn } from "@/lib/utils";

export default function IconButton({
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-lg text-gray-600 hover:bg-muted-100 active:bg-muted-200 focus-visible:focus-ring disabled:opacity-50",
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
