"use client";
import DropdownMenu from "@/components/ui/DropdownMenu";
import { cn } from "@/lib/utils";

type Action = { id: string; label: string; onSelect: () => void; danger?: boolean; disabled?: boolean };

export default function ActionMenu({ items, className }: { items: Action[]; className?: string }) {
  return (
    <DropdownMenu
      className={className}
      items={items.map((i) => ({ ...i, label: i.label }))}
      trigger={({ toggle }) => (
        <button
          type="button"
          className={cn("focus-ring rounded-lg p-2 text-neutral-500 hover:bg-neutral-100")}
          aria-label="Actions"
          onClick={(e) => {
            e.stopPropagation();
            toggle();
          }}
        >
          ⋮
        </button>
      )}
    />
  );
}
