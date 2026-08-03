"use client";
import { useI18n } from "@/lib/i18n";
import type { ContractStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const styles: Record<ContractStatus, string> = {
  processing: "bg-blue-100 text-blue-800",
  ready: "bg-emerald-100 text-emerald-800",
  needs_review: "bg-amber-100 text-amber-800",
  failed: "bg-red-100 text-red-800",
  unsupported: "bg-red-100 text-red-800",
};

export default function StatusChip({ status }: { status: ContractStatus }) {
  const { t } = useI18n();
  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", styles[status])}>
      {t(`status.${status}` as any)}
    </span>
  );
}
