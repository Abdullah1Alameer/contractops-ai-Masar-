"use client";
import { useCallback, useEffect, useMemo, useState } from "react";

import SendForReviewDialog, { DeliveryStatusBadge, ReviewStatusBadge } from "@/components/SendForReviewDialog";
import { useToast } from "@/components/feedback/ToastProvider";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import StageBadge from "@/components/ui/StageBadge";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { apiErrorCode, fetchContractReviews, fetchVersions, resendContractReview } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ContractVersionRow, ReviewRequestRow } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function ReviewHistoryPanel({
  contractId,
  highlightId,
}: {
  contractId: string;
  highlightId?: string | null;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const [rows, setRows] = useState<ReviewRequestRow[]>([]);
  const [versions, setVersions] = useState<ContractVersionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([fetchContractReviews(contractId), fetchVersions(contractId)])
      .then(([reviews, vh]) => {
        setRows(reviews);
        setVersions(vh.versions);
      })
      .catch(() => {
        setRows([]);
        setVersions([]);
      })
      .finally(() => setLoading(false));
  }, [contractId]);

  useEffect(load, [load]);

  const current = useMemo(() => versions.find((v) => v.is_current), [versions]);

  const versionLabel = (versionId: string | null | undefined) => {
    if (!versionId) return "—";
    const v = versions.find((x) => x.id === versionId);
    return v?.version_label ?? "—";
  };

  const retry = async (reviewId: string) => {
    setRetrying(reviewId);
    try {
      const res = await resendContractReview(contractId, reviewId);
      load();
      // A resend can itself fail or still be in flight; never announce success
      // unless the persisted attempt actually reports "sent".
      if (res.delivery?.status === "sent") {
        toast.success(t("review.retrySuccess"));
      } else if (res.delivery?.status === "failed") {
        toast.error(t("review.retryFailed"));
      } else {
        toast.info(t("review.retryPending"));
      }
    } catch (caught) {
      toast.error(apiErrorCode(caught, t("common.error")));
    } finally {
      setRetrying(null);
    }
  };

  const copyLink = async (reviewId: string, link: string) => {
    try {
      await navigator.clipboard.writeText(link);
      setCopiedId(reviewId);
      setTimeout(() => setCopiedId((current) => (current === reviewId ? null : current)), 2000);
    } catch (caught) {
      toast.error(apiErrorCode(caught, t("common.copyFailed")));
    }
  };

  if (loading) return <SkeletonCard rows={3} />;
  if (rows.length === 0) return <EmptyState title={t("review.empty")} />;

  return (
    <div className="space-y-4">
      {rows.map((r) => (
        <Card key={r.id} className={cn(highlightId === r.id && "ring-2 ring-brand-500/40 motion-safe:animate-pulse")}>
          <CardBody className="space-y-2 text-sm">
            {r.is_stale && (
              <div className="rounded-card border border-warning-200/80 bg-warning-50/60 p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <StageBadge stage="negotiation" />
                  <span className="text-sm text-warning-900">{t("versions.staleBelongsTo")}</span>
                </div>
                <p className="mt-1 text-xs text-warning-800">
                  {versionLabel(r.version_id)} → {current?.version_label ?? "—"}
                </p>
                <div className="mt-2">
                  <SendForReviewDialog contractId={contractId} onSent={load} triggerLabel={t("versions.staleRestart")} />
                </div>
              </div>
            )}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <ReviewStatusBadge status={r.status} />
              <span className="text-gray-500">
                {r.recipient_name} · {r.recipient_email}
              </span>
            </div>
            <dl className="grid gap-1 text-xs text-gray-600 sm:grid-cols-3">
              <div>
                <dt className="font-semibold">{t("review.dashboard.sent")}</dt>
                <dd>{r.created_at?.slice(0, 10) ?? "—"}</dd>
              </div>
              <div>
                <dt className="font-semibold">{t("review.dashboard.opened")}</dt>
                <dd>{r.opened_at?.slice(0, 10) ?? "—"}</dd>
              </div>
              <div>
                <dt className="font-semibold">{t("review.dashboard.responded")}</dt>
                <dd>{r.responded_at?.slice(0, 10) ?? "—"}</dd>
              </div>
            </dl>
            {r.decision && (
              <p className="text-gray-800">
                {t(`review.decision.${r.decision}` as import("@/lib/i18n").TKey)}
                {r.overall_comment ? `: ${r.overall_comment}` : ""}
              </p>
            )}
            {r.delivery && (
              <div className="flex flex-wrap items-center gap-2 rounded-lg border border-gray-100 bg-muted-50/40 p-2 text-xs text-gray-600">
                <DeliveryStatusBadge status={r.delivery.status} />
                <span>
                  {t("delivery.attempts")}: {r.delivery.attempt_count}
                </span>
                {r.delivery.status === "sent" && r.delivery.sent_at && (
                  <span>
                    {t("delivery.sentAt")}: {r.delivery.sent_at.slice(0, 19)}
                  </span>
                )}
                {r.delivery.status === "failed" && (
                  <span>
                    {t("delivery.failedAt")}: {r.delivery.failed_at?.slice(0, 19) ?? "—"}
                    {r.delivery.safe_error_code ? ` · ${r.delivery.safe_error_code}` : ""}
                  </span>
                )}
              </div>
            )}
            {r.review_link && <p className="break-all text-xs text-brand-700">{r.review_link}</p>}
            <div className="flex flex-wrap gap-2">
              {r.actionable && (
                <Button
                  variant="secondary"
                  size="sm"
                  loading={retrying === r.id}
                  disabled={retrying !== null}
                  onClick={() => retry(r.id)}
                >
                  {t("review.retryEmail")}
                </Button>
              )}
              {r.review_link && (
                <Button variant="secondary" size="sm" onClick={() => copyLink(r.id, r.review_link!)}>
                  {copiedId === r.id ? t("review.send.copied") : t("review.send.copyLink")}
                </Button>
              )}
            </div>
            {r.comments.length > 0 && (
              <ul className="mt-2 space-y-1 border-t pt-2">
                {r.comments.map((c) => (
                  <li key={c.id} className="text-xs text-gray-700">
                    {c.clause_ref && <span className="font-semibold">{c.clause_ref}: </span>}
                    {c.comment}
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      ))}
    </div>
  );
}
