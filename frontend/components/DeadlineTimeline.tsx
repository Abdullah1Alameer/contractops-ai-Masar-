"use client";
import { useCallback, useEffect, useState } from "react";

import DualDate from "@/components/DualDate";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { ApiError, fetchDeadlines } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { DeadlineRow, DeadlineSummary, SourceTarget } from "@/lib/types";
import { cn } from "@/lib/utils";

const SEV_DOT: Record<string, string> = {
  normal: "bg-gray-400 ring-gray-400/70",
  info: "bg-info-500 ring-info-500/70",
  warning: "bg-warning-500 ring-warning-500/70",
  critical: "bg-danger-600 ring-danger-600/70",
};

function typeKey(t: string): TKey {
  const k = `deadline.type.${t}` as TKey;
  return k;
}

export default function DeadlineTimeline({
  contractId,
  demoToday,
  contractStatus,
  refreshKey,
  onSourceClick,
}: {
  contractId: string;
  demoToday: string;
  contractStatus: string;
  refreshKey: number;
  onSourceClick: (target: SourceTarget) => void;
}) {
  const { t, lang } = useI18n();
  const [rows, setRows] = useState<DeadlineRow[]>([]);
  const [summary, setSummary] = useState<DeadlineSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<"generic" | "409" | null>(null);

  const load = useCallback(() => {
    if (!["ready", "needs_review"].includes(contractStatus)) {
      setLoading(false);
      setRows([]);
      setSummary(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    fetchDeadlines(contractId)
      .then((r) => {
        setRows(r.deadlines);
        setSummary(r.summary);
      })
      .catch((e) => {
        setError(e instanceof ApiError && e.status === 409 ? "409" : "generic");
      })
      .finally(() => setLoading(false));
  }, [contractId, contractStatus]);

  useEffect(load, [load, demoToday, refreshKey]);

  if (!["ready", "needs_review"].includes(contractStatus)) {
    return <p className="py-8 text-center text-sm text-gray-500">{t("timeline.incomplete")}</p>;
  }
  if (loading) return <SkeletonCard rows={4} />;
  if (error === "409") return <p className="py-8 text-center text-sm text-amber-700">{t("timeline.error409")}</p>;
  if (error)
    return (
      <div className="py-8 text-center">
        <p className="mb-2 text-sm text-red-600">{t("common.error")}</p>
        <Button variant="secondary" size="sm" onClick={load}>
          {t("common.retry")}
        </Button>
      </div>
    );

  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-gray-800">{t("timeline.title")}</h3>
      {summary && (
        <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
          <Stat label={t("timeline.summary.total")} value={summary.total} />
          <Stat label={t("timeline.summary.critical")} value={summary.critical} />
          <Stat label={t("timeline.summary.within14")} value={summary.within_14_days} />
          <Stat label={t("timeline.summary.missed")} value={summary.missed_or_time_barred} />
          <Stat label={t("timeline.summary.needsReview")} value={summary.needs_review} />
        </div>
      )}
      {rows.length === 0 && <EmptyState title={t("empty.deadlines")} description={t("timeline.empty")} />}
      <ul className="space-y-0 border-s-2 border-gray-200 ps-4">
        {rows.map((d) => (
          <li key={d.id} className="relative pb-6 last:pb-0">
            <span
              className={cn(
                "absolute -start-[11px] top-1 h-3.5 w-3.5 rounded-full ring-4 ring-white motion-safe:transition-shadow",
                SEV_DOT[d.severity] ?? "bg-gray-400 ring-gray-400/70"
              )}
            />
            <div
              className={cn(
                "rounded-lg border p-4 shadow-card motion-safe:transition-colors",
                d.status === "critical" || d.severity === "critical" ? "border-danger-500" : "",
                d.time_barred && "border-danger-700 bg-danger-50",
                d.needs_review && "border-warning-400 bg-warning-50/40",
                d.status === "missed" && !d.time_barred && "border-danger-600 bg-danger-50/30",
                d.status === "upcoming" && "border-info-300",
                !d.time_barred && !d.needs_review && d.status !== "missed" && d.status !== "upcoming" && "border-gray-200 bg-white"
              )}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-semibold text-gray-900">
                    {d.title || (t(typeKey(d.type)) as string)}
                  </p>
                  <p className="text-xs text-gray-500">{t(typeKey(d.type))}</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <Badge tone={severityTone(d.severity)} dot>
                    {t(`deadline.severity.${d.severity}` as TKey)}
                  </Badge>
                  <Badge tone={statusTone(d.status)}>{t(`deadline.status.${d.status}` as TKey)}</Badge>
                </div>
              </div>
              {d.description && <p className="mt-1 text-sm text-gray-600">{d.description}</p>}
              {d.event_date && (
                <p className={cn("mt-2 text-sm", d.status === "missed" && "line-through text-gray-500")}>
                  <DualDate date={d.event_date} />
                </p>
              )}
              {d.days_remaining != null && (
                <p className="mt-1 text-sm font-medium text-gray-800">
                  {t("deadline.daysRemaining")}: {formatDays(d.days_remaining, lang)}
                </p>
              )}
              {d.time_barred && (
                <p className="mt-1 text-sm font-semibold text-red-800">{t("deadline.timeBarred")}</p>
              )}
              {d.needs_review && d.review_reason && (
                <p className="mt-1 text-sm text-amber-800">
                  {t(`deadline.needsReview.${d.review_reason}` as TKey)}
                </p>
              )}
              {d.responsible_party && (
                <p className="mt-1 text-xs text-gray-500">
                  {t("deadline.responsibleParty")}: {d.responsible_party}
                </p>
              )}
              <div className="mt-2 flex flex-wrap gap-2">
                {d.verified && d.page != null && d.char_start != null && d.char_end != null ? (
                  <button
                    type="button"
                    onClick={() =>
                      onSourceClick({ page: d.page!, char_start: d.char_start!, char_end: d.char_end! })
                    }
                    className="rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700 hover:bg-brand-100"
                  >
                    {t("deadline.viewClause")} {d.clause_ref ?? ""}
                  </button>
                ) : d.clause_ref ? (
                  <span className="text-xs text-gray-500">
                    {t("detail.clause")} {d.clause_ref}
                  </span>
                ) : null}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border bg-white px-3 py-2 text-center shadow-sm">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-lg font-bold text-gray-800">{value}</p>
    </div>
  );
}

function severityTone(sev: string): "danger" | "warning" | "info" | "neutral" {
  if (sev === "critical") return "danger";
  if (sev === "warning") return "warning";
  if (sev === "info") return "info";
  return "neutral";
}

function statusTone(st: string): "danger" | "warning" | "info" | "neutral" {
  if (st === "missed" || st === "time_barred") return "danger";
  if (st === "needs_review") return "warning";
  if (st === "upcoming") return "info";
  return "neutral";
}

function formatDays(n: number, lang: "ar" | "en") {
  if (lang === "ar") return n.toLocaleString("ar-SA-u-nu-arab");
  return String(n);
}
