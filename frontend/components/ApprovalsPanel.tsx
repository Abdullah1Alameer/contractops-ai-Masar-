"use client";
import { useCallback, useEffect, useState } from "react";

import ApprovalRouteBuilder from "@/components/ApprovalRouteBuilder";
import { useConfirm } from "@/components/feedback/ConfirmDialog";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import SectionHeader from "@/components/ui/SectionHeader";
import Timeline from "@/components/ui/Timeline";
import ProgressBar from "@/components/ui/ProgressBar";
import { SkeletonCard } from "@/components/ui/Skeleton";
import {
  apiErrorCode,
  cancelApproval,
  DEMO_ROLE_EVENT,
  fetchActivity,
  fetchApprovals,
  fetchContractApprovalRoute,
  patchApprovalStep,
  startApproval,
} from "@/lib/api";
import { useToast } from "@/components/feedback/ToastProvider";
import { useI18n, type TKey } from "@/lib/i18n";
import { mapActivityEvents } from "@/lib/activity";
import type { ActivityEventRow, ApprovalWorkflowView, ContractApprovalRoute } from "@/lib/types";
import { cn } from "@/lib/utils";

function roleLabel(t: (k: TKey) => string, role: string): string {
  return t(`role.${role}` as TKey);
}

export default function ApprovalsPanel({
  contractId,
  contractStage,
  highlightId,
  onLifecycleChange,
  onGoToNegotiation,
}: {
  contractId: string;
  contractStage?: string;
  highlightId?: string | null;
  onLifecycleChange?: () => void;
  onGoToNegotiation?: () => void;
}) {
  const { t, lang } = useI18n();
  const { confirm } = useConfirm();
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [workflow, setWorkflow] = useState<ApprovalWorkflowView | null>(null);
  const [contractRoute, setContractRoute] = useState<ContractApprovalRoute | null>(null);
  const [unresolved, setUnresolved] = useState<{ id: string }[]>([]);
  const [events, setEvents] = useState<ActivityEventRow[]>([]);
  const [comment, setComment] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [editingRoute, setEditingRoute] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([fetchApprovals(contractId), fetchActivity(contractId), fetchContractApprovalRoute(contractId)])
      .then(([a, ev, r]) => {
        setWorkflow(a.workflow);
        setUnresolved(a.unresolved_negotiations ?? []);
        setEvents(ev.events ?? []);
        setContractRoute(r.route);
      })
      .catch(() => {
        setWorkflow(null);
        setUnresolved([]);
        setContractRoute(null);
      })
      .finally(() => setLoading(false));
  }, [contractId]);

  useEffect(load, [load]);
  useEffect(() => {
    const h = () => load();
    window.addEventListener(DEMO_ROLE_EVENT, h);
    return () => window.removeEventListener(DEMO_ROLE_EVENT, h);
  }, [load]);

  const active = workflow?.status === "in_progress";
  const blocked = unresolved.length > 0;
  // Canonical precondition only (docs/contract-lifecycle-policy.md §6 "Start
  // conditions"): stage must be internal_review. No fallback for a missing
  // stage — an unknown stage must never be treated as "start is allowed".
  const canConfigure = !active && !blocked && contractStage === "internal_review";
  const actionable = workflow?.actionable ?? false;
  const hasDraftRoute = contractRoute?.status === "draft" && (contractRoute.steps?.length ?? 0) > 0;

  const onRouteConfigured = () => {
    setEditingRoute(false);
    load();
  };

  const startWorkflow = () => {
    confirm({
      title: t("approval.startTitle"),
      body: t("approval.startBody"),
      confirmLabel: t("approval.routeBuilder.startWorkflow"),
      onConfirm: () => {
        setBusy(true);
        startApproval(contractId)
          .then((w) => {
            setWorkflow(w);
            load();
            onLifecycleChange?.();
          })
          .catch((error) => toast.error(apiErrorCode(error, t("common.error"))))
          .finally(() => setBusy(false));
      },
    });
  };

  const act = async (status: string) => {
    if (!workflow?.current_step || !actionable) return;
    if ((status === "rejected" || status === "changes_requested") && !comment.trim()) return;
    setBusy(true);
    try {
      const w = await patchApprovalStep(workflow.current_step.id, { status, comment: comment || undefined });
      setWorkflow(w);
      setComment("");
      load();
      onLifecycleChange?.();
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!cancelReason.trim()) return;
    setBusy(true);
    try {
      await cancelApproval(contractId, cancelReason.trim());
      setCancelReason("");
      load();
      onLifecycleChange?.();
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <SkeletonCard rows={4} />;
  if (!workflow && !canConfigure && !blocked) {
    return (
      <EmptyState
        title={t("approval.empty")}
        description={
          contractStage
            ? `${t("approval.requiresInternalReview")} ${t(`stage.${contractStage}` as import("@/lib/i18n").TKey)}`
            : undefined
        }
        actionLabel={contractStage === "negotiation" && onGoToNegotiation ? t("approval.goToNegotiation") : undefined}
        onAction={contractStage === "negotiation" ? onGoToNegotiation : undefined}
      />
    );
  }

  return (
    <div className={cn("space-y-6", highlightId && workflow?.id === highlightId && "rounded-card ring-2 ring-brand-500/40 p-2")}>
      {!active && blocked && (
        <div className="rounded-lg border border-warning-200 bg-warning-50 p-3 text-sm text-warning-900">
          <p>
            <span className="font-semibold">{t("approval.unresolvedWarning")}</span> {t("approval.unresolvedBody")}
          </p>
          {onGoToNegotiation && (
            <Button variant="secondary" size="sm" className="mt-2" onClick={onGoToNegotiation}>
              {t("approval.goToNegotiation")}
            </Button>
          )}
        </div>
      )}

      {/* No workflow yet: configure (or resume configuring) the route, then
          start it explicitly — never a generic button that silently creates
          a hardcoded sequence. See docs/configurable-approval-routes-report.md. */}
      {canConfigure && (!hasDraftRoute || editingRoute) && (
        <ApprovalRouteBuilder
          contractId={contractId}
          initialDraft={contractRoute?.status === "draft" ? contractRoute : null}
          onConfigured={onRouteConfigured}
        />
      )}

      {canConfigure && hasDraftRoute && !editingRoute && contractRoute && (
        <Card>
          <CardBody className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-bold">{contractRoute.name || t("approval.configureRoute")}</h3>
              <Badge tone="info">{t("approval.workflowType.sequential")}</Badge>
            </div>
            <ol className="space-y-1 text-sm text-neutral-800">
              {contractRoute.steps.map((s) => (
                <li key={s.id}>
                  {s.step_order}. {roleLabel(t, s.role)}
                  {s.approver_name && ` — ${s.approver_name}`}
                  {!s.required && ` (${t("approval.routeBuilder.optionalTag")})`}
                </li>
              ))}
            </ol>
            <div className="flex flex-wrap gap-2">
              <Button variant="primary" loading={busy} onClick={startWorkflow}>
                {t("approval.routeBuilder.startWorkflow")}
              </Button>
              <Button variant="secondary" onClick={() => setEditingRoute(true)}>
                {t("approval.routeBuilder.customize")}
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {workflow?.is_stale && (
        <p className="rounded-lg border border-warning-200 bg-warning-50 p-3 text-sm text-warning-900">{t("versions.stale")}</p>
      )}

      {workflow && (
        <>
          <Card>
            <CardBody className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="font-bold">{workflow.route_name || t("approval.title")}</h3>
                  {workflow.workflow_type && (
                    <p className="text-xs text-neutral-500">{t(`approval.workflowType.${workflow.workflow_type}` as TKey)}</p>
                  )}
                </div>
                <Badge tone={workflow.status === "approved" ? "success" : workflow.status === "in_progress" ? "info" : "warning"}>
                  {t(`approval.workflow.${workflow.status}` as TKey)}
                </Badge>
              </div>
              <div className="grid gap-2 text-sm text-gray-600 sm:grid-cols-3">
                <p>{t("approval.started")}: {workflow.started_at?.slice(0, 16) ?? "—"}</p>
                <p>{t("approval.approvedCount")}: {workflow.approved_count}</p>
                <p>{t("approval.remainingCount")}: {workflow.remaining_count}</p>
              </div>
              {/* Total is always workflow.steps.length — never assumed to be
                  four. A one-step or six-step route renders identically. */}
              <ProgressBar
                value={workflow.approved_count}
                max={workflow.steps.length || 1}
                tone="brand"
                label={t("dashboard.section.approvalProgress")}
              />
              <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {workflow.steps.map((step) => {
                  const isCurrent = step.step_order === workflow.current_step_order && step.status === "pending";
                  const outOfOrder = step.status === "locked" && step.step_order < workflow.current_step_order;
                  return (
                    <li
                      key={step.id}
                      className={cn(
                        "surface-card p-4 text-sm",
                        isCurrent && "ring-2 ring-brand-600/30",
                        step.status === "approved" && "border-success-200/80"
                      )}
                    >
                      <p className="text-xs font-semibold uppercase text-neutral-400">{step.step_order}</p>
                      <p className="font-semibold text-neutral-900">{roleLabel(t, step.role)}</p>
                      <p className="text-xs text-neutral-500">{step.approver_name ?? "—"}</p>
                      {step.required === false && (
                        <Badge tone="subtle" className="mt-1">{t("approval.routeBuilder.optionalTag")}</Badge>
                      )}
                      <p className="mt-2 text-xs font-medium">{t(`approval.step.${step.status}` as TKey)}</p>
                      {outOfOrder && <p className="text-xs text-warning-700">{t("approval.notActionable")}</p>}
                      {step.acted_at && <p className="text-xs text-neutral-400">{step.acted_at.slice(0, 16)}</p>}
                      {step.comment && <p className="mt-1 text-xs italic text-neutral-600">{step.comment}</p>}
                    </li>
                  );
                })}
              </ol>
            </CardBody>
          </Card>

          {actionable && workflow.allowed_actions.length > 0 && (
            <Card>
              <CardBody className="space-y-3">
                <h4 className="font-semibold">{t("approval.currentAction")}</h4>
                <textarea
                  className="w-full rounded-lg border p-2 text-sm"
                  rows={3}
                  placeholder={t("approval.commentPlaceholder")}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                />
                <div className="flex flex-wrap gap-2">
                  <Button variant="primary" size="sm" loading={busy} onClick={() => act("approved")}>
                    {t("approval.approve")}
                  </Button>
                  <Button variant="secondary" size="sm" loading={busy} onClick={() => act("changes_requested")}>
                    {t("approval.requestChanges")}
                  </Button>
                  <Button variant="danger" size="sm" loading={busy} onClick={() => act("rejected")}>
                    {t("approval.reject")}
                  </Button>
                </div>
              </CardBody>
            </Card>
          )}

          {active && !actionable && (
            <p className="text-sm text-neutral-500">
              {workflow.current_required_role
                ? `${t("approval.waitingFor")} ${roleLabel(t, workflow.current_required_role)}`
                : t("approval.notActionable")}
            </p>
          )}

          {active && (
            <Card>
              <CardBody className="space-y-3">
                <h4 className="font-semibold">{t("approval.cancel")}</h4>
                <input
                  className="w-full rounded-lg border p-2 text-sm"
                  placeholder={t("approval.cancelReasonPlaceholder")}
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                />
                <Button
                  variant="secondary"
                  size="sm"
                  loading={busy}
                  disabled={!cancelReason.trim()}
                  onClick={cancel}
                >
                  {t("approval.cancel")}
                </Button>
              </CardBody>
            </Card>
          )}
        </>
      )}

      {events.length > 0 && (
        <Card>
          <CardBody>
            <SectionHeader title={t("activity.title")} />
            <Timeline items={mapActivityEvents(events, t)} />
          </CardBody>
        </Card>
      )}
    </div>
  );
}
