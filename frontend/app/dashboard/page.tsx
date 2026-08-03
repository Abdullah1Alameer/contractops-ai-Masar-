"use client";
// F5 — dashboard. Aggregates come from GET /api/dashboard (see
// backend/app/routers/dashboard.py). Enterprise BI-style layout modeled on a
// classic PowerBI report page: sidebar nav, 4 centered KPI cards, a
// bar+donut row, then a trend chart + recent-contracts table row.
import { useEffect, useState } from "react";
import Link from "next/link";

import AreaLineChart, { type TimeSeriesPoint } from "@/components/AreaLineChart";
import DonutChart, { type DonutSegment } from "@/components/DonutChart";
import Sidebar from "@/components/Sidebar";
import StackedBarChart, { type HistogramBucket } from "@/components/StackedBarChart";
import StatusChip from "@/components/StatusChip";
import TypeBadge from "@/components/TypeBadge";
import { api, apiWithMeta } from "@/lib/api";
import { CHART_FORSYTHIA, CHART_NOCTURNAL, CHART_OCEANIC, CHART_SAFFRON } from "@/lib/chartColors";
import { monthLabel } from "@/lib/chartMath";
import { useI18n } from "@/lib/i18n";
import type { ContractListItem, DashboardData } from "@/lib/types";
import { useCountUp } from "@/lib/useCountUp";
import { formatSAR } from "@/lib/utils";

export default function DashboardPage() {
  const { t, lang, setLang } = useI18n();
  const [meta, setMeta] = useState<{ data: DashboardData; placeholder: boolean } | null>(null);
  const [contracts, setContracts] = useState<ContractListItem[] | null>(null);
  const [error, setError] = useState(false);

  const load = () => {
    setError(false);
    Promise.all([apiWithMeta<DashboardData>("/api/dashboard"), api<ContractListItem[]>("/api/contracts")])
      .then(([dash, list]) => {
        setMeta(dash);
        setContracts(list);
      })
      .catch(() => setError(true));
  };
  useEffect(load, []);

  const totalContracts = useCountUp(meta?.data.contracts.total ?? 0);
  const deadlines30 = useCountUp(meta?.data.deadlines_next_30_days ?? 0);
  const overdue = useCountUp(meta?.data.overdue_obligations ?? 0);
  const claimable = useCountUp(meta?.data.claimable_milestones_sar ?? 0);

  return (
    <div className="-mx-4 -my-6 flex bg-arctic">
      <Sidebar />

      <div className="min-w-0 flex-1 p-6">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-3xl font-extrabold text-oceanic">{t("dashboard.title")}</h1>
          <button
            onClick={() => setLang(lang === "ar" ? "en" : "ar")}
            className="rounded-sm border border-mint bg-white px-4 py-2 text-sm font-medium text-oceanic shadow-sm hover:bg-arctic"
          >
            {lang === "ar" ? "English" : "العربية"}
          </button>
        </div>

        {error && (
          <div className="rounded-sm bg-white p-8 text-center shadow-sm">
            <p className="mb-3 text-red-600">{t("dashboard.error")}</p>
            <button onClick={load} className="rounded-sm border px-4 py-1.5 text-sm hover:bg-gray-50">
              {t("common.retry")}
            </button>
          </div>
        )}
        {!error && !meta && <p className="p-8 text-center text-gray-400">{t("common.loading")}</p>}

        {!error && meta && (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <KpiCard delay={0} accent={CHART_NOCTURNAL} label={t("dashboard.contracts")} value={Math.round(totalContracts)} />
              <KpiCard delay={80} accent={CHART_OCEANIC} label={t("dashboard.deadlines30")} value={Math.round(deadlines30)} />
              <KpiCard
                delay={160}
                accent={CHART_SAFFRON}
                label={t("dashboard.overdueObligations")}
                value={Math.round(overdue)}
                sub={meta.data.overdue_obligations === 0 ? t("dashboard.overdueNone") : undefined}
              />
              <KpiCard delay={240} accent={CHART_FORSYTHIA} label={t("dashboard.claimable")} value={formatSAR(Math.round(claimable), lang)} />
            </div>

            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-5">
              <ChartCard delay={320} className="lg:col-span-3" title={t("dashboard.obligationsTimeline")} subtitle={t("dashboard.obligationsTimelineSub")}>
                <StackedBarChart
                  buckets={obligationsTimeline(meta.data.obligations_timeline, lang)}
                  series={[
                    { key: "pending", label: t("obligation.pending"), color: CHART_SAFFRON },
                    { key: "overdue", label: t("obligation.overdue"), color: CHART_FORSYTHIA },
                    { key: "done", label: t("obligation.done"), color: CHART_NOCTURNAL },
                  ]}
                />
              </ChartCard>
              <ChartCard delay={380} className="lg:col-span-2" title={t("dashboard.contractStatus")} subtitle={t("dashboard.byStatus")}>
                <DonutChart centerLabel={t("dashboard.contracts")} segments={contractSegments(meta.data.contracts, t)} />
              </ChartCard>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-5">
              <ChartCard delay={440} className="lg:col-span-3" title={t("dashboard.deadlinesTimeline")} subtitle={t("dashboard.deadlinesTimelineSub")}>
                <AreaLineChart data={deadlinesTimeline(meta.data.deadlines_timeline, lang)} color={CHART_NOCTURNAL} />
              </ChartCard>
              <div className="lg:col-span-2">
                <RecentContracts rows={contracts ?? []} t={t} lang={lang} delay={500} />
              </div>
            </div>
          </>
        )}
        {meta?.placeholder && <p className="mt-3 text-center text-xs text-amber-600">{t("common.placeholderData")}</p>}
      </div>
    </div>
  );
}

