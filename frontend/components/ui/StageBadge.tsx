"use client";
import Badge from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";

const STAGE_TONE: Record<string, "subtle" | "info" | "warning" | "success" | "purple" | "orange" | "danger"> = {
  draft: "subtle",
  ready_for_client: "subtle",
  negotiation: "info",
  client_review: "warning",
  internal_review: "purple",
  ready_to_sign: "orange",
  awaiting_signature: "orange",
  partially_signed: "warning",
  approved: "success",
  signed: "success",
  active: "success",
  completed: "success",
  rejected: "danger",
  cancelled: "danger",
  terminated: "danger",
};

export default function StageBadge({ stage }: { stage?: string | null }) {
  const { t } = useI18n();
  // No hardcoded stage fallback: an unset stage is unknown, not "negotiation".
  if (!stage) {
    return (
      <Badge tone="subtle" size="sm">
        {t("common.unknown")}
      </Badge>
    );
  }
  const tone = STAGE_TONE[stage] ?? "subtle";
  const labelKey = `stage.${stage}` as import("@/lib/i18n").TKey;
  const label = t(labelKey) !== labelKey ? t(labelKey) : stage.replace(/_/g, " ");
  return (
    <Badge tone={tone} size="sm">
      {label}
    </Badge>
  );
}
