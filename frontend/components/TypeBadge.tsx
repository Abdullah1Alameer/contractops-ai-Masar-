"use client";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export default function TypeBadge({ type }: { type: "main" | "subcontract" }) {
  const { t } = useI18n();
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ring-inset",
        type === "main" ? "bg-brand-50 text-brand-700 ring-brand-600/20" : "bg-violet-50 text-violet-700 ring-violet-600/20"
      )}
    >
      {t(type === "main" ? "type.main" : "type.subcontract")}
    </span>
  );
}