// Chart colors come from lib/chartColors.ts (nocturnal/forsythia/saffron/oceanic).
function contractSegments(c: DashboardData["contracts"], t: (k: any) => string): DonutSegment[] {
  return [
    { key: "ready", label: t("status.ready"), value: c.ready, color: CHART_NOCTURNAL },
    { key: "processing", label: t("status.processing"), value: c.processing, color: CHART_SAFFRON },
    { key: "needs_review", label: t("status.needs_review"), value: c.needs_review, color: CHART_FORSYTHIA },
    { key: "failed", label: t("status.failed"), value: c.failed, color: CHART_OCEANIC },
  ];
}

function obligationsTimeline(rows: DashboardData["obligations_timeline"], lang: "ar" | "en"): HistogramBucket[] {
  return rows.map((r) => ({
    key: r.month,
    label: monthLabel(r.month, lang),
    values: { pending: r.pending, overdue: r.overdue, done: r.done },
  }));
}

function deadlinesTimeline(rows: DashboardData["deadlines_timeline"], lang: "ar" | "en"): TimeSeriesPoint[] {
  return rows.map((r) => ({ key: r.month, label: monthLabel(r.month, lang), value: r.count }));
}

function KpiCard({
  label,
  value,
  sub,
  accent,
  delay = 0,
}: {
  label: string;
  value: number | string;
  sub?: string;
  accent: string;
  delay?: number;
}) {
  return (
    <div
      className="animate-fade-up group relative overflow-hidden rounded-sm bg-white px-6 py-7 text-center shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
      style={{ animationDelay: `${delay}ms` }}
    >
      <span className="absolute inset-x-0 top-0 h-1 origin-left scale-x-0 transition-transform duration-300 group-hover:scale-x-100" style={{ backgroundColor: accent }} />
      <p className="text-4xl font-extrabold leading-none text-oceanic">{value}</p>
      <p className="mt-2.5 text-xs font-medium uppercase tracking-wide text-gray-500">{label}</p>
      {sub && <p className="mt-1 text-[11px] text-gray-400">{sub}</p>}
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
  delay = 0,
  className = "",
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  return (
    <div
      className={`animate-fade-up rounded-sm bg-white shadow-sm transition-shadow duration-200 hover:shadow-md ${className}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="border-b border-arctic px-5 py-3">
        <p className="text-sm font-bold text-oceanic">{title}</p>
        <p className="mt-0.5 text-xs text-gray-500">{subtitle}</p>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function RecentContracts({
  rows,
  t,
  lang,
  delay = 0,
}: {
  rows: ContractListItem[];
  t: (k: any) => string;
  lang: "ar" | "en";
  delay?: number;
}) {
  const recent = rows.slice(0, 6);
  const total = rows.reduce((sum, c) => sum + (c.value_sar ?? 0), 0);
  return (
    <div className="animate-fade-up h-full overflow-x-auto rounded-sm bg-white shadow-sm" style={{ animationDelay: `${delay}ms` }}>
      <div className="px-5 py-3">
        <p className="text-sm font-semibold text-oceanic">{t("dashboard.recentContracts")}</p>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-mint text-start text-oceanic">
          <tr>
            {(["list.col.title", "list.col.value", "list.col.status"] as const).map((k) => (
              <th key={k} className="px-5 py-2.5 text-start font-semibold">
                {t(k)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {recent.length === 0 && (
            <tr>
              <td colSpan={3} className="px-5 py-8 text-center text-gray-400">
                {t("common.empty")}
              </td>
            </tr>
          )}
          {recent.map((c, i) => (
            <tr key={c.id} className={i % 2 === 1 ? "bg-arctic" : ""}>
              <td className="px-5 py-2.5">
                <Link href={`/contracts/${c.id}`} className="font-medium text-nocturnal hover:underline">
                  {c.title}
                </Link>
                <div className="mt-0.5">
                  <TypeBadge type={c.type} />
                </div>
              </td>
              <td className="px-5 py-2.5 text-gray-700">{formatSAR(c.value_sar, lang)}</td>
              <td className="px-5 py-2.5">
                <StatusChip status={c.status} />
              </td>
            </tr>
          ))}
        </tbody>
        {recent.length > 0 && (
          <tfoot>
            <tr className="border-t-2 border-mint font-bold text-oceanic">
              <td className="px-5 py-3">{t("common.total")}</td>
              <td className="px-5 py-3">{formatSAR(total, lang)}</td>
              <td />
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}
