"use client";
import { useCallback, useEffect, useState } from "react";

import CreateSignatureDialog from "@/components/CreateSignatureDialog";
import { useConfirm } from "@/components/feedback/ConfirmDialog";
import { useToast } from "@/components/feedback/ToastProvider";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import { SkeletonCard } from "@/components/ui/Skeleton";
import {
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

function statusKey(s: string): TKey {
  return `signature.status.${s}` as TKey;
}

export default function SignaturePanel({
  contractId,
  contractStage,
  highlightId,
}: {
  contractId: string;
  contractStage?: string;
  highlightId?: string | null;
}) {
  const { t } = useI18n();
  const { confirm } = useConfirm();
  const toast = useToast();
  const [loading, setLoading] = useState(true);
  const [bundle, setBundle] = useState<SignatureBundleResponse | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [lastLink, setLastLink] = useState<string | null>(null);
  const [activated, setActivated] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    fetchSignatureBundle(contractId)
      .then(setBundle)
      .catch(() => setBundle(null))
      .finally(() => setLoading(false));
  }, [contractId]);

  useEffect(load, [load]);

  const req = bundle?.request;
  const canCreate =
    (bundle?.can_create ?? (contractStage === "approved" || contractStage === "ready_to_sign")) &&
    !req?.status?.match(/partially_signed|completed/);

  const create = async (body: Parameters<typeof createSignatureRequest>[1]) => {
    setBusy(true);
    try {
      const out = await createSignatureRequest(contractId, body);
      const link = (out as { signer_links?: { signer_link: string }[] }).signer_links?.[0]?.signer_link;
      if (link) setLastLink(link);
      setDialogOpen(false);
      load();
      toast.success(t("signature.create"));
    } catch {
      toast.error(t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const send = () => {
    if (!req) return;
    confirm({
      title: t("signature.send"),
      body: t("signature.title"),
      confirmLabel: t("signature.send"),
      onConfirm: async () => {
        setBusy(true);
        try {
          await sendSignatureRequest(req.id);
          load();
        } catch {
          toast.error(t("common.error"));
          throw new Error("send failed");
        } finally {
          setBusy(false);
        }
      },
    });
  };

  if (loading) return <SkeletonCard rows={3} />;
  if (!req && !canCreate) return <EmptyState title={t("signature.title")} />;

  return (
    <div className={cn("space-y-4", highlightId && req?.id === highlightId && "rounded-card ring-2 ring-brand-500/40 p-2")}>
      <div className="flex flex-wrap gap-2">
        {canCreate && (
          <Button variant="primary" size="sm" onClick={() => setDialogOpen(true)}>
            {t("signature.create")}
          </Button>
        )}
        {req && ["draft", "created"].includes(req.status) && (
          <Button variant="primary" size="sm" loading={busy} onClick={send}>
            {t("signature.send")}
          </Button>
        )}
        {req && !["completed", "declined", "cancelled", "expired"].includes(req.status) && (
          <Button
            variant="secondary"
            size="sm"
            onClick={async () => {
              if (!req) return;
              const reason = window.prompt(t("signature.cancelReason"));
              if (!reason?.trim()) return;
              setBusy(true);
              try {
                await cancelSignatureRequest(req.id, reason.trim());
                load();
              } catch {
                toast.error(t("common.error"));
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("signature.cancel")}
          </Button>
        )}
        {req?.status === "completed" && (
          <>
            {!activated && <Button
              variant="primary"
              size="sm"
              onClick={async () => {
                const reason = window.prompt(t("signature.activationReason"));
                const evidence = reason ? window.prompt(t("signature.activationEvidence")) : null;
                if (!reason?.trim() || !evidence?.trim()) return;
                setBusy(true);
                try {
                  await activateSignatureRequest(req.id, reason.trim(), evidence.trim());
                  setActivated(true);
                  load();
                } catch {
                  toast.error(t("common.error"));
                } finally {
                  setBusy(false);
                }
              }}
            >
              {t("signature.activate")}
            </Button>
            }
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                const blob = await downloadSignedPdf(req.id);
                const url = URL.createObjectURL(blob);
                window.open(url, "_blank");
              }}
            >
              {t("signature.downloadSigned")}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                const blob = await downloadSignatureCertificate(req.id);
                const url = URL.createObjectURL(blob);
                window.open(url, "_blank");
              }}
            >
              {t("signature.downloadCert")}
            </Button>
          </>
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

      {req && (
        <>
          {req.is_stale && (
            <p className="rounded-lg border border-warning-200 bg-warning-50 p-3 text-sm text-warning-900">{t("versions.stale")}</p>
          )}
          <RequestView
            req={req}
            t={t}
            onResend={async (signerId) => {
              const r = await resendSignatureSigner(req.id, signerId);
              setLastLink(r.signer_link);
              toast.success(t("signature.resend"));
              load();
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
  onResend,
}: {
  req: SignatureRequestRow;
  t: (k: TKey) => string;
  onResend: (signerId: string) => void;
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
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded border p-2 text-sm">
              <span>
                {s.signer_order}. {s.name} — {t(`signature.role.${s.role}` as TKey)} — {s.status}
              </span>
              {s.status !== "signed" && (
                <Button variant="secondary" size="sm" onClick={() => onResend(s.id)}>
                  {t("signature.resend")}
                </Button>
              )}
            </li>
          ))}
        </ol>
      </CardBody>
    </Card>
  );
}
