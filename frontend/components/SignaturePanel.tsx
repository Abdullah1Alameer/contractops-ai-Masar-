"use client";
import { useCallback, useEffect, useState } from "react";

import CreateSignatureDialog from "@/components/CreateSignatureDialog";
import { useConfirm } from "@/components/feedback/ConfirmDialog";
import { useToast } from "@/components/feedback/ToastProvider";
import { DeliveryStatusBadge } from "@/components/SendForReviewDialog";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonCard } from "@/components/ui/Skeleton";
import {
  apiErrorCode,
  cancelSignatureRequest,
  activateSignatureRequest,
  createSignatureRequest,
  downloadSignatureCertificate,
  downloadSignedPdf,
  fetchSignatureBundle,
  resendSignatureSigner,
  sendSignatureRequest,
} from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { SignatureBundleResponse, SignatureRequestRow } from "@/lib/types";
import { cn } from "@/lib/utils";

const FIELD_CLASS =
  "w-full rounded-lg border border-gray-300 bg-white p-2 text-sm text-gray-900 placeholder:text-gray-400 focus-visible:focus-ring disabled:bg-muted-50 disabled:text-gray-400";

function statusKey(s: string): TKey {
  return `signature.status.${s}` as TKey;
}

export default function SignaturePanel({
  contractId,
  contractStage,
  highlightId,
  onLifecycleChange,
}: {
  contractId: string;
  contractStage?: string;
  highlightId?: string | null;
  onLifecycleChange?: () => void | Promise<void>;
}) {
  const { t } = useI18n();
  const { confirm } = useConfirm();
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [bundle, setBundle] = useState<SignatureBundleResponse | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const [lastLink, setLastLink] = useState<string | null>(null);
  const [activated, setActivated] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [activationReason, setActivationReason] = useState("");
  const [activationEvidence, setActivationEvidence] = useState("");
  const busy = pending !== null;

  const load = useCallback(() => {
    setLoading(true);
    fetchSignatureBundle(contractId)
      .then(setBundle)
      .catch(() => setBundle(null))
      .finally(() => setLoading(false));
  }, [contractId]);

  useEffect(load, [load]);
  useEffect(() => setActivated(false), [contractId]);

  const req = bundle?.request;
  const canCreate =
    (bundle?.can_create ?? (contractStage === "approved" || contractStage === "ready_to_sign")) &&
    !req?.status?.match(/partially_signed|completed/);
  // Executed artifacts follow the request, not the stage, so they stay reachable from
  // `signed` through `active` and every later stage. Only activation is stage-gated.
  const completed = req?.status === "completed";
  const showSignedDownload = completed && req?.signed_file_url !== null;
  const showCertificateDownload = completed && req?.certificate_file_url !== null;
  const showActivation = completed && contractStage === "signed" && !activated;

  const create = async (body: Parameters<typeof createSignatureRequest>[1]) => {
    setPending("create");
    try {
      const out = await createSignatureRequest(contractId, body);
      const link = (out as { signer_links?: { signer_link: string }[] }).signer_links?.[0]?.signer_link;
      if (link) setLastLink(link);
      setDialogOpen(false);
      load();
      toast.success(t("signature.create"));
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
    } finally {
      setPending(null);
    }
  };

  const send = () => {
    if (!req) return;
    confirm({
      title: t("signature.send"),
      body: t("signature.title"),
      confirmLabel: t("signature.send"),
      onConfirm: async () => {
        setPending("send");
        try {
          const out = await sendSignatureRequest(req.id);
          load();
          // The request/link is always persisted at this point; only the invitation
          // email itself may have failed, so success must reflect actual delivery.
          const failed = (out.deliveries ?? []).some((d) => d.status === "failed");
          if (failed) {
            toast.error(t("signature.deliveryFailed"));
          } else {
            toast.success(t("signature.sent"));
          }
          await onLifecycleChange?.();
        } catch (error) {
          toast.error(apiErrorCode(error, t("common.error")));
          throw new Error("send failed");
        } finally {
          setPending(null);
        }
      },
    });
  };

  const cancel = async () => {
    if (!req) return;
    if (!cancelReason.trim()) {
      toast.error(t("signature.cancelReasonRequired"));
      return;
    }
    setPending("cancel");
    try {
      await cancelSignatureRequest(req.id, cancelReason.trim());
      setCancelReason("");
      load();
      toast.success(t("signature.cancelled"));
      await onLifecycleChange?.();
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
    } finally {
      setPending(null);
    }
  };

  const activate = async () => {
    if (!req) return;
    if (!activationReason.trim()) {
      toast.error(t("signature.activationReasonRequired"));
      return;
    }
    if (!activationEvidence.trim()) {
      toast.error(t("signature.activationEvidenceRequired"));
      return;
    }
    setPending("activate");
    try {
      await activateSignatureRequest(req.id, activationReason.trim(), activationEvidence.trim());
      setActivationReason("");
      setActivationEvidence("");
      setActivated(true);
      load();
      toast.success(t("signature.activated"));
      await onLifecycleChange?.();
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
    } finally {
      setPending(null);
    }
  };

  const download = async (kind: "signed" | "certificate") => {
    if (!req) return;
    setPending(`download-${kind}`);
    try {
      const blob = kind === "signed"
        ? await downloadSignedPdf(req.id)
        : await downloadSignatureCertificate(req.id);
      window.open(URL.createObjectURL(blob), "_blank");
    } catch (error) {
      toast.error(apiErrorCode(error, t("signature.downloadFailed")));
    } finally {
      setPending(null);
    }
  };

  if (loading) return <SkeletonCard rows={3} />;
  if (!req && !canCreate) return <EmptyState title={t("signature.title")} />;

  return (
    <div className={cn("space-y-4", highlightId && req?.id === highlightId && "rounded-card ring-2 ring-brand-500/40 p-2")}>
      <div className="flex flex-wrap gap-2">
        {canCreate && (
          <Button variant="primary" size="sm" disabled={busy} onClick={() => setDialogOpen(true)}>
            {t("signature.create")}
          </Button>
        )}
        {req && ["draft", "created"].includes(req.status) && (
          <Button variant="primary" size="sm" loading={pending === "send"} disabled={busy} onClick={send}>
            {t("signature.send")}
          </Button>
        )}
        {showSignedDownload && (
          <Button
            variant="secondary"
            size="sm"
            loading={pending === "download-signed"}
            disabled={busy}
            onClick={() => download("signed")}
          >
            {t("signature.downloadSigned")}
          </Button>
        )}
        {showCertificateDownload && (
          <Button
            variant="secondary"
            size="sm"
            loading={pending === "download-certificate"}
            disabled={busy}
            onClick={() => download("certificate")}
          >
            {t("signature.downloadCert")}
          </Button>
        )}
        {lastLink && (
          <Button
            variant="secondary"
            size="sm"
            onClick={async () => {
              await navigator.clipboard.writeText(lastLink);
              toast.success(t("negotiation.copied"));
            }}
          >
            {t("signature.copyLink")}
          </Button>
        )}
      </div>

      {req && !["completed", "declined", "cancelled", "expired"].includes(req.status) && (
        <Card>
          <CardBody className="space-y-3">
            <h4 className="font-semibold">{t("signature.cancelTitle")}</h4>
            <input
              className={FIELD_CLASS}
              aria-label={t("signature.cancelReason")}
              placeholder={t("signature.cancelReason")}
              value={cancelReason}
              disabled={busy}
              onChange={(e) => setCancelReason(e.target.value)}
            />
            <Button
              variant="secondary"
              size="sm"
              loading={pending === "cancel"}
              disabled={busy}
              onClick={cancel}
            >
              {t("signature.cancel")}
            </Button>
          </CardBody>
        </Card>
      )}

      {showActivation && (
        <Card>
          <CardBody className="space-y-3">
            <h4 className="font-semibold">{t("signature.activationTitle")}</h4>
            <input
              className={FIELD_CLASS}
              aria-label={t("signature.activationReason")}
              placeholder={t("signature.activationReason")}
              value={activationReason}
              disabled={busy}
              onChange={(e) => setActivationReason(e.target.value)}
            />
            <input
              className={FIELD_CLASS}
              aria-label={t("signature.activationEvidence")}
              placeholder={t("signature.activationEvidence")}
              value={activationEvidence}
              disabled={busy}
              onChange={(e) => setActivationEvidence(e.target.value)}
            />
            <Button
              variant="primary"
              size="sm"
              loading={pending === "activate"}
              disabled={busy}
              onClick={activate}
            >
              {t("signature.activate")}
            </Button>
          </CardBody>
        </Card>
      )}

      {req && (
        <>
          {req.is_stale && (
            <p className="rounded-lg border border-warning-200 bg-warning-50 p-3 text-sm text-warning-900">{t("versions.stale")}</p>
          )}
          <RequestView
            req={req}
            t={t}
            busy={busy}
            onResend={async (signerId) => {
              setPending(`resend-${signerId}`);
              try {
                const r = await resendSignatureSigner(req.id, signerId);
                setLastLink(r.signer_link);
                // Persist honesty about delivery: a resend that fails to reach the
                // signer must never be reported as a successful send.
                if (r.delivery?.status === "failed") {
                  toast.error(t("signature.deliveryFailed"));
                } else {
                  toast.success(t("signature.deliverySent"));
                }
                load();
              } catch (error) {
                toast.error(apiErrorCode(error, t("common.error")));
              } finally {
                setPending(null);
              }
            }}
            onCopyLink={async (link) => {
              await navigator.clipboard.writeText(link);
              toast.success(t("common.copied"));
            }}
          />
        </>
      )}

      {bundle?.events && bundle.events.length > 0 && (
        <Card>
          <CardBody>
            <h4 className="mb-2 font-semibold">{t("activity.title")}</h4>
            <ul className="space-y-1 text-sm text-gray-700">
              {bundle.events.map((e) => (
                <li key={e.id}>
                  {e.created_at?.slice(0, 19)} — {e.action}
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}

      <CreateSignatureDialog open={dialogOpen} onClose={() => setDialogOpen(false)} onSubmit={create} busy={busy} />
    </div>
  );
}

function RequestView({
  req,
  t,
  busy,
  onResend,
  onCopyLink,
}: {
  req: SignatureRequestRow;
  t: (k: TKey) => string;
  busy: boolean;
  onResend: (signerId: string) => void;
  onCopyLink: (link: string) => void;
}) {
  return (
    <Card>
      <CardBody className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="info">{t(statusKey(req.status))}</Badge>
          <Badge tone="neutral">{t("signature.demoLabel")}</Badge>
        </div>
        <p className="text-sm">
          <span className="font-semibold">{req.subject}</span>
        </p>
        <p className="text-sm text-gray-600">
          {t("signature.progress")
            .replace("{done}", String(req.progress.completed))
            .replace("{total}", String(req.progress.total))}
        </p>
        <ol className="space-y-2">
          {req.signers.map((s) => (
            <li key={s.id} className="flex flex-col gap-2 rounded border p-2 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {s.signer_order}. {s.name} — {t(`signature.role.${s.role}` as TKey)} — {t(statusKey(s.status))}
                </span>
                {/* Only the currently eligible (invited/opened) signer exposes Retry
                    and Copy Link — future, not-yet-invited signers get no invite
                    action, matching the resend endpoint's own eligibility guard. */}
                {s.eligible && (
                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" disabled={busy} onClick={() => onResend(s.id)}>
                      {t("signature.resend")}
                    </Button>
                    {s.signer_link && (
                      <Button variant="secondary" size="sm" disabled={busy} onClick={() => onCopyLink(s.signer_link!)}>
                        {t("signature.copyLink")}
                      </Button>
                    )}
                  </div>
                )}
              </div>
              {s.delivery && (
                <div className="flex flex-wrap items-center gap-2 text-xs text-gray-600">
                  <DeliveryStatusBadge status={s.delivery.status} />
                  <span>
                    {t("delivery.attempts")}: {s.delivery.attempt_count}
                  </span>
                  {s.delivery.status === "sent" && s.delivery.sent_at && (
                    <span>
                      {t("delivery.sentAt")}: {s.delivery.sent_at.slice(0, 19)}
                    </span>
                  )}
                  {s.delivery.status === "failed" && (
                    <span>
                      {t("delivery.failedAt")}: {s.delivery.failed_at?.slice(0, 19) ?? "—"}
                      {s.delivery.safe_error_code ? ` · ${s.delivery.safe_error_code}` : ""}
                    </span>
                  )}
                </div>
              )}
            </li>
          ))}
        </ol>
      </CardBody>
    </Card>
  );
}
