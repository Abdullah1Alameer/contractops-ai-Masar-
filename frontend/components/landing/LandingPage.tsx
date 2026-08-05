"use client";

import { useMemo } from "react";

import AiTodayWidget from "@/components/landing/AiTodayWidget";
import AttentionList from "@/components/landing/AttentionList";
import HeroGreeting from "@/components/landing/HeroGreeting";
import KpiGrid from "@/components/landing/KpiGrid";
import PipelineRail, { PipelineRailSkeleton } from "@/components/landing/PipelineRail";
import QuickActions from "@/components/landing/QuickActions";
import RecentActivityTimeline from "@/components/landing/RecentActivityTimeline";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import RefreshingDot from "@/components/ui/RefreshingDot";
import { SkeletonKPI } from "@/components/ui/Skeleton";
import { api, listNegotiationMonitorThreads } from "@/lib/api";
import { useCachedFetch } from "@/lib/cache";
import { useI18n } from "@/lib/i18n";
import { summarizePipeline, type HomeContractRow } from "@/lib/pipeline";
import type {
  ApprovalSummaryKpis,
  ContractListItem,
  DeadlineRow,
  ReviewRequestRow,
  SignatureSummaryKpis,
} from "@/lib/types";

type DashboardSummaryResponse = {
  kpis: Record<string, number>;
  recent_activity: (import("@/lib/types").ActivityEventRow & {
    contract_id?: string;
    contract_title?: string;
  })[];
  reviews_summary: { items: ReviewRequestRow[] };
  approvals_summary: ApprovalSummaryKpis;
  signature_summary: SignatureSummaryKpis;
  aggregate: {
    total: number;
    upcoming7: number;
    claimable_sar: number;
    high_risk_count: number;
    upcoming_list: { contract_id: string; contract_title: string; row: DeadlineRow }[];
    risk_contracts: { id: string; title: string; score: number }[];
  };
};

type ContractWithWorkflow = ContractListItem & {
  workflow_summary?: HomeContractRow["workflow_summary"];
  end_date?: string | null;
};

export default function LandingPage() {
  const { t, lang } = useI18n();

  const { data: summary, isLoading, isValidating, error, refresh } = useCachedFetch("home:summary", () =>
    api<DashboardSummaryResponse>("/api/dashboard/summary")
  );

  const { data: contracts } = useCachedFetch("home:contracts", () =>
    api<ContractWithWorkflow[]>("/api/contracts?include=workflow_summary")
  );

  const { data: threads } = useCachedFetch("home:negotiation:threads", () =>
    listNegotiationMonitorThreads().then((r) => r.threads)
  );

  const highRiskIds = useMemo(() => {
    const set = new Set<string>();
    for (const r of summary?.aggregate?.risk_contracts ?? []) {
      if (r.score > 0) set.add(r.id);
    }
    return set;
  }, [summary]);

  const pipelineBuckets = useMemo(() => {
    const rows: HomeContractRow[] = (contracts ?? []).map((c) => ({
      id: c.id,
      status: c.status,
      stage: c.stage,
      value_sar: c.value_sar,
      end_date: c.end_date ?? null,
      workflow_summary: c.workflow_summary,
    }));
    return summarizePipeline(rows, highRiskIds);
  }, [contracts, highRiskIds]);

  const portfolioValue = useMemo(
    () => (contracts ?? []).reduce((sum, c) => sum + (Number(c.value_sar) || 0), 0),
    [contracts]
  );

  const needsLegal = useMemo(
    () => (threads ?? []).filter((th) => th.requires_attention || th.status === "lawyer_review").length,
    [threads]
  );

  const aiToday = useMemo(
    () => ({
      needsAttention:
        (summary?.aggregate?.high_risk_count ?? 0) + (summary?.aggregate?.upcoming7 ?? 0) + (summary?.kpis?.pending_reviews ?? 0),
      awaitingSignature: summary?.signature_summary?.awaiting_signature ?? summary?.kpis?.ready_to_sign ?? 0,
      needsLegal,
      deadlinesThisWeek: summary?.aggregate?.upcoming7 ?? 0,
    }),
    [summary, needsLegal]
  );

  const kpiData = useMemo(
    () => ({
      totalContracts: summary?.kpis?.total_contracts ?? summary?.aggregate?.total ?? 0,
      portfolioValue,
      pendingReviews: summary?.kpis?.pending_reviews ?? 0,
      awaitingSignature: summary?.signature_summary?.awaiting_signature ?? 0,
      highRisk: summary?.aggregate?.high_risk_count ?? 0,
      activeNegotiations: summary?.kpis?.negotiations ?? threads?.length ?? 0,
    }),
    [summary, portfolioValue, threads]
  );

  if (error) {
    return (
      <div className="space-y-4">
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

  const loading = isLoading && !summary;

  return (
    <div className="space-y-10 motion-safe:animate-fadeIn pb-8">
      <div className="flex items-center gap-2">
        <span className="sr-only">{t("nav.home")}</span>
        {isValidating ? <RefreshingDot /> : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-12 lg:items-stretch">
        <div className="lg:col-span-8">
          <HeroGreeting />
        </div>
        <div className="lg:col-span-4">
          {loading ? <div className="surface-glass h-full min-h-[12rem] skeleton-shimmer" /> : <AiTodayWidget metrics={aiToday} />}
        </div>
      </div>

      {loading ? (
        <PipelineRailSkeleton />
      ) : (
        <PipelineRail buckets={pipelineBuckets} />
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonKPI key={i} />
          ))}
        </div>
      ) : (
        <KpiGrid data={kpiData} />
      )}

      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <QuickActions />
        </div>
        <div className="lg:col-span-7">
          {summary ? (
            <AttentionList
              data={{
                reviewItems: summary.reviews_summary?.items ?? [],
                approvalKpis: summary.approvals_summary ?? null,
                sigKpis: summary.signature_summary ?? null,
                upcomingList: summary.aggregate?.upcoming_list ?? [],
                claimableSar: summary.aggregate?.claimable_sar ?? 0,
                locale: lang,
              }}
            />
          ) : (
            <div className="surface-panel h-64 skeleton-shimmer" />
          )}
        </div>
      </div>

      {summary ? (
        <RecentActivityTimeline events={summary.recent_activity ?? []} />
      ) : (
        <div className="surface-panel h-48 skeleton-shimmer" />
      )}
    </div>
  );
}
