"use client";
import KPI from "@/components/ui/KPI";
import { useI18n } from "@/lib/i18n";
import type { FlowdownSummary as FlowdownSummaryType } from "@/lib/types";

export default function FlowdownSummary({ summary }: { summary: FlowdownSummaryType }) {
  const { t } = useI18n();
  const risk = summary.overall_risk_score;
  const riskTone = risk >= 60 ? "danger" : risk >= 30 ? "warning" : "info";
  const cov = summary.coverage_pct;
  const covTone = cov >= 80 ? "success" : cov >= 50 ? "warning" : "danger";

  return (
    <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <KPI label={t("flowdown.summary.risk")} value={`${risk}%`} tone={riskTone} />
      <KPI label={t("flowdown.summary.critical")} value={summary.critical_count} tone={summary.critical_count > 0 ? "danger" : "default"} />
      <KPI label={t("flowdown.summary.missing")} value={summary.missing_count} tone={summary.missing_count > 0 ? "warning" : "default"} />
      <KPI label={t("flowdown.summary.conflict")} value={summary.conflict_count} tone={summary.conflict_count > 0 ? "danger" : "default"} />
      <KPI label={t("flowdown.summary.coverage")} value={`${cov}%`} tone={covTone} />
    </div>
  );
}
