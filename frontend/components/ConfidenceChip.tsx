"use client";
import Badge from "@/components/ui/Badge";
import { useI18n } from "@/lib/i18n";

export default function ConfidenceChip({ confidence }: { confidence: number | null | undefined }) {
  const { t } = useI18n();
  if (confidence == null) return null;
  const low = confidence < 0.7;
  return (
    <Badge tone={low ? "warning" : "success"} title={`${Math.round(confidence * 100)}%`}>
      {low ? t("detail.needsReview") : t("confidence.high")}
    </Badge>
  );
}
