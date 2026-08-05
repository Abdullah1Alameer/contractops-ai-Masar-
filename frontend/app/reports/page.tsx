"use client";
import { useEffect, useMemo, useState } from "react";

import ProgressBar from "@/components/ui/ProgressBar";
import SectionHeader from "@/components/ui/SectionHeader";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ContractListItem } from "@/lib/types";

export default function ReportsPage() {
  const { t } = useI18n();
  const [rows, setRows] = useState<ContractListItem[]>([]);

  useEffect(() => {
    api<ContractListItem[]>("/api/contracts").then(setRows).catch(() => setRows([]));
  }, []);

  const byStage = useMemo(() => {
    const m: Record<string, number> = {};
    for (const c of rows) {
      const s = c.stage ?? "negotiation";
      m[s] = (m[s] ?? 0) + 1;
    }
    return Object.entries(m).sort((a, b) => b[1] - a[1]);
  }, [rows]);

  const awaitingSign = rows.filter((c) => c.stage === "awaiting_signature" || c.stage === "partially_signed").length;
  const internal = rows.filter((c) => c.stage === "internal_review").length;

  return (
    <div className="space-y-8">
      <h1 className="text-title">{t("nav.reports")}</h1>
      <section className="surface-panel p-6">
        <SectionHeader title={t("reports.section.byStage")} />
        <ul className="space-y-3">
          {byStage.map(([stage, count]) => (
            <li key={stage}>
              <div className="mb-1 flex justify-between text-sm">
                <span>{stage}</span>
                <span className="font-semibold tabular-nums">{count}</span>
              </div>
              <ProgressBar value={count} max={rows.length || 1} tone="brand" />
            </li>
          ))}
        </ul>
      </section>
      <div className="grid gap-6 md:grid-cols-2">
        <div className="surface-card p-6">
          <SectionHeader title={t("reports.section.turnaround")} />
          <p className="text-3xl font-bold text-brand-700">{awaitingSign}</p>
          <p className="text-hint">{t("nav.signatures")}</p>
        </div>
        <div className="surface-card p-6">
          <SectionHeader title={t("reports.section.bottlenecks")} />
          <p className="text-3xl font-bold text-warning-600">{internal}</p>
          <p className="text-hint">{t("nav.approvals")}</p>
        </div>
      </div>
    </div>
  );
}
