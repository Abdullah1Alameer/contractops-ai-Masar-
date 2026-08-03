"use client";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export default function ConfidenceChip({ confidence }: { confidence: number | null | undefined }) {
  const { t } = useI18n();
  if (confidence == null) return null;
  const low = confidence < 0.7;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        low ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"
      )}
      title={`${Math.round(confidence * 100)}%`}
    >
      {low ? t("detail.needsReview") : t("confidence.high")}
    </span>
  );
}
