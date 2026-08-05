"use client";
import { useCallback, useEffect, useState } from "react";

import ConfidenceChip from "@/components/ConfidenceChip";
import DualDate from "@/components/DualDate";
import Button from "@/components/ui/Button";
import EmptyState from "@/components/ui/EmptyState";
import { Card } from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { ApiError, fetchMilestones, patchMilestone } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { PaymentMilestoneRow, PaymentSummary, SourceTarget } from "@/lib/types";
import { cn, formatSAR } from "@/lib/utils";

function typeKey(t: string): TKey {
  return `payment.type.${t}` as TKey;
}

function statusKey(st: string): TKey {
  return `payment.status.${st}` as TKey;
}

function statusTone(st: string): "info" | "success" | "danger" | "warning" | "neutral" {
  if (st === "claimable" || st === "due") return "info";
  if (st === "scheduled") return "neutral";
  if (st === "paid") return "success";
  if (st === "overdue") return "danger";
  if (st === "needs_review" || st === "inactive") return "warning";
  return "neutral";
}

export default function PaymentTracker({
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
  const [rows, setRows] = useState<PaymentMilestoneRow[]>([]);
  const [summary, setSummary] = useState<PaymentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<"generic" | "409" | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    if (!["ready", "needs_review"].includes(contractStatus)) {
      setLoading(false);
      setRows([]);
      setSummary(null);
      return;
    }
    setLoading(true);
    setError(null);
    fetchMilestones(contractId)
      .then((r) => {
        setRows(r.milestones);
        setSummary(r.summary);
      })
      .catch((e) => {
        setError(e instanceof ApiError && e.status === 409 ? "409" : "generic");
      })
      .finally(() => setLoading(false));
  }, [contractId, contractStatus]);

  useEffect(load, [load, demoToday, refreshKey]);

  const recomputeSummary = (list: PaymentMilestoneRow[]) => {
    const s: PaymentSummary = {
      total: list.length,
      claimable_sar: 0,
      blocked_sar: 0,
      overdue_sar: 0,
      paid_sar: 0,
      needs_review_count: 0,
    };
    for (const m of list) {
      const amt = m.amount_sar ?? 0;
      if (m.status === "claimable") s.claimable_sar += amt;
      else if (m.status === "blocked") s.blocked_sar += amt;
      else if (m.status === "overdue") s.overdue_sar += amt;
      else if (m.status === "paid") s.paid_sar += amt;
      else if (m.status === "needs_review") s.needs_review_count += 1;
    }
    setSummary(s);
  };

  const applyUpdated = (updated: PaymentMilestoneRow) => {
    setRows((prev) => {
      const next = prev.map((r) => (r.id === updated.id ? updated : r));
      recomputeSummary(next);
      return next;
    });
  };

  const togglePre = async (m: PaymentMilestoneRow, preId: string, completed: boolean) => {
    setBusyId(m.id);
    try {
      const updated = await patchMilestone(m.id, { precondition_id: preId, completed });
      applyUpdated(updated);
    } catch {
      // revert by re-reading; keep silent
    } finally {
      setBusyId(null);
    }
  };

  const togglePaid = async (m: PaymentMilestoneRow, paid: boolean) => {
    setBusyId(m.id);
    try {
      const updated = await patchMilestone(m.id, { paid });
      applyUpdated(updated);
    } catch {
      // ignore
    } finally {
      setBusyId(null);
    }
  };

  if (!["ready", "needs_review"].includes(contractStatus)) {
    return <p className="py-8 text-center text-sm text-gray-500">{t("payment.error409")}</p>;
  }
  if (loading) return <SkeletonCard rows={3} />;
  if (error === "409") return <p className="py-8 text-center text-sm text-amber-700">{t("payment.error409")}</p>;
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
      <h3 className="mb-3 text-sm font-semibold text-gray-800">{t("payment.title")}</h3>
      {summary && (
        <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label={t("payment.summary.total")} value={String(summary.total)} />
          <Stat label={t("payment.summary.claimable")} value={formatSAR(summary.claimable_sar, lang)} />
          <Stat label={t("payment.summary.blocked")} value={formatSAR(summary.blocked_sar, lang)} />
          <Stat label={t("payment.summary.overdue")} value={formatSAR(summary.overdue_sar, lang)} />
          <Stat label={t("payment.summary.paid")} value={formatSAR(summary.paid_sar, lang)} />
          <Stat label={t("payment.summary.needsReview")} value={String(summary.needs_review_count)} />
        </div>
      )}
      {rows.length === 0 && <EmptyState title={t("empty.milestones")} description={t("payment.empty")} />}
      <ul className="space-y-4">
        {rows
          .filter((m) => m.role !== "component")
          .map((m) => {
          const breakdown = rows.filter((c) => c.role === "component" && c.parent_seq === m.sequence);
          return (
          <li key={m.id}>
            <Card className="p-5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-semibold text-gray-900">
                  {m.sequence}. {m.label}
                </p>
                <p className="text-xs text-gray-500">{t(typeKey(m.type))}</p>
              </div>
              <Badge tone={statusTone(m.status)}>{t(statusKey(m.status))}</Badge>
            </div>

            <div className="mt-2 flex flex-wrap gap-3 text-sm text-gray-700">
              {m.amount_sar != null && <span>{formatSAR(m.amount_sar, lang)}</span>}
              {m.amount_percentage != null && (
                <span>
                  {m.amount_sar != null ? "+" : ""}
                  {lang === "ar" ? `${m.amount_percentage}٪` : `${m.amount_percentage}%`}
                </span>
              )}
              {m.amount_sar == null && m.amount_percentage == null && <span className="text-gray-400">—</span>}
            </div>

            <p className="mt-1 text-sm">
              {m.next_due_date || m.due_date ? (
                <DualDate date={(m.next_due_date || m.due_date)!} />
              ) : (
                <span className="text-gray-400">{t("payment.noDueDate")}</span>
              )}
            </p>
            {m.frequency && (
              <p className="text-xs text-gray-500">
                {m.frequency}
                {m.due_rule?.day != null ? ` · ${t("payment.dueDay" as TKey)} ${m.due_rule.day}` : ""}
              </p>
            )}
            {m.calculation_explanation && (
              <p className="mt-1 text-xs text-gray-600">{m.calculation_explanation}</p>
            )}
            {!m.claimable && m.status === "scheduled" && (
              <p className="mt-1 text-xs text-gray-500">{t("payment.status.scheduled")}</p>
            )}

            <div className="mt-3">
              <div className="mb-1 flex justify-between text-xs text-gray-600">
                <span>{t("payment.readiness")}</span>
                <span>{m.readiness_percentage}%</span>
              </div>
              <div className="h-2.5 overflow-hidden rounded-full bg-muted-100">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-success-500 to-brand-600 motion-safe:transition-all"
                  style={{ width: `${Math.min(100, m.readiness_percentage)}%` }}
                />
              </div>
            </div>

            {m.missing_preconditions.length > 0 && m.status === "blocked" && (
              <p className="mt-2 text-xs text-amber-800">
                {t("payment.missing")}: {m.missing_preconditions.join(lang === "ar" ? "، " : ", ")}
              </p>
            )}

            {m.preconditions.length > 0 && (
              <ul className="mt-3 space-y-1.5">
                {m.preconditions.map((p) => (
                  <li key={p.id} className="flex items-center gap-2 rounded-md px-1 py-1 text-sm motion-safe:transition-colors hover:bg-muted-50">
                    <input
                      type="checkbox"
                      className="rounded border-gray-300"
                      checked={p.completed}
                      disabled={busyId === m.id || m.paid}
                      onChange={(e) => togglePre(m, p.id, e.target.checked)}
                    />
                    <span className={cn(p.completed && "text-gray-500 line-through")}>{p.label}</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="mt-3 flex flex-wrap items-center gap-2">
              {m.confidence != null && <ConfidenceChip confidence={m.confidence} />}
              {m.verified && m.page != null && m.char_start != null && m.char_end != null ? (
                <button
                  type="button"
                  onClick={() =>
                    onSourceClick({ page: m.page!, char_start: m.char_start!, char_end: m.char_end! })
                  }
                  className="rounded-md bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700 hover:bg-brand-100"
                >
                  {t("payment.viewClause")} {m.clause_ref ?? ""}
                </button>
              ) : null}
              {!m.paid ? (
                <Button variant="primary" size="sm" disabled={busyId === m.id || !m.claimable} loading={busyId === m.id} onClick={() => togglePaid(m, true)}>
                  {t("payment.markPaid")}
                </Button>
              ) : (
                <Button variant="secondary" size="sm" disabled={busyId === m.id} onClick={() => togglePaid(m, false)}>
                  {t("payment.markUnpaid")}
                </Button>
              )}
            </div>
            {breakdown.length > 0 && (
              <ul className="mt-3 space-y-1 border-t pt-3 text-xs text-gray-600">
                {breakdown.map((c) => (
                  <li key={c.id} className="flex justify-between gap-2">
                    <span>{c.label}</span>
                    <span>{c.amount_sar != null ? formatSAR(c.amount_sar, lang) : "—"}</span>
                  </li>
                ))}
              </ul>
            )}
            </Card>
          </li>
        );
        })}
      </ul>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-white px-3 py-2 text-center shadow-sm">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-sm font-bold text-gray-800">{value}</p>
    </div>
  );
}
