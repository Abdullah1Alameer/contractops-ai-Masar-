"use client";
import Link from "next/link";
import { useMemo } from "react";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { ReviewStatusBadge } from "@/components/SendForReviewDialog";
import Button from "@/components/ui/Button";
import Stat from "@/components/ui/Stat";
import Timeline from "@/components/ui/Timeline";
import RefreshingDot from "@/components/ui/RefreshingDot";
import { SkeletonCard, SkeletonKPI } from "@/components/ui/Skeleton";
import { api } from "@/lib/api";
import { mapActivityEvents } from "@/lib/activity";
import { useCachedFetch } from "@/lib/cache";
import AreaTrend from "@/components/charts/AreaTrend";
import BarList from "@/components/charts/BarList";
import ChartCard from "@/components/charts/ChartCard";
import Donut from "@/components/charts/Donut";
import StackedBar from "@/components/charts/StackedBar";
import { useI18n } from "@/lib/i18n";
import { cn, formatCount, formatDate, formatNum } from "@/lib/utils";
import type { ContractListItem, DeadlineRow, ReviewRequestRow } from "@/lib/types";

type DashboardAggregate = {
  total: number;
  active: number;
  upcoming7: number;
  overdue: number;
  claimableSar: number;
  highRiskCount: number;
  coveragePct: number | null;
  missingCritical: number | null;
  overdueList: { contractTitle: string; contractId: string; row: DeadlineRow }[];
  upcomingList: { contractTitle: string; contractId: string; row: DeadlineRow }[];
  riskContracts: { id: string; title: string; score: number }[];
};

type DashboardSummaryResponse = {
  kpis: Record<string, number>;
  recent_contracts: ContractListItem[];
  recent_activity: import("@/lib/types").ActivityEventRow[];
  reviews_summary: { items: ReviewRequestRow[] };
  approvals_summary: import("@/lib/types").ApprovalSummaryKpis;
  signature_summary: import("@/lib/types").SignatureSummaryKpis;
  aggregate: {
    total: number;
    active: number;
    upcoming7: number;
    overdue: number;
    claimable_sar: number;
    high_risk_count: number;
    overdue_list: { contract_id: string; contract_title: string; row: DeadlineRow }[];
    upcoming_list: { contract_id: string; contract_title: string; row: DeadlineRow }[];
    risk_contracts: { id: string; title: string; score: number }[];
  };
};

function mapSummaryToAgg(raw: DashboardSummaryResponse) {
  const a = raw.aggregate;
  return {
    agg: {
      total: a.total,
      active: a.active,
      upcoming7: a.upcoming7,
      overdue: a.overdue,
      claimableSar: a.claimable_sar,
      highRiskCount: a.high_risk_count,
      coveragePct: null as number | null,
      missingCritical: null as number | null,
      overdueList: a.overdue_list.map((x) => ({
        contractId: x.contract_id,
        contractTitle: x.contract_title,
        row: x.row,
      })),
      upcomingList: a.upcoming_list.map((x) => ({
        contractId: x.contract_id,
        contractTitle: x.contract_title,
        row: x.row,
      })),
      riskContracts: a.risk_contracts,
    } satisfies DashboardAggregate,
    reviewItems: raw.reviews_summary?.items ?? [],
    approvalKpis: raw.approvals_summary,
    sigKpis: raw.signature_summary,
    negotiationCount: raw.kpis?.negotiations ?? 0,
    recentContracts: raw.recent_contracts ?? [],
  };
}

