"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import SignatureCanvas from "@/components/SignatureCanvas";
import TypedSignaturePreview from "@/components/TypedSignaturePreview";
import { useToast } from "@/components/feedback/ToastProvider";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import {
  apiErrorCode,
  declineSignerPortal,
  fetchSignerPortal,
  openSignerPortal,
  publicSignDocumentUrl,
  submitSignerPortal,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { SignerPublicPayload } from "@/lib/types";

type Method = "drawn" | "typed" | "uploaded";

// The demo prototype disclosure must stay visible on every state of this public
// page — loading, error, declined, completed, waiting, and the active signing
// form — and is intentionally identical text in both languages, not translated.
function PrototypeDisclosure() {
  const { t } = useI18n();
  return (
    <p className="mx-auto max-w-4xl px-4 pb-2 pt-3 text-center text-xs font-medium text-gray-500">
      {t("signature.demoDisclosure")}
    </p>
  );
}

export default function SignPage() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [data, setData] = useState<SignerPublicPayload | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [method, setMethod] = useState<Method>("drawn");
  const [drawn, setDrawn] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [consent, setConsent] = useState(false);
  const [nameConfirm, setNameConfirm] = useState("");
  const [declineReason, setDeclineReason] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setErrorCode(null);
    fetchSignerPortal(token)
      .then(setData)
      .catch((caught) => setErrorCode(apiErrorCode(caught, "unknown")));
  }, [token]);

  useEffect(() => {
    openSignerPortal(token)
      .then(setData)
      .catch(load);
  }, [token, load]);

  const submit = async () => {
    if (!data || !consent) return;
    let signature_value = "";
    if (method === "drawn") {
      if (!drawn) return;
      signature_value = drawn;
    } else if (method === "typed") {
      if (!typed.trim()) return;
      signature_value = typed.trim();
    }
    setBusy(true);
    try {
      const out = await submitSignerPortal(token, {
        signature_type: method === "typed" ? "typed" : "drawn",
        signature_value,
        consent_accepted: true,
        signer_name_confirmation: nameConfirm,
      });
      setData(out);
    } catch (caught) {
      toast.error(t("signature.errorWithCode").replace("{code}", apiErrorCode(caught, "unknown")));
    } finally {
      setBusy(false);
    }
  };

  const decline = async () => {
    if (!declineReason.trim()) return;
    setBusy(true);
    try {
      const out = await declineSignerPortal(token, declineReason);
      setData(out);
    } catch (caught) {
      toast.error(t("signature.errorWithCode").replace("{code}", apiErrorCode(caught, "unknown")));
    } finally {
      setBusy(false);
    }
  };

  if (errorCode) {
    return (
      <div className="mx-auto max-w-lg space-y-4 p-8 text-center">
        <PrototypeDisclosure />
        <p className="text-danger-600">{t("signature.errorWithCode").replace("{code}", errorCode)}</p>
        <Button variant="secondary" onClick={load}>
          {t("common.retry")}
        </Button>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="p-8 text-center">
        <PrototypeDisclosure />
        <p>{t("common.loading")}</p>
      </div>
    );
  }

  const consentLabel = lang === "ar" ? data.consent_text.ar : data.consent_text.en;

  if (data.declined) {
    return (
      <div className="mx-auto max-w-lg p-8 text-center">
        <PrototypeDisclosure />
        <h1 className="text-xl font-bold">{t("signature.declinedState")}</h1>
      </div>
    );
  }

  if (data.read_only && data.signer.status === "signed") {
    return (
      <div className="mx-auto max-w-lg space-y-4 p-8 text-center">
        <PrototypeDisclosure />
        <h1 className="text-xl font-bold text-success-700">{t("signature.completed")}</h1>
        <p className="text-sm text-gray-600">{data.signer.signed_at}</p>
      </div>
    );
  }

  if (data.waiting_for_prior) {
    return (
      <div className="mx-auto max-w-lg p-8 text-center">
        <PrototypeDisclosure />
        <p>{t("signature.waitingPrior")}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted-50/30 pb-24">
      <PrototypeDisclosure />
      <header className="border-b border-brand-100 bg-white px-4 py-6">
        <div className="mx-auto max-w-4xl space-y-3">
          <Badge tone="subtle">{t("signature.demoLabel")}</Badge>
          <h1 className="text-2xl font-bold text-gray-900">{data.subject}</h1>
          <p className="text-sm text-gray-600">
            {data.sender_name} · {data.contract_title}
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="chip chip-active">
              {data.progress.completed}/{data.progress.total}
            </span>
            <span className="chip">{data.signer.name}</span>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-8">
      <Card>
        <CardBody className="p-2">
          <p className="mb-2 px-2 text-xs text-gray-500">{t("signature.tab")}</p>
          <iframe
            title="document"
            src={publicSignDocumentUrl(token)}
            className="h-[55vh] w-full rounded-xl border-2 border-gray-200 bg-gray-50 shadow-inner"
          />
        </CardBody>
      </Card>

      <Card>
        <CardBody className="space-y-4">
          <p className="text-sm">
            {data.signer.name} — {t(`signature.role.${data.signer.role}` as import("@/lib/i18n").TKey)}
          </p>
          <div className="flex gap-2">
            <Button variant={method === "drawn" ? "primary" : "secondary"} size="sm" onClick={() => setMethod("drawn")}>
              {t("signature.draw")}
            </Button>
            <Button variant={method === "typed" ? "primary" : "secondary"} size="sm" onClick={() => setMethod("typed")}>
              {t("signature.type")}
            </Button>
          </div>
          {method === "drawn" && <SignatureCanvas onChange={setDrawn} />}
          {method === "typed" && (
            <>
              <input
                className="w-full rounded border px-3 py-2"
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
              />
              <TypedSignaturePreview value={typed} />
            </>
          )}
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            {consentLabel}
          </label>
          <input
            className="w-full rounded border px-3 py-2 text-sm"
            placeholder={t("signature.nameConfirm")}
            value={nameConfirm}
            onChange={(e) => setNameConfirm(e.target.value)}
          />
          <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-white/95 p-4 shadow-lg backdrop-blur md:static md:border-0 md:bg-transparent md:p-0 md:shadow-none">
            <Button variant="primary" className="w-full md:w-auto" loading={busy} onClick={submit}>
              {t("signature.signSubmit")}
            </Button>
          </div>
          <textarea
            className="w-full rounded border px-3 py-2 text-sm"
            placeholder={t("signature.decline")}
            value={declineReason}
            onChange={(e) => setDeclineReason(e.target.value)}
          />
          <Button variant="danger" size="sm" loading={busy} onClick={decline}>
            {t("signature.decline")}
          </Button>
        </CardBody>
      </Card>
      </div>
    </div>
  );
}
