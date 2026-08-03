"use client";
import ConfidenceChip from "@/components/ConfidenceChip";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { useI18n, type TKey } from "@/lib/i18n";
import type { FlowdownFindingRow, SourceTarget } from "@/lib/types";

function catKey(c: string): TKey {
  return `flowdown.category.${c}` as TKey;
}

function statusKey(s: string): TKey {
  return `flowdown.status.${s}` as TKey;
}

function riskKey(r: string): TKey {
  return `flowdown.risk.${r}` as TKey;
}

function statusTone(s: string): "success" | "warning" | "orange" | "danger" | "purple" | "info" | "neutral" {
  if (s === "fully_flowed_down") return "success";
  if (s === "modified") return "warning";
  if (s === "weaker") return "orange";
  if (s === "missing") return "danger";
  if (s === "conflict") return "purple";
  if (s === "stronger") return "info";
  return "neutral";
}

function riskTone(r: string): "danger" | "orange" | "warning" | "info" | "neutral" {
  if (r === "critical") return "danger";
  if (r === "high") return "orange";
  if (r === "medium") return "warning";
  if (r === "low") return "info";
  return "neutral";
}

export default function FlowdownFindings({
  findings,
  onViewMain,
  onViewSub,
}: {
  findings: FlowdownFindingRow[];
  onViewMain: (t: SourceTarget) => void;
  onViewSub: (t: SourceTarget) => void;
}) {
  const { t } = useI18n();

  if (findings.length === 0) {
    return <EmptyState title={t("empty.flowdown")} description={t("flowdown.empty")} />;
  }

  const toTarget = (src: FlowdownFindingRow["main_source"]): SourceTarget | null => {
    if (!src || src.char_start == null || src.char_end == null || src.page == null) return null;
    return { page: src.page, char_start: src.char_start, char_end: src.char_end };
  };

  return (
    <div className="max-h-[70vh] overflow-auto rounded-xl border border-gray-200 bg-white shadow-card">
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10 border-b bg-muted-50 text-gray-600 shadow-sm">
          <tr>
            <th className="px-4 py-3.5 text-start font-semibold">{t("flowdown.col.category")}</th>
            <th className="px-4 py-3.5 text-start font-semibold">{t("flowdown.col.status")}</th>
            <th className="px-4 py-3.5 text-start font-semibold">{t("flowdown.col.risk")}</th>
            <th className="px-4 py-3.5 text-start font-semibold">{t("flowdown.col.recommendation")}</th>
            <th className="px-4 py-3.5 text-start font-semibold">{t("flowdown.col.confidence")}</th>
            <th className="px-4 py-3.5 text-start font-semibold">{t("flowdown.col.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((f) => {
            const mainT = toTarget(f.main_source);
            const subT = toTarget(f.sub_source);
            const rec = f.recommendation || f.explanation || "—";
            return (
              <tr key={f.id} className="border-t align-top motion-safe:transition-colors hover:bg-muted-50/80">
                <td className="px-4 py-3.5 font-bold text-gray-900">{t(catKey(f.category))}</td>
                <td className="px-4 py-3.5">
                  <Badge tone={statusTone(f.status)}>{t(statusKey(f.status))}</Badge>
                </td>
                <td className="px-4 py-3.5">
                  <Badge tone={riskTone(f.risk_level)}>{t(riskKey(f.risk_level))}</Badge>
                </td>
                <td className="max-w-[36ch] px-4 py-3.5 text-gray-700" title={rec}>
                  <span className="line-clamp-2">{rec}</span>
                </td>
                <td className="px-4 py-3.5">
                  {f.confidence != null ? <ConfidenceChip confidence={f.confidence} /> : "—"}
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex flex-wrap gap-2">
                    {mainT ? (
                      <Button variant="ghost" size="sm" onClick={() => onViewMain(mainT)}>
                        {t("flowdown.viewMain")}
                      </Button>
                    ) : (
                      <Badge tone="neutral">{t("flowdown.na")}</Badge>
                    )}
                    {subT ? (
                      <Button variant="secondary" size="sm" onClick={() => onViewSub(subT)}>
                        {t("flowdown.viewSub")}
                      </Button>
                    ) : (
                      <Badge tone="neutral">{t("flowdown.na")}</Badge>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
