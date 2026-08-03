"use client";
// TODO(F5): dashboard. GET /api/dashboard already returns a realistic
// placeholder shape (X-Placeholder: true) — replace the backend aggregation
// and this page lights up with real numbers, zero routing work.
import { useEffect, useState } from "react";

import { apiWithMeta } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatSAR } from "@/lib/utils";

export default function DashboardPage() {
  const { t, lang } = useI18n();
  const [meta, setMeta] = useState<{ data: any; placeholder: boolean } | null>(null);

  useEffect(() => {
    apiWithMeta<any>("/api/dashboard").then(setMeta).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">{t("dashboard.title")}</h1>
      <div className="mb-4 rounded-xl border border-dashed bg-white p-6 text-center">
        <p className="mb-1 font-semibold text-gray-700">{t("common.wip")}</p>
        <p className="text-sm text-gray-500">{t("dashboard.wip")}</p>
      </div>
      {meta && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label={t("nav.contracts")} value={meta.data.contracts?.total} />
          <Stat label={t("detail.tab.deadlines")} value={meta.data.deadlines_next_30_days} />
          <Stat label={t("obligation.overdue")} value={meta.data.overdue_obligations} />
          <Stat label={t("milestone.status.claimable")} value={formatSAR(meta.data.claimable_milestones_sar, lang)} />
        </div>
      )}
      {meta?.placeholder && <p className="mt-3 text-center text-xs text-amber-600">{t("common.placeholderData")}</p>}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-xl border bg-white p-5 shadow-sm">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-gray-800">{value ?? "—"}</p>
    </div>
  );
}
