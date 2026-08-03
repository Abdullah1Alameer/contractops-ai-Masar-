"use client";
import Badge from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";
import type { ContractStatus } from "@/lib/types";

const tones: Record<ContractStatus, "info" | "success" | "warning" | "danger"> = {
  processing: "info",
  ready: "success",
  needs_review: "warning",
  failed: "danger",
  unsupported: "danger",
};

export default function StatusChip({ status }: { status: ContractStatus }) {
  const { t } = useI18n();
  return <Badge tone={tones[status]}>{t(`status.${status}` as any)}</Badge>;
}
