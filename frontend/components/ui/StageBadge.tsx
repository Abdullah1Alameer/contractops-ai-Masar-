"use client";
import Badge from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";

const STAGE_TONE: Record<string, "subtle" | "info" | "warning" | "success" | "purple" | "orange"> = {
  draft: "subtle",
  negotiation: "info",
  client_review: "warning",
  internal_review: "purple",
  ready_to_sign: "orange",
  awaiting_signature: "orange",
  partially_signed: "warning",
  approved: "success",
  active: "success",
  signed: "success",
};

export default function StageBadge({ stage }: { stage?: string | null }) {
  const { t } = useI18n();
  const s = stage ?? "negotiation";
  const tone = STAGE_TONE[s] ?? "subtle";
  const labelKey = `stage.${s}` as import("@/lib/i18n").TKey;
  const label = t(labelKey) !== labelKey ? t(labelKey) : s.replace(/_/g, " ");
  return (
    <Badge tone={tone} size="sm">
      {label}
    </Badge>
  );
}
