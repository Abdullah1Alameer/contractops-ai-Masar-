"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import FlowdownFindings from "@/components/FlowdownFindings";
import FlowdownSummary from "@/components/FlowdownSummary";
import { ReviewStatusBadge } from "@/components/SendForReviewDialog";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import DualDate from "@/components/DualDate";
import { useConfirm } from "@/components/feedback/ConfirmDialog";
import { useToast } from "@/components/feedback/ToastProvider";
import {
  fetchReviewPortal,
  reviewAddComment,
  reviewApprove,
  reviewReject,
  reviewRequestChanges,
} from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { ReviewPortalPayload } from "@/lib/types";
import { cn, formatSAR } from "@/lib/utils";

type Tab = "summary" | "risks" | "obligations" | "timeline" | "payments" | "comparison";

export default function ReviewPortalPage() {
  const { t, lang } = useI18n();
  const params = useParams<{ token: string }>();
  const token = params.token;
  const { confirm } = useConfirm();
  const { success: toastSuccess, error: toastError } = useToast();

  const [data, setData] = useState<ReviewPortalPayload | null>(null);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [clauseRef, setClauseRef] = useState("");
  const [clauseComment, setClauseComment] = useState("");
  const [overallComment, setOverallComment] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);
  const [showChanges, setShowChanges] = useState(false);

  const load = useCallback(() => {
    setError(false);
    fetchReviewPortal(token)
      .then(setData)
      .catch(() => setError(true));
  }, [token]);

  useEffect(load, [load]);

  const readOnly = data?.read_only ?? false;
  const responded = data?.status === "approved" || data?.status === "rejected" || data?.status === "changes_requested";

  const tabs: { key: Tab; label: TKey }[] = [
    { key: "summary", label: "review.portal.tab.summary" },
    { key: "risks", label: "review.portal.tab.risks" },
    { key: "obligations", label: "review.portal.tab.obligations" },
    { key: "timeline", label: "review.portal.tab.timeline" },
    { key: "payments", label: "review.portal.tab.payments" },
    { key: "comparison", label: "review.portal.tab.comparison" },
  ];

  const onApprove = () => {
    confirm({
      title: t("review.decision.approve"),
      body: t("review.portal.submitApprove"),
      confirmLabel: t("review.decision.approve"),
      onConfirm: async () => {
        setBusy(true);
        try {
          await reviewApprove(token);
          toastSuccess(t("review.portal.thanks"));
          load();
        } catch {
          toastError(t("common.error"));
          throw new Error("approve failed");
        } finally {
          setBusy(false);
        }
      },
    });
  };

  const onReject = async () => {
    if (!rejectReason.trim()) return;
    setBusy(true);
    try {
      await reviewReject(token, rejectReason);
      toastSuccess(t("review.portal.thanks"));
      setShowReject(false);
      load();
    } catch {
      toastError(t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const onChanges = async () => {
    if (!overallComment.trim()) return;
    setBusy(true);
    try {
      await reviewRequestChanges(token, overallComment);
      toastSuccess(t("review.portal.thanks"));
      setShowChanges(false);
      load();
    } catch {
      toastError(t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const onAddComment = async () => {
    if (!clauseComment.trim()) return;
    setBusy(true);
    try {
      await reviewAddComment(token, {
        comment: clauseComment,
        clause_ref: clauseRef || undefined,
        page: undefined,
      });
      setClauseComment("");
      setClauseRef("");
      load();
    } catch {
      toastError(t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  if (error) {
    return (
      <Card>
        <CardBody className="text-center">
          <p className="text-danger-600">{t("common.error")}</p>
          <Button variant="secondary" className="mt-3" onClick={load}>
            {t("common.retry")}
          </Button>
        </CardBody>
      </Card>
    );
  }

  if (!data) return <p className="p-8 text-center text-gray-400">{t("common.loading")}</p>;

  return (
    <div className="min-h-screen bg-white">
      <div className="border-b border-brand-100 bg-brand-50/50 px-4 py-6">
        <div className="mx-auto max-w-6xl">
          <p className="text-sm font-medium text-brand-800">{t("review.portal.title")}</p>
          <h1 className="text-2xl font-bold text-gray-900">{data.contract.title}</h1>
          <div className="mt-2 flex flex-wrap gap-2">
            <ReviewStatusBadge status={data.status} />
            {data.expires_at && <Badge tone="subtle">{data.expires_at.slice(0, 10)}</Badge>}
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-6 pb-28 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {(readOnly || data.status === "expired") && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {data.status === "expired" ? t("review.portal.expired") : responded ? t("review.portal.thanks") : t("review.portal.readOnly")}
            </div>
          )}

          <Card>
            <CardBody>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">{t("review.portal.aiSummary")}</h2>
              <pre className="whitespace-pre-wrap font-sans text-sm text-gray-800">{data.ai_summary}</pre>
            </CardBody>
          </Card>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap gap-1 border-b bg-muted-50/50 p-2">
          {tabs.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={cn(
                "rounded-lg px-3 py-2 text-sm font-semibold",
                tab === key ? "bg-white text-brand-700 shadow-sm" : "text-gray-500"
              )}
            >
              {t(label)}
            </button>
          ))}
        </div>
        <CardBody>
          {tab === "summary" && (
            <dl className="grid gap-3 sm:grid-cols-2 text-sm">
              <div>
                <dt className="text-gray-500">{t("detail.value")}</dt>
                <dd className="font-semibold">{formatSAR(data.contract.value_sar, lang)}</dd>
              </div>
              <div>
                <dt className="text-gray-500">{t("detail.law")}</dt>
                <dd>{data.contract.governing_law ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-gray-500">{t("detail.from")}</dt>
                <dd><DualDate date={data.contract.start_date} /></dd>
              </div>
              <div>
                <dt className="text-gray-500">{t("detail.to")}</dt>
                <dd><DualDate date={data.contract.end_date} /></dd>
              </div>
            </dl>
          )}
          {tab === "risks" && (
            <ul className="space-y-2">
              {data.risks.items.length === 0 && <p className="text-sm text-gray-500">{t("common.empty")}</p>}
              {data.risks.items.map((r, i) => (
                <li key={i} className="rounded-lg border p-3 text-sm">
                  <Badge tone={r.severity === "critical" ? "danger" : r.severity === "high" ? "orange" : "warning"}>
                    {r.severity}
                  </Badge>
                  <p className="mt-1 font-medium">{r.label}</p>
                  <p className="text-gray-600">{r.detail}</p>
                </li>
              ))}
            </ul>
          )}
          {tab === "obligations" && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500">
                    <th className="py-2 text-start">{t("obligation.desc")}</th>
                    <th className="py-2 text-start">{t("obligation.party")}</th>
                    <th className="py-2 text-start">{t("obligation.due")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.obligations.map((o) => (
                    <tr key={o.id} className="border-t">
                      <td className="py-2">{o.description}</td>
                      <td className="py-2">{o.responsible_party ?? "—"}</td>
                      <td className="py-2">{o.due_date ? <DualDate date={o.due_date} /> : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {tab === "timeline" && (
            <ul className="space-y-2 text-sm">
              {data.timeline.deadlines.map((d) => (
                <li key={d.id} className="flex justify-between gap-2 border-b py-2">
                  <span>{d.title ?? d.type}</span>
                  <span className="text-gray-600">{d.deadline_date ?? "—"}</span>
                </li>
              ))}
            </ul>
          )}
          {tab === "payments" && (
            <ul className="space-y-2 text-sm">
              {data.payments.milestones.map((m) => (
                <li key={m.id} className="flex justify-between gap-2 border-b py-2">
                  <span>{m.label}</span>
                  <span>{formatSAR(m.amount_sar, lang)}</span>
                </li>
              ))}
            </ul>
          )}
          {tab === "comparison" &&
            (data.comparison ? (
              <div className="space-y-4">
                <FlowdownSummary summary={data.comparison.summary} />
                <FlowdownFindings findings={data.comparison.findings} onViewMain={() => {}} onViewSub={() => {}} />
              </div>
            ) : (
              <p className="text-sm text-gray-500">{t("review.portal.noComparison")}</p>
            ))}
        </CardBody>
      </Card>

      {data.comments.length > 0 && (
        <Card>
          <CardBody>
            <h3 className="mb-2 font-semibold">{t("review.portal.comments")}</h3>
            <ul className="space-y-2 text-sm">
              {data.comments.map((c) => (
                <li key={c.id} className="rounded border p-2">
                  {c.clause_ref && <span className="font-semibold">{c.clause_ref}: </span>}
                  {c.comment}
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}
        </div>

      {!readOnly && (
        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <Card>
            <CardBody className="space-y-3">
              <h3 className="font-semibold">{t("review.portal.clauseComment")}</h3>
              <input
                className="w-full rounded-lg border px-3 py-2 text-sm"
                placeholder={t("review.portal.clauseRef")}
                value={clauseRef}
                onChange={(e) => setClauseRef(e.target.value)}
              />
              <textarea
                rows={3}
                className="w-full rounded-lg border px-3 py-2 text-sm"
                value={clauseComment}
                onChange={(e) => setClauseComment(e.target.value)}
              />
              <Button variant="secondary" size="sm" loading={busy} onClick={onAddComment}>
                {t("review.portal.addComment")}
              </Button>
            </CardBody>
          </Card>

          <Card className="hidden lg:block">
            <CardBody className="space-y-2">
              <Button variant="primary" className="w-full" loading={busy} onClick={onApprove}>
                {t("review.decision.approve")}
              </Button>
              <Button variant="secondary" className="w-full" onClick={() => { setShowReject(true); setShowChanges(false); }}>
                {t("review.decision.reject")}
              </Button>
              <Button variant="secondary" className="w-full" onClick={() => { setShowChanges(true); setShowReject(false); }}>
                {t("review.decision.changes_requested")}
              </Button>
            </CardBody>
          </Card>

          {showReject && (
            <Card>
              <CardBody className="space-y-2">
                <label className="text-sm font-semibold">{t("review.portal.rejectReason")}</label>
                <textarea className="w-full rounded-lg border px-3 py-2 text-sm" rows={3} value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
                <Button variant="danger" size="sm" loading={busy} onClick={onReject}>
                  {t("review.portal.submitReject")}
                </Button>
              </CardBody>
            </Card>
          )}

          {showChanges && (
            <Card>
              <CardBody className="space-y-2">
                <label className="text-sm font-semibold">{t("review.portal.overallComment")}</label>
                <textarea className="w-full rounded-lg border px-3 py-2 text-sm" rows={3} value={overallComment} onChange={(e) => setOverallComment(e.target.value)} />
                <Button variant="primary" size="sm" loading={busy} onClick={onChanges}>
                  {t("review.portal.submitChanges")}
                </Button>
              </CardBody>
            </Card>
          )}
        </aside>
      )}
      </div>

      {!readOnly && (
          <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-white/95 p-4 shadow-lg backdrop-blur lg:hidden">
            <div className="mx-auto flex max-w-5xl flex-wrap items-end justify-center gap-2">
              <Button variant="primary" loading={busy} onClick={onApprove}>
                {t("review.decision.approve")}
              </Button>
              <Button variant="secondary" onClick={() => { setShowReject(true); setShowChanges(false); }}>
                {t("review.decision.reject")}
              </Button>
              <Button variant="secondary" onClick={() => { setShowChanges(true); setShowReject(false); }}>
                {t("review.decision.changes_requested")}
              </Button>
            </div>
          </div>
      )}
    </div>
  );
}
