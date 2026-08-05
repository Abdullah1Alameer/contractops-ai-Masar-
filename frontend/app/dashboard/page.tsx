"use client";
import Link from "next/link";
import { useMemo } from "react";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { ReviewStatusBadge } from "@/components/SendForReviewDialog";
import Button from "@/components/ui/Button";
import Stat from "@/components/ui/Stat";
import Timeline from "@/components/ui/Timeline";
import SectionHeader from "@/components/ui/SectionHeader";
import RefreshingDot from "@/components/ui/RefreshingDot";
import { SkeletonCard, SkeletonKPI } from "@/components/ui/Skeleton";
import { api } from "@/lib/api";
import { mapActivityEvents } from "@/lib/activity";
import { useCachedFetch } from "@/lib/cache";
import { useI18n } from "@/lib/i18n";
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
  const { t } = useI18n();
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

  const coverageTone = useMemo(() => {
    if (agg?.coveragePct == null) return "default" as const;
    if (agg.coveragePct >= 80) return "success" as const;
    if (agg.coveragePct >= 50) return "warning" as const;
    return "danger" as const;
  }, [agg?.coveragePct]);

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">{t("dashboard.title")}</h1>
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
      <h1 className="text-title flex items-center gap-2">
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
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Link href="/contracts"><Stat label={t("dashboard.kpi.activeContracts")} value={agg.active} tone="brand" /></Link>
            <Link href="/reviews"><Stat label={t("dashboard.kpi.pendingReviews")} value={reviewItems.filter((r) => r.status === "sent" || r.status === "opened").length} tone="info" /></Link>
            <Link href="/contracts?stage=negotiation"><Stat label={t("dashboard.kpi.negotiationsOpen")} value={negotiationCount} /></Link>
            <Link href="/contracts?stage=internal_review&role=legal"><Stat label={t("dashboard.kpi.awaitingLegal")} value={approvalKpis?.pending_legal ?? 0} tone="warning" /></Link>
            <Link href="/contracts?stage=internal_review&role=finance"><Stat label={t("dashboard.kpi.awaitingFinance")} value={approvalKpis?.pending_finance ?? 0} tone="warning" /></Link>
            <Link href="/contracts?stage=internal_review&role=executive"><Stat label={t("dashboard.kpi.awaitingExecutive")} value={approvalKpis?.pending_executive ?? 0} tone="warning" /></Link>
            <Link href="/contracts?stage=awaiting_signature"><Stat label={t("dashboard.kpi.readyToSign")} value={sigKpis?.awaiting_signature ?? 0} tone="success" /></Link>
            <Link href="/contracts?stage=active"><Stat label={t("dashboard.kpi.completed")} value={sigKpis?.completed_signatures ?? 0} tone="success" /></Link>
            <Stat label={t("dashboard.kpi.rejected")} value={sigKpis?.declined_requests ?? 0} tone="danger" />
          </div>

          {agg.active === 0 && agg.total === 0 ? (
            <EmptyState title={t("dashboard.empty.noData")} actionLabel={t("nav.upload")} onAction={() => (window.location.href = "/upload")} />
          ) : (
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="space-y-6">
                <Card className="surface-panel border-0 shadow-none">
                  <CardHeader>
                    <SectionHeader title={t("dashboard.section.recentActivity")} />
                  </CardHeader>
                  <CardBody>
                    {activityItems.length === 0 ? (
                      <EmptyState title={t("common.empty")} />
                    ) : (
                      <Timeline items={activityItems} />
                    )}
                  </CardBody>
                </Card>
                <Card className="surface-panel border-0 shadow-none">
                  <CardHeader>
                    <SectionHeader title={t("dashboard.section.aiInsights")} />
                  </CardHeader>
                  <CardBody>
                    <ul className="space-y-2">
                      {agg.riskContracts.filter((c) => c.score > 0).slice(0, 5).map((c) => (
                        <li key={c.id}>
                          <Link href={`/contracts/${c.id}`} className="link-strong">
                            {c.title}
                          </Link>
                          <span className="ms-2 text-xs font-bold text-danger-600">{c.score}</span>
                        </li>
                      ))}
                      {agg.riskContracts.every((c) => c.score === 0) && <p className="text-hint">{t("common.empty")}</p>}
                    </ul>
                  </CardBody>
                </Card>
                {sigKpis && (
                  <Card>
                    <CardHeader>
                      <h2 className="font-bold">{t("dashboard.section.signatureProgress")}</h2>
                    </CardHeader>
                    <CardBody className="grid gap-2 sm:grid-cols-2">
                      <Link href="/contracts?stage=awaiting_signature" className="text-sm font-semibold text-brand-700">
                        {t("dashboard.kpi.sigAwaiting")}: {sigKpis.awaiting_signature}
                      </Link>
                      <Link href="/contracts?stage=partially_signed" className="text-sm font-semibold text-brand-700">
                        {t("dashboard.kpi.sigPartial")}: {sigKpis.partially_signed}
                      </Link>
                    </CardBody>
                  </Card>
                )}
              </div>
              <div className="space-y-6">
                <Card className="surface-panel border-0 shadow-none">
                  <CardHeader>
                    <SectionHeader title={t("dashboard.section.recentUpdates")} />
                  </CardHeader>
                  <CardBody className="divide-y divide-neutral-100 p-0">
                    {recentContracts.map((c) => (
                      <Link key={c.id} href={`/contracts/${c.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-neutral-50">
                        <span className="font-medium text-neutral-900">{c.title}</span>
                        <span className="text-xs text-neutral-500">{c.created_at?.slice(0, 10) ?? "—"}</span>
                      </Link>
                    ))}
                  </CardBody>
                </Card>
                <Panel title={t("dashboard.section.upcoming")} empty={t("empty.deadlines")} rows={agg.upcomingList.slice(0, 8)} t={t} />
                <RiskPanel title={t("dashboard.section.highRisk")} contracts={agg.riskContracts.slice(0, 5)} empty={t("dashboard.empty.noData")} t={t} />
                {approvalKpis && (
                  <Card>
                    <CardHeader>
                      <h2 className="font-bold">{t("dashboard.section.approvalProgress")}</h2>
                    </CardHeader>
                    <CardBody className="space-y-2 text-sm">
                      <Link href="/contracts?stage=internal_review&role=legal" className="block text-brand-700">
                        {t("dashboard.kpi.pendingLegalApproval")}: {approvalKpis.pending_legal}
                      </Link>
                      <Link href="/contracts?stage=approved" className="block text-brand-700">
                        {t("dashboard.kpi.awaitingSignature")}: {approvalKpis.approved_awaiting_signature}
                      </Link>
                    </CardBody>
                  </Card>
                )}
              </div>
            </div>
          )}

          <Card>
            <CardHeader>
              <Link href="/reviews" className="font-bold text-gray-900 hover:text-brand-700">
                {t("review.dashboard.title")}
              </Link>
            </CardHeader>
            <CardBody className="pt-0">
              {reviewItems.length === 0 ? (
                <p className="py-6 text-center text-sm text-gray-500">{t("review.dashboard.empty")}</p>
              ) : (
                <ul className="divide-y divide-gray-100">
                  {reviewItems.slice(0, 12).map((r) => (
                    <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                      <div>
                        <Link href={`/contracts/${r.contract_id}`} className="text-sm font-semibold text-brand-700 hover:underline">
                          {r.contract_title ?? r.contract_id}
                        </Link>
                        <p className="text-xs text-gray-500">
                          {t("review.dashboard.recipient")}: {r.recipient_name} · {r.created_at?.slice(0, 10)}
                        </p>
                      </div>
                      <ReviewStatusBadge status={r.status} />
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </>
      ) : null}
    </div>
  );
}

function Panel({
  title,
  empty,
  rows,
  t,
}: {
  title: string;
  empty: string;
  rows: { contractTitle: string; contractId: string; row: DeadlineRow }[];
  t: (k: import("@/lib/i18n").TKey) => string;
}) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <h2 className="font-bold text-gray-900">{title}</h2>
      </CardHeader>
      <CardBody className="flex-1 pt-0">
        {rows.length === 0 ? (
          <p className="py-6 text-center text-sm text-gray-500">{empty}</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {rows.map(({ contractId, contractTitle, row }) => (
              <li key={row.id} className="py-3 motion-safe:transition-colors hover:bg-muted-50/80">
                <Link href={`/contracts/${contractId}`} className="block">
                  <p className="text-sm font-semibold text-gray-900">{row.title ?? row.type}</p>
                  <p className="text-xs text-gray-500">{contractTitle}</p>
                  <p className="mt-1 text-xs tabular-nums text-danger-600">
                    {row.deadline_date ?? "—"}
                    {row.days_remaining != null && (
                      <span className="ms-2 text-gray-600">
                        ({row.days_remaining} {t("common.days")})
                      </span>
                    )}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

function RiskPanel({
  title,
  contracts,
  empty,
  t,
}: {
  title: string;
  contracts: { id: string; title: string; score: number }[];
  empty: string;
  t: (k: import("@/lib/i18n").TKey) => string;
}) {
  return (
    <Card>
      <CardHeader>
        <h2 className="font-bold text-gray-900">{title}</h2>
      </CardHeader>
      <CardBody className="pt-0">
        {contracts.length === 0 || contracts.every((c) => c.score === 0) ? (
          <p className="py-6 text-center text-sm text-gray-500">{empty}</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {contracts
              .filter((c) => c.score > 0)
              .map((c) => (
                <li key={c.id} className="flex items-center justify-between py-3 hover:bg-muted-50/80">
                  <Link href={`/contracts/${c.id}`} className="text-sm font-semibold text-brand-700 hover:underline">
                    {c.title}
                  </Link>
                  <span className="rounded-full bg-danger-100 px-2 py-0.5 text-xs font-bold text-danger-700">{c.score}</span>
                </li>
              ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