export default function DashboardPage() {
  const { t, lang } = useI18n();
  const { data: summary, isLoading, isValidating, error, refresh } = useCachedFetch(
    "dashboard:summary",
    () => api<DashboardSummaryResponse>("/api/dashboard/summary")
  );

  const mapped = useMemo(() => (summary ? mapSummaryToAgg(summary) : null), [summary]);

  const activityItems = useMemo(() => {
    if (!summary?.recent_activity) return [];
    return mapActivityEvents(summary.recent_activity, t);
  }, [summary?.recent_activity, t]);

  const agg = mapped?.agg ?? null;
  const reviewItems = mapped?.reviewItems ?? [];
  const approvalKpis = mapped?.approvalKpis ?? null;
  const sigKpis = mapped?.sigKpis ?? null;
  const negotiationCount = mapped?.negotiationCount ?? 0;
  const recentContracts = mapped?.recentContracts ?? [];

  /**
   * Chart series derived from the summary already on the page — the dashboard
   * makes no extra requests to render its analytics.
   */
  const workloadSegments = useMemo(
    () => [
      { label: t("dashboard.kpi.awaitingLegal"), value: approvalKpis?.pending_legal ?? 0 },
      { label: t("dashboard.kpi.awaitingFinance"), value: approvalKpis?.pending_finance ?? 0 },
      { label: t("dashboard.kpi.awaitingExecutive"), value: approvalKpis?.pending_executive ?? 0 },
      { label: t("dashboard.kpi.readyToSign"), value: sigKpis?.awaiting_signature ?? 0 },
      { label: t("dashboard.kpi.completed"), value: sigKpis?.completed_signatures ?? 0 },
    ],
    [approvalKpis, sigKpis, t],
  );

  const lifecycleSlices = useMemo(
    () =>
      [
        { label: t("dashboard.kpi.activeContracts"), value: agg?.active ?? 0 },
        { label: t("dashboard.kpi.negotiationsOpen"), value: negotiationCount },
        { label: t("dashboard.kpi.readyToSign"), value: sigKpis?.awaiting_signature ?? 0 },
        { label: t("dashboard.kpi.completed"), value: sigKpis?.completed_signatures ?? 0 },
        { label: t("dashboard.kpi.rejected"), value: sigKpis?.declined_requests ?? 0 },
      ].filter((d) => d.value > 0),
    [agg?.active, negotiationCount, sigKpis, t],
  );

  // Magnitude, so this is a sequential bar list rather than five more hues.
  const riskRows = useMemo(
    () =>
      (agg?.riskContracts ?? [])
        .filter((c) => c.score > 0)
        .sort((a, b) => b.score - a.score)
        .slice(0, 6)
        .map((c) => ({ label: c.title, value: c.score })),
    [agg?.riskContracts],
  );

  /**
   * Intake trend: contracts created per month, oldest → newest. Derived from
   * the recent-contracts list already on the page, so it costs no extra
   * request. Month labels come from the locale so the Arabic UI stays Arabic.
   */
  const intakeTrend = useMemo(() => {
    const buckets = new Map<string, { label: string; value: number; sort: number }>();
    for (const c of recentContracts) {
      if (!c.created_at) continue;
      const d = new Date(c.created_at);
      if (Number.isNaN(d.getTime())) continue;
      const key = `${d.getFullYear()}-${d.getMonth()}`;
      const label = new Intl.DateTimeFormat(lang === "ar" ? "ar-SA-u-nu-arab" : "en-US", {
        calendar: "gregory",
        month: "short",
      }).format(d);
      const prev = buckets.get(key);
      buckets.set(key, {
        label,
        value: (prev?.value ?? 0) + 1,
        sort: d.getFullYear() * 12 + d.getMonth(),
      });
    }
    return Array.from(buckets.values()).sort((a, b) => a.sort - b.sort).map(({ label, value }) => ({ label, value }));
  }, [recentContracts, lang]);

  /**
   * Deadline pressure by severity across both the overdue and upcoming lists.
   * Magnitude, so it renders as a sequential bar list rather than more hues.
   */
  const severityRows = useMemo(() => {
    const order = ["critical", "high", "medium", "low"];
    const labels: Record<string, string> = {
      critical: "حرجة",
      high: "مرتفعة",
      medium: "متوسطة",
      low: "منخفضة",
    };
    const counts = new Map<string, number>();
    for (const d of [...(agg?.overdueList ?? []), ...(agg?.upcomingList ?? [])]) {
      const k = (d.row.severity ?? "low").toLowerCase();
      counts.set(k, (counts.get(k) ?? 0) + 1);
    }
    return order
      .filter((k) => (counts.get(k) ?? 0) > 0)
      .map((k) => ({ label: labels[k] ?? k, value: counts.get(k) ?? 0 }));
  }, [agg?.overdueList, agg?.upcomingList]);

  const coverageTone = useMemo(() => {
    if (agg?.coveragePct == null) return "default" as const;
    if (agg.coveragePct >= 80) return "success" as const;
    if (agg.coveragePct >= 50) return "warning" as const;
    return "danger" as const;
  }, [agg?.coveragePct]);

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">{t("dashboard.title")}</h1>
        <Card>
          <CardBody className="text-center">
            <p className="text-danger-600">{t("common.error")}</p>
            <Button variant="secondary" className="mt-4" onClick={() => refresh()}>
              {t("common.retry")}
            </Button>
          </CardBody>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8 motion-safe:animate-fadeIn">
      <h1 className="flex items-center gap-2 text-3xl font-extrabold tracking-tight text-slate-900 md:text-4xl">
        {t("dashboard.title")}
        {isValidating && <RefreshingDot />}
      </h1>

      {isLoading && !agg ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <SkeletonKPI key={i} />
            ))}
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        </>
      ) : agg ? (
        <>
          {/* Headline row. Nine equally-weighted tiles gave the reader no order
              to scan in; the five that drive decisions lead, and the rest are
              legible inside the panels below. */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <Link href="/contracts">
              <Stat label={t("dashboard.kpi.activeContracts")} value={formatCount(agg.active, lang)} tone="brand" />
            </Link>
            <Link href="/reviews">
              <Stat
                label={t("dashboard.kpi.pendingReviews")}
                value={formatCount(reviewItems.filter((r) => r.status === "sent" || r.status === "opened").length, lang)}
                tone="info"
              />
            </Link>
            <Link href="/contracts?stage=negotiation">
              <Stat label={t("dashboard.kpi.negotiationsOpen")} value={formatCount(negotiationCount, lang)} />
            </Link>
            <Link href="/contracts?stage=awaiting_signature">
              <Stat label={t("dashboard.kpi.readyToSign")} value={formatCount(sigKpis?.awaiting_signature ?? 0, lang)} tone="success" />
            </Link>
            <Stat label={t("dashboard.kpi.rejected")} value={formatCount(sigKpis?.declined_requests ?? 0, lang)} tone="danger" />
          </div>

          {/* Analytics grid */}
          <div className="grid gap-5 lg:grid-cols-12">
            <ChartCard
              title={t("dashboard.section.lifecycleMix")}
              subtitle={t("dashboard.section.lifecycleMixHint")}
              className="lg:col-span-5"
            >
              {lifecycleSlices.length === 0 ? (
                <EmptyState title={t("common.empty")} />
              ) : (
                <Donut slices={lifecycleSlices} centerLabel={t("dashboard.kpi.activeContracts")} />
              )}
            </ChartCard>

            <ChartCard
              title={t("dashboard.section.workload")}
              subtitle={t("dashboard.section.workloadHint")}
              className="lg:col-span-7"
              delay={0.06}
            >
              <StackedBar segments={workloadSegments} />
            </ChartCard>

            <ChartCard
              title={t("dashboard.section.riskRanking")}
              subtitle={t("dashboard.section.riskRankingHint")}
              className="lg:col-span-7"
              delay={0.12}
            >
              {riskRows.length === 0 ? (
                <EmptyState title={t("common.empty")} />
              ) : (
                <BarList rows={riskRows} />
              )}
            </ChartCard>

            <ChartCard
              title={t("dashboard.section.severity")}
              subtitle={t("dashboard.section.severityHint")}
              className="lg:col-span-5"
              delay={0.24}
            >
              {severityRows.length === 0 ? (
                <EmptyState title={t("empty.deadlines")} />
              ) : (
                <BarList rows={severityRows} />
              )}
            </ChartCard>

            <ChartCard
              title={t("dashboard.section.intake")}
              subtitle={t("dashboard.section.intakeHint")}
              className="lg:col-span-7"
              delay={0.18}
            >
              {intakeTrend.length < 2 ? (
                <EmptyState title={t("common.empty")} />
              ) : (
                <AreaTrend points={intakeTrend} />
              )}
            </ChartCard>


            <ChartCard
              title={t("dashboard.section.recentActivity")}
              className="lg:col-span-5"
              delay={0.3}
            >
              {activityItems.length === 0 ? (
                <EmptyState title={t("common.empty")} />
              ) : (
                <Timeline items={activityItems.slice(0, 6)} />
              )}
            </ChartCard>
          </div>

          {agg.active === 0 && agg.total === 0 ? (
            <EmptyState title={t("dashboard.empty.noData")} actionLabel={t("nav.upload")} onAction={() => (window.location.href = "/upload")} />
          ) : (
            <>
              {/* Operations row. Three equal columns on one baseline — the
                  previous two-column stack let the left side run twice the
                  height of the right, which read as an unfinished layout. */}
              <div className="grid items-start gap-5 lg:grid-cols-3">
                <ChartCard title={t("dashboard.section.upcoming")}>
                  {agg.upcomingList.length === 0 ? (
                    <EmptyState title={t("empty.deadlines")} />
                  ) : (
                    <ul className="divide-y divide-slate-100">
                      {agg.upcomingList.slice(0, 5).map((d) => (
                        <li key={`${d.contractId}-${d.row.id ?? d.row.title}`} className="py-3 first:pt-0">
                          <Link
                            href={`/contracts/${d.contractId}`}
                            className="group flex items-start justify-between gap-3"
                          >
                            <span className="min-w-0">
                              <span className="block truncate text-sm font-bold text-slate-900 group-hover:text-emerald-800">
                                {d.row.title ?? d.contractTitle}
                              </span>
                              <span className="mt-0.5 block truncate text-xs text-slate-500">{d.contractTitle}</span>
                            </span>
                            {/* Days remaining, not the raw date: the whole
                                product is about how much of a notice window is
                                left. Tone follows urgency. */}
                            <span
                              className={cn(
                                "tnum shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-bold",
                                (d.row.days_remaining ?? 99) <= 7
                                  ? "border-rose-100 bg-rose-50 text-rose-700"
                                  : (d.row.days_remaining ?? 99) <= 21
                                    ? "border-amber-100 bg-amber-50 text-amber-700"
                                    : "border-emerald-100 bg-emerald-50 text-emerald-700",
                              )}
                            >
                              {d.row.days_remaining != null
                                ? `${formatNum(d.row.days_remaining, lang)} ${t("common.days")}`
                                : formatDate(d.row.deadline_date, lang)}
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </ChartCard>

                <ChartCard title={t("dashboard.section.recentUpdates")} delay={0.06}>
                  {recentContracts.length === 0 ? (
                    <EmptyState title={t("common.empty")} />
                  ) : (
                    <ul className="divide-y divide-slate-100">
                      {recentContracts.slice(0, 5).map((c) => (
                        <li key={c.id} className="py-3 first:pt-0">
                          <Link
                            href={`/contracts/${c.id}`}
                            className="group flex items-center justify-between gap-3"
                          >
                            <span className="min-w-0 truncate text-sm font-bold text-slate-900 group-hover:text-emerald-800">
                              {c.title}
                            </span>
                            <span className="tnum shrink-0 text-xs font-medium text-slate-500">
                              {formatDate(c.created_at, lang)}
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </ChartCard>

                <ChartCard
                  title={t("review.dashboard.title")}
                  delay={0.12}
                  action={
                    <Link href="/reviews" className="text-xs font-bold text-emerald-700 hover:text-emerald-800">
                      {t("common.viewAll")}
                    </Link>
                  }
                >
                  {reviewItems.length === 0 ? (
                    <EmptyState title={t("review.dashboard.empty")} />
                  ) : (
                    <ul className="divide-y divide-slate-100">
                      {reviewItems.slice(0, 5).map((r) => (
                        <li key={r.id} className="flex items-center justify-between gap-3 py-3 first:pt-0">
                          <span className="min-w-0">
                            <Link
                              href={`/contracts/${r.contract_id}`}
                              className="block truncate text-sm font-bold text-slate-900 hover:text-emerald-800"
                            >
                              {r.contract_title ?? r.contract_id}
                            </Link>
                            <span className="mt-0.5 block truncate text-xs text-slate-500">
                              {r.recipient_name} · {formatDate(r.created_at, lang)}
                            </span>
                          </span>
                          <ReviewStatusBadge status={r.status} />
                        </li>
                      ))}
                    </ul>
                  )}
                </ChartCard>
              </div>

              {/* Progress row */}
              <div className="grid items-start gap-5 lg:grid-cols-2">
                {sigKpis && (
                  <ChartCard title={t("dashboard.section.signatureProgress")} delay={0.06}>
                    <StackedBar
                      segments={[
                        { label: t("dashboard.kpi.sigAwaiting"), value: sigKpis.awaiting_signature },
                        { label: t("dashboard.kpi.sigPartial"), value: sigKpis.partially_signed },
                        { label: t("dashboard.kpi.completed"), value: sigKpis.completed_signatures },
                      ]}
                    />
                  </ChartCard>
                )}

                {approvalKpis && (
                  <ChartCard title={t("dashboard.section.approvalProgress")} delay={0.12}>
                    <StackedBar
                      segments={[
                        { label: t("dashboard.kpi.pendingLegalApproval"), value: approvalKpis.pending_legal },
                        { label: t("dashboard.kpi.awaitingFinance"), value: approvalKpis.pending_finance },
                        { label: t("dashboard.kpi.awaitingSignature"), value: approvalKpis.approved_awaiting_signature },
                      ]}
                    />
                  </ChartCard>
                )}
              </div>
            </>
          )}

        </>
      ) : null}
    </div>
  );
}
