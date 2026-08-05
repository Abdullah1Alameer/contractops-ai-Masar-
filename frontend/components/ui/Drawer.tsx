"use client";
import { useEffect, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type DrawerProps = {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  side?: "end" | "start";
  size?: "md" | "lg";
  children: ReactNode;
  className?: string;
};

export default function Drawer({ open, onClose, title, side = "end", size = "md", children, className }: DrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[90]" role="dialog" aria-modal>
      <button type="button" className="absolute inset-0 bg-black/40" aria-label="Close overlay" onClick={onClose} />
      <div
        className={cn(
          "absolute top-0 flex h-full w-full flex-col bg-white shadow-elevation-3 motion-safe:animate-slideUp",
          size === "lg" ? "max-w-3xl" : "max-w-md",
          side === "end" ? "end-0" : "start-0",
          className
        )}
      >
        {title && (
          <div className="flex items-center justify-between border-b border-neutral-100 px-5 py-4">
            <h2 className="text-lg font-bold text-neutral-900">{title}</h2>
            <button type="button" className="focus-ring rounded-lg p-2 text-neutral-500 hover:bg-neutral-50" onClick={onClose}>
              ×
            </button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}
