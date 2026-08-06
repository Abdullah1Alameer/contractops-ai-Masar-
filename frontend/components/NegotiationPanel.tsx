"use client";
import { useCallback, useEffect, useState } from "react";

import RiskScoreRing from "@/components/ui/RiskScoreRing";
import Stat from "@/components/ui/Stat";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonCard } from "@/components/ui/Skeleton";
import { useConfirm } from "@/components/feedback/ConfirmDialog";
import { useToast } from "@/components/feedback/ToastProvider";
import {
  abandonNegotiation,
  analyzeNegotiation,
  apiErrorCode,
  DEMO_ROLE_EVENT,
  DEMO_ROLE_STORAGE,
  fetchNegotiations,
  patchNegotiation,
  recordNegotiationAgreement,
  sendNegotiationUpdated,
} from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { NegotiationCandidate, NegotiationRow } from "@/lib/types";
import { cn } from "@/lib/utils";

const AGREEMENT_OVERRIDE_ROLES = new Set(["legal", "executive"]);

function riskTone(r: string | null): "success" | "warning" | "orange" | "danger" | "neutral" {
  if (r === "critical") return "danger";
  if (r === "high") return "orange";
  if (r === "medium") return "warning";
  if (r === "low") return "success";
  return "neutral";
}

function wsKey(ws: string): TKey {
  return `negotiation.workflow.${ws}` as TKey;
}

function recKey(r: string | null): TKey {
  return `negotiation.rec.${r}` as TKey;
}

function ClauseBlock({ title, body, readOnly }: { title: string; body: string | null; readOnly?: boolean }) {
  return (
    <div className="rounded-lg border bg-white p-3">
      <h5 className="mb-2 text-xs font-semibold uppercase text-gray-500">{title}</h5>
      <p className={`text-sm whitespace-pre-wrap ${readOnly ? "text-gray-700" : ""}`}>{body || "—"}</p>
    </div>
  );
}

function ImpactCard({ title, body }: { title: string; body: string | null }) {
  return (
    <Card className="h-full">
      <CardBody>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</h4>
        <p className="text-sm text-gray-800 whitespace-pre-wrap">{body || "—"}</p>
      </CardBody>
    </Card>
  );
}

