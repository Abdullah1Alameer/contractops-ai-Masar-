"use client";
import { useCallback, useEffect, useState } from "react";

import DualDate from "@/components/DualDate";
import { ApiError, fetchDeadlines } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { DeadlineRow, DeadlineSummary, SourceTarget } from "@/lib/types";
import { cn } from "@/lib/utils";

const SEV_DOT: Record<string, string> = {
  normal: "bg-gray-400",
  info: "bg-blue-500",
  warning: "bg-amber-500",
  critical: "bg-red-600",
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
  if (loading) return <p className="py-8 text-center text-sm text-gray-400">{t("common.loading")}</p>;
  if (error === "409") return <p className="py-8 text-center text-sm text-amber-700">{t("timeline.error409")}</p>;
  if (error)
    return (
      <div className="py-8 text-center">
        <p className="mb-2 text-sm text-red-600">{t("common.error")}</p>
        <button onClick={load} className="rounded-md border px-3 py-1 text-sm hover:bg-gray-50">
          {t("common.retry")}
        </button>
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
      {rows.length === 0 && <p className="py-6 text-center text-sm text-gray-400">{t("timeline.empty")}</p>}
      <ul className="space-y-0 border-s-2 border-gray-200 ps-4">
        {rows.map((d) => (
          <li key={d.id} className="relative pb-6 last:pb-0">
            <span
              className={cn(
                "absolute -start-[9px] top-1 h-3 w-3 rounded-full ring-2 ring-white",
                SEV_DOT[d.severity] ?? "bg-gray-400"
              )}
            />
            <div
              className={cn(
                "rounded-lg border p-3 shadow-sm",
                d.time_barred && "border-red-300 bg-red-50",
                d.needs_review && "border-amber-300 bg-amber-50/50",
                d.status === "missed" && !d.time_barred && "border-red-200 bg-red-50/30"
              )}
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-semibold text-gray-900">
                    {d.title || (t(typeKey(d.type)) as string)}
                  </p>
                  <p className="text-xs text-gray-500">{t(typeKey(d.type))}</p>
                </div>
                <div className="flex flex-wrap gap-1">
                  <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", severityClass(d.severity))}>
                    {t(`deadline.severity.${d.severity}` as TKey)}
                  </span>
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
                    {t(`deadline.status.${d.status}` as TKey)}
                  </span>
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

function severityClass(sev: string) {
  if (sev === "critical") return "bg-red-100 text-red-800";
  if (sev === "warning") return "bg-amber-100 text-amber-800";
  if (sev === "info") return "bg-blue-100 text-blue-800";
  return "bg-gray-100 text-gray-700";
}

function formatDays(n: number, lang: "ar" | "en") {
  if (lang === "ar") return n.toLocaleString("ar-SA-u-nu-arab");
  return String(n);
}
