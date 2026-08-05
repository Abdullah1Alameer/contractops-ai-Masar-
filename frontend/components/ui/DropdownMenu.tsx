"use client";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type Item = { id: string; label: ReactNode; onSelect: () => void; danger?: boolean; disabled?: boolean };

export default function DropdownMenu({
  trigger,
  items,
  align = "end",
  className,
}: {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode;
  items: Item[];
  align?: "start" | "end";
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <div ref={ref} className={cn("relative inline-block", className)}>
      {trigger({ open, toggle: () => setOpen((o) => !o) })}
      {open && (
        <ul
          id={menuId}
          role="menu"
          className={cn(
            "absolute z-50 mt-1 min-w-[10rem] rounded-card border border-neutral-200 bg-white py-1 shadow-elevation-2",
            align === "end" ? "end-0" : "start-0"
          )}
        >
          {items.map((item) => (
            <li key={item.id} role="none">
              <button
                type="button"
                role="menuitem"
                disabled={item.disabled}
                className={cn(
                  "focus-ring block w-full px-3 py-2 text-start text-sm font-medium motion-safe:transition-colors hover:bg-neutral-50 disabled:opacity-40",
                  item.danger ? "text-danger-600" : "text-neutral-800"
                )}
                onClick={() => {
                  if (item.disabled) return;
                  setOpen(false);
                  item.onSelect();
                }}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