function NegotiationResult({
  row,
  lang,
  contractStage,
  role,
  onUpdated,
  onRestart,
  onLifecycleChanged,
  onAgreementResolved,
}: {
  row: NegotiationRow;
  lang: "ar" | "en";
  contractStage?: string | null;
  role: string;
  onUpdated: () => void;
  onRestart?: () => void;
  onLifecycleChanged?: () => void | Promise<void>;
  // Called (not rendered locally) when the override resolves the contract to
  // internal_review. `onUpdated()` triggers the parent's loading-skeleton
  // refetch, which unmounts/remounts this component — any local state set
  // after that call would be silently dropped, so the "resolved" banner is
  // owned by the parent (NegotiationPanel), which never unmounts.
  onAgreementResolved?: () => void;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const { confirm } = useConfirm();
  const [draft, setDraft] = useState(row);
  const [finalEn, setFinalEn] = useState(row.lawyer_final_clause ?? "");
  const [finalAr, setFinalAr] = useState(row.lawyer_final_clause_ar ?? "");
  const [whyOpen, setWhyOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setDraft(row);
    setFinalEn(row.lawyer_final_clause ?? "");
    setFinalAr(row.lawyer_final_clause_ar ?? "");
  }, [row]);

  const save = async (patch: Partial<NegotiationRow>) => {
    setBusy(true);
    try {
      await patchNegotiation(row.id, patch as any);
      onUpdated();
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  const resetToAi = () =>
    save({ lawyer_final_clause: null as any, lawyer_final_clause_ar: null as any });

  const saveFinal = () =>
    save({
      lawyer_final_clause: finalEn || undefined,
      lawyer_final_clause_ar: finalAr || undefined,
    });

  const copyText = async (text: string) => {
    await navigator.clipboard.writeText(text);
    toast.success(t("negotiation.copied"));
  };

  const longWhy = (draft.reasoning?.length ?? 0) > 400;

  const send = async () => {
    setBusy(true);
    try {
      const res = await sendNegotiationUpdated(row.id);
      toast.success(t("negotiation.sent"));
      await navigator.clipboard.writeText(res.review_link);
      onUpdated();
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  const abandon = async () => {
    const reason = window.prompt(t("negotiation.abandonPrompt"))?.trim();
    if (!reason) return;
    setBusy(true);
    try {
      await abandonNegotiation(row.id, reason);
      toast.success(t("negotiation.abandoned"));
      onUpdated();
      onLifecycleChanged?.();
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  // Authorized internal override (docs/contract-lifecycle-policy.md §5): the
  // canonical path is the counterparty clicking Approve on the public
  // follow-up link. This is a distinct, audited trigger for the exact same
  // LifecycleService transition — for when the counterparty confirmed
  // agreement outside the portal (phone/email/in person). It never bypasses
  // LifecycleService or invents new stage semantics on the frontend; it just
  // calls the backend override endpoint and reflects its response.
  const canRecordAgreement =
    contractStage === "negotiation" &&
    row.actionable !== false &&
    !row.is_stale &&
    row.workflow_status !== "accepted" &&
    row.workflow_status !== "closed" &&
    AGREEMENT_OVERRIDE_ROLES.has(role);

  const recordAgreement = () => {
    const reason = window.prompt(t("negotiation.recordAgreementReasonPrompt"))?.trim();
    if (!reason) return;
    confirm({
      title: t("negotiation.recordAgreement"),
      body: t("negotiation.recordAgreementConfirmBody"),
      confirmLabel: t("negotiation.recordAgreement"),
      onConfirm: async () => {
        setBusy(true);
        try {
          const result = await recordNegotiationAgreement(row.id, reason);
          toast.success(t("negotiation.recordAgreementSuccess"));
          if (result.contract_stage === "internal_review") {
            onAgreementResolved?.();
          }
          onUpdated();
          await onLifecycleChanged?.();
        } catch (error) {
          toast.error(apiErrorCode(error, t("common.error")));
        } finally {
          setBusy(false);
        }
      },
    });
  };

  const counter =
    lang === "ar" ? draft.counter_clause_ar || draft.counter_clause : draft.counter_clause || draft.counter_clause_ar;

  return (
    <div className="mt-4 space-y-4 border-t pt-4">
      {row.is_stale && (
        <div className="rounded-card border border-warning-200/80 bg-warning-50/60 p-3">
          <p className="text-sm text-warning-900">{t("versions.staleBelongsTo")}</p>
          {onRestart && (
            <Button variant="secondary" size="sm" className="mt-2" loading={busy} onClick={onRestart}>
              {t("versions.staleRestart")}
            </Button>
          )}
        </div>
      )}
      <Badge tone="info" className="text-sm px-3 py-1">
        {t(wsKey(draft.workflow_status || "pending_analysis"))}
      </Badge>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <ImpactCard title={t("negotiation.card.businessImpact")} body={draft.business_impact} />
        <ImpactCard title={t("negotiation.card.legalRisk")} body={draft.legal_impact} />
        <div className="surface-card flex flex-col items-center justify-center p-4">
          <RiskScoreRing score={(draft.confidence ?? 0.5) * 100} label={t("negotiation.card.score")} size={72} />
        </div>
        <Stat
          label={t("negotiation.card.strategy")}
          value={draft.recommendation ? t(recKey(draft.recommendation)) : "—"}
          tone="brand"
        />
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <ClauseBlock title={t("negotiation.col.original")} body={draft.original_clause} readOnly />
        <ClauseBlock title={t("negotiation.col.client")} body={counter ?? draft.reviewer_comment} readOnly />
        <div className="rounded-card border border-brand-600/20 bg-brand-50/30 p-3">
          <div className="mb-2 flex flex-wrap gap-2">
            <h5 className="text-xs font-semibold uppercase text-neutral-500">{t("negotiation.col.lawyer")}</h5>
            <Button variant="secondary" size="sm" onClick={resetToAi}>
              {t("negotiation.resetAi")}
            </Button>
          </div>
          <textarea
            className="mb-2 w-full rounded-lg border bg-white p-2 text-sm"
            rows={3}
            value={finalEn}
            disabled={!row.actionable || row.is_stale}
            onChange={(e) => setFinalEn(e.target.value)}
            onBlur={saveFinal}
          />
          <textarea
            className="w-full rounded-lg border bg-white p-2 text-sm"
            rows={3}
            dir="rtl"
            value={finalAr}
            disabled={!row.actionable || row.is_stale}
            onChange={(e) => setFinalAr(e.target.value)}
            onBlur={saveFinal}
          />
        </div>
      </div>

      <Card>
        <CardBody className="space-y-2 text-sm">
          <p>
            <span className="font-semibold">{t("negotiation.recommendation")}: </span>
            {draft.recommendation ? t(recKey(draft.recommendation)) : "—"}
          </p>
          <p>
            <span className="font-semibold">{t("negotiation.why")}: </span>
            {longWhy && !whyOpen ? `${draft.reasoning?.slice(0, 400)}…` : draft.reasoning}
          </p>
          {longWhy && (
            <button type="button" className="text-brand-700 underline" onClick={() => setWhyOpen(!whyOpen)}>
              {t("negotiation.whyExpand")}
            </button>
          )}
          <div className="grid gap-3 md:grid-cols-2 pt-2">
            <ImpactCard title={t("negotiation.businessImpact")} body={draft.business_impact} />
            <ImpactCard title={t("negotiation.legalImpact")} body={draft.legal_impact} />
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            <Badge tone={riskTone(draft.risk_level)}>
              {t("negotiation.riskLevel")}: {draft.risk_level ? t(`negotiation.risk.${draft.risk_level}` as TKey) : "—"}
            </Badge>
            {draft.confidence != null && (
              <Badge tone="neutral">
                {t("negotiation.confidence")}: {Math.round(draft.confidence * 100)}%
              </Badge>
            )}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <h4 className="text-xs font-semibold uppercase text-gray-500">{t("negotiation.pros")}</h4>
              <ul className="list-disc ps-5">{(draft.pros || []).map((p, i) => <li key={i}>{p}</li>)}</ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold uppercase text-gray-500">{t("negotiation.cons")}</h4>
              <ul className="list-disc ps-5">{(draft.cons || []).map((c, i) => <li key={i}>{c}</li>)}</ul>
            </div>
          </div>
        </CardBody>
      </Card>

      {draft.final_summary && (
        <Card>
          <CardBody>
            <h4 className="mb-2 font-semibold">{t("negotiation.summaryTitle")}</h4>
            <dl className="grid gap-1 text-sm text-gray-700">
              {Object.entries(draft.final_summary)
                .filter(([k]) => k !== "review_link")
                .map(([k, v]) => (
                  <div key={k}>
                    <dt className="inline font-semibold">{k}: </dt>
                    <dd className="inline whitespace-pre-wrap">{String(v ?? "—")}</dd>
                  </div>
                ))}
            </dl>
          </CardBody>
        </Card>
      )}

      {/* Per docs/contract-lifecycle-policy.md §5, negotiation resolves to
          internal_review only when the counterparty accepts the sent
          counterproposal. An authorized legal/executive user can also
          record that agreement was reached out-of-band via the
          "Record Agreement Reached" override below — it fires the exact
          same LifecycleService transition, just triggered internally
          instead of by the counterparty's public click. */}
      {draft.workflow_status === "sent_to_client" && (
        <div className="rounded-card border border-info-200/80 bg-info-50/60 p-3">
          <p className="text-sm font-semibold text-info-900">{t("negotiation.waitingForClient")}</p>
          <p className="mt-1 text-xs text-info-800">{t("negotiation.waitingForClientBody")}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {typeof draft.final_summary?.review_link === "string" && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => copyText(draft.final_summary!.review_link as string)}
              >
                {t("negotiation.copyClientLink")}
              </Button>
            )}
            {canRecordAgreement && (
              <Button variant="primary" size="sm" loading={busy} onClick={recordAgreement}>
                {t("negotiation.recordAgreement")}
              </Button>
            )}
            {row.actionable !== false && !row.is_stale && (
              <Button variant="danger" size="sm" loading={busy} onClick={abandon}>
                {t("negotiation.abandon")}
              </Button>
            )}
          </div>
        </div>
      )}

      {row.actionable !== false && !row.is_stale && row.workflow_status !== "sent_to_client" && row.status !== "sent" && (
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" size="sm" loading={busy} onClick={() => save({ status: "approved" })}>
            {t("negotiation.approve")}
          </Button>
          <Button variant="primary" size="sm" loading={busy} onClick={send}>
            {t("negotiation.send")}
          </Button>
          {canRecordAgreement && (
            <Button variant="primary" size="sm" loading={busy} onClick={recordAgreement}>
              {t("negotiation.recordAgreement")}
            </Button>
          )}
          <Button variant="danger" size="sm" loading={busy} onClick={abandon}>
            {t("negotiation.abandon")}
          </Button>
        </div>
      )}
    </div>
  );
}

export default function NegotiationPanel({
  contractId,
  contractStage,
  highlightId,
  onLifecycleChanged,
  onGoToApproval,
}: {
  contractId: string;
  contractStage?: string | null;
  highlightId?: string | null;
  onLifecycleChanged?: () => void | Promise<void>;
  onGoToApproval?: () => void;
}) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [candidates, setCandidates] = useState<NegotiationCandidate[]>([]);
  const [analyzingKey, setAnalyzingKey] = useState<string | null>(null);
  const [role, setRole] = useState("legal");
  // Owned here, not in NegotiationResult: `onUpdated()` (passed to that
  // child) triggers `load()` below, which unmounts/remounts every candidate
  // card via the `loading` skeleton gate. This component instance does not
  // unmount, so the "resolved" banner survives that refresh.
  const [agreementResolved, setAgreementResolved] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    fetchNegotiations(contractId)
      .then((r) => setCandidates(r.candidates))
      .catch(() => setCandidates([]))
      .finally(() => setLoading(false));
  }, [contractId]);

  useEffect(load, [load]);

  useEffect(() => {
    const saved = localStorage.getItem(DEMO_ROLE_STORAGE);
    if (saved) setRole(saved);
    const onRoleChange = () => setRole(localStorage.getItem(DEMO_ROLE_STORAGE) || "legal");
    window.addEventListener(DEMO_ROLE_EVENT, onRoleChange);
    return () => window.removeEventListener(DEMO_ROLE_EVENT, onRoleChange);
  }, []);

  const analyze = async (c: NegotiationCandidate) => {
    const key = `${c.review_id}-${c.comment_id ?? "overall"}`;
    setAnalyzingKey(key);
    try {
      await analyzeNegotiation(c.review_id, c.comment_id);
      load();
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
    } finally {
      setAnalyzingKey(null);
    }
  };

  if (loading) return <SkeletonCard rows={3} />;
  if (candidates.length === 0) return <EmptyState title={t("negotiation.empty")} />;

  return (
    <div className="space-y-4">
      {agreementResolved && (
        <div className="rounded-card border border-success-200/80 bg-success-50/60 p-3">
          <p className="text-sm font-semibold text-success-700">{t("negotiation.recordAgreementResolved")}</p>
          {onGoToApproval && (
            <Button variant="secondary" size="sm" className="mt-2" onClick={onGoToApproval}>
              {t("negotiation.goToApproval")}
            </Button>
          )}
        </div>
      )}
      {candidates.map((c) => {
        const key = `${c.review_id}-${c.comment_id ?? "overall"}`;
        const neg = c.negotiation;
        return (
          <Card key={key} className={cn(c.negotiation?.id === highlightId && "ring-2 ring-brand-500/40")}>
            <CardBody>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex-1">
                  {neg && (
                    <Badge tone="info" className="mb-2">
                      {t(wsKey(neg.workflow_status || "pending_analysis"))}
                    </Badge>
                  )}
                  {c.clause_ref && (
                    <p className="text-xs font-semibold text-brand-700">{c.clause_ref}</p>
                  )}
                  <p className="mt-1 text-sm font-medium text-gray-900">{t("negotiation.reviewerComment")}</p>
                  <p className="text-sm text-gray-700">{c.reviewer_comment}</p>
                </div>
                <Badge tone={c.review_status === "rejected" ? "danger" : "warning"}>{c.review_status}</Badge>
              </div>
              {(neg?.original_clause || c.original_clause) && (
                <div className="mt-3 rounded-lg border bg-muted-50/50 p-3">
                  <p className="mb-1 text-xs font-semibold uppercase text-gray-500">{t("negotiation.originalClause")}</p>
                  <p className="text-sm text-gray-800">{neg?.original_clause || c.original_clause}</p>
                </div>
              )}
              {!neg?.ai_summary && (
                <Button
                  variant="primary"
                  size="sm"
                  className="mt-4"
                  loading={analyzingKey === key}
                  onClick={() => analyze(c)}
                >
                  {analyzingKey === key ? t("negotiation.analyzing") : t("negotiation.analyze")}
                </Button>
              )}
              {neg?.ai_summary && (
                <NegotiationResult
                  row={neg}
                  lang={lang}
                  contractStage={contractStage}
                  role={role}
                  onUpdated={load}
                  onLifecycleChanged={onLifecycleChanged}
                  onAgreementResolved={() => setAgreementResolved(true)}
                  onRestart={
                    neg.is_stale && c.review_id
                      ? () => analyze(c)
                      : undefined
                  }
                />
              )}
            </CardBody>
          </Card>
        );
      })}
    </div>
  );
}
