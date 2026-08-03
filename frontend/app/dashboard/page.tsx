"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import KPI from "@/components/ui/KPI";
import { SkeletonCard, SkeletonKPI } from "@/components/ui/Skeleton";
import Button from "@/components/ui/Button";
import {
  api,
  fetchDeadlines,
  fetchMilestones,
  getFlowdown,
  listFlowdownContracts,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ContractListItem, DeadlineRow, MilestonesResponse } from "@/lib/types";
import { formatCompactSAR } from "@/lib/utils";

type ContractBundle = {
  contract: ContractListItem;
  deadlines: DeadlineRow[];
  milestones: MilestonesResponse | null;
};

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

async function mapPool<T, R>(items: T[], limit: number, fn: (item: T) => Promise<R>): Promise<R[]> {
  const out: R[] = [];
  let i = 0;
  async function worker() {
    while (i < items.length) {
      const idx = i++;
      out[idx] = await fn(items[idx]);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, () => worker()));
  return out;
}

function isReady(c: ContractListItem) {
  return c.status === "ready" || c.status === "needs_review";
}

function deadlineOverdue(d: DeadlineRow) {
  if (d.status === "missed" || d.status === "time_barred") return true;
  if (d.days_remaining != null && d.days_remaining < 0) return true;
  return false;
}

function riskScore(deadlines: DeadlineRow[]): number {
  let s = 0;
  for (const d of deadlines) {
    if (deadlineOverdue(d)) s += 10;
    else if (d.severity === "critical" && d.days_remaining != null && d.days_remaining <= 30) s += 8;
    else if (d.severity === "critical") s += 5;
    if (d.needs_review) s += 3;
  }
  return s;
}

function buildAggregate(bundles: ContractBundle[], total: number): DashboardAggregate {
  let active = 0;
  let upcoming7 = 0;
  let overdue = 0;
  let claimableSar = 0;
  let highRiskCount = 0;
  const overdueList: DashboardAggregate["overdueList"] = [];
  const upcomingList: DashboardAggregate["upcomingList"] = [];
  const riskContracts: DashboardAggregate["riskContracts"] = [];

  for (const b of bundles) {
    active++;
    const rs = riskScore(b.deadlines);
    if (rs >= 8) highRiskCount++;
    riskContracts.push({ id: b.contract.id, title: b.contract.title, score: rs });

    for (const d of b.deadlines) {
      if (deadlineOverdue(d)) {
        overdue++;
        overdueList.push({ contractTitle: b.contract.title, contractId: b.contract.id, row: d });
      } else if (d.days_remaining != null && d.days_remaining >= 0 && d.days_remaining <= 7) {
        upcoming7++;
        upcomingList.push({ contractTitle: b.contract.title, contractId: b.contract.id, row: d });
      }
    }

    if (b.milestones?.summary) {
      claimableSar += b.milestones.summary.claimable_sar ?? 0;
    }
  }

  overdueList.sort((a, b) => (a.row.days_remaining ?? -999) - (b.row.days_remaining ?? -999));
  upcomingList.sort((a, b) => (a.row.days_remaining ?? 999) - (b.row.days_remaining ?? 999));
  riskContracts.sort((a, b) => b.score - a.score);

  return {
    total,
    active,
    upcoming7,
    overdue,
    claimableSar,
    highRiskCount,
    coveragePct: null,
    missingCritical: null,
    overdueList,
    upcomingList,
    riskContracts,
  };
}

export default function DashboardPage() {
  const { t, lang } = useI18n();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [agg, setAgg] = useState<DashboardAggregate | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const contracts = await api<ContractListItem[]>("/api/contracts");
      const ready = contracts.filter(isReady);
      const bundles = await mapPool(ready, 4, async (c) => {
        const [deadlinesRes, milestonesRes] = await Promise.all([
          fetchDeadlines(c.id).catch(() => ({ deadlines: [], summary: {} as any })),
          fetchMilestones(c.id).catch(() => null),
        ]);
        return {
          contract: c,
          deadlines: deadlinesRes.deadlines ?? [],
          milestones: milestonesRes,
        };
      });

      let data = buildAggregate(bundles, contracts.length);

      try {
        const pairs = await listFlowdownContracts();
        const main = pairs.main[0];
        const sub = pairs.sub[0];
        if (main && sub) {
          const fd = await getFlowdown(main.id, sub.id);
          if (fd.findings?.length) {
            data = {
              ...data,
              coveragePct: fd.summary.coverage_pct,
              missingCritical: fd.summary.missing_count + fd.summary.critical_count,
            };
          }
        }
      } catch {
        /* no cached flowdown */
      }

      setAgg(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

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
            <Button variant="secondary" className="mt-4" onClick={load}>
              {t("common.retry")}
            </Button>
          </CardBody>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-8 motion-safe:animate-fadeIn">
      <h1 className="text-2xl font-bold text-gray-900 md:text-3xl">{t("dashboard.title")}</h1>

      {loading ? (
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
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KPI label={t("dashboard.kpi.totalContracts")} value={agg.total} />
            <KPI label={t("dashboard.kpi.active")} value={agg.active} tone="info" />
            <KPI label={t("dashboard.kpi.upcoming")} value={agg.upcoming7} tone="warning" />
            <KPI label={t("dashboard.kpi.overdue")} value={agg.overdue} tone="danger" />
            <KPI label={t("dashboard.kpi.claimable")} value={formatCompactSAR(agg.claimableSar, lang)} tone="success" />
            <KPI label={t("dashboard.kpi.highRisk")} value={agg.highRiskCount} tone={agg.highRiskCount > 0 ? "danger" : "default"} />
            <KPI
              label={t("dashboard.kpi.coverage")}
              value={agg.coveragePct != null ? `${Math.round(agg.coveragePct)}%` : "—"}
              tone={coverageTone}
              hint={
                agg.coveragePct == null ? (
                  <span>
                    {t("dashboard.empty.noFlowdown")}{" "}
                    <Link href="/flowdown" className="font-semibold text-brand-700 underline">
                      {t("nav.flowdown")}
                    </Link>
                  </span>
                ) : undefined
              }
            />
            <KPI
              label={t("dashboard.kpi.missingCritical")}
              value={agg.missingCritical ?? "—"}
              tone={agg.missingCritical != null && agg.missingCritical > 0 ? "warning" : "default"}
            />
          </div>

          {agg.active === 0 && agg.total === 0 ? (
            <EmptyState title={t("dashboard.empty.noData")} actionLabel={t("nav.upload")} onAction={() => (window.location.href = "/upload")} />
          ) : (
            <div className="grid gap-6 lg:grid-cols-3">
              <Panel title={t("dashboard.panel.recentAlerts")} empty={t("empty.deadlines")} rows={agg.overdueList.slice(0, 8)} t={t} />
              <Panel title={t("dashboard.panel.upcoming7")} empty={t("empty.deadlines")} rows={agg.upcomingList.slice(0, 8)} t={t} />
              <RiskPanel title={t("dashboard.panel.highestRisk")} contracts={agg.riskContracts.slice(0, 5)} empty={t("dashboard.empty.noData")} t={t} />
            </div>
          )}
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
