"use client";
import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import Logo from "@/components/Logo";
import SignatureCanvas from "@/components/SignatureCanvas";
import SignerDocumentViewer from "@/components/SignerDocumentViewer";
import TypedSignaturePreview from "@/components/TypedSignaturePreview";
import { useToast } from "@/components/feedback/ToastProvider";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import {
  apiErrorCode,
  declineSignerPortal,
  openSignerPortal,
  publicSignDocumentUrl,
  submitSignerPortal,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { SignerPublicPayload } from "@/lib/types";
import { formatDate, formatNum } from "@/lib/utils";

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
  // Gate: the signer must have jumped to/seen every one of their required
  // fields at least once before submit is enabled — "field cannot be
  // submitted before being completed" applies to the whole set, not just
  // the signature capture widget.
  const [allFieldsViewed, setAllFieldsViewed] = useState(false);

  // A single deterministic entry point for both the initial mount and manual
  // retry. `open` re-validates staleness/expiry/eligibility on every call (it is
  // safe to repeat once already opened), so a rejection here must be surfaced
  // immediately — never silently swapped for a second, less-strict read that
  // could mask a real `workflow_stale`/`expired`/`not_active_signer` error.
  const load = useCallback(() => {
    setErrorCode(null);
    openSignerPortal(token)
      .then(setData)
      .catch((caught) => setErrorCode(apiErrorCode(caught, "unknown")));
  }, [token]);

  useEffect(load, [load]);

  const submit = async () => {
    if (!data || !consent) return;
    if (data.fields.length > 0 && !allFieldsViewed) return;
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
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#F8FAFC] p-8 text-center">
        <PrototypeDisclosure />
        <div className="glass-card mx-auto w-full max-w-lg space-y-4 p-8">
          <p className="text-danger-600">{t("signature.errorWithCode").replace("{code}", errorCode)}</p>
          <Button variant="secondary" onClick={load}>
            {t("common.retry")}
          </Button>
        </div>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#F8FAFC] p-8 text-center">
        <PrototypeDisclosure />
        <p className="text-sm font-medium text-slate-500">{t("common.loading")}</p>
      </div>
    );
  }

  const consentLabel = lang === "ar" ? data.consent_text.ar : data.consent_text.en;

  if (data.declined) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#F8FAFC] p-8 text-center">
        <PrototypeDisclosure />
        <div className="glass-card mx-auto w-full max-w-lg space-y-4 p-8">
          <h1 className="text-xl font-extrabold tracking-tight text-slate-900">{t("signature.declinedState")}</h1>
        </div>
      </div>
    );
  }

  if (data.read_only && data.signer.status === "signed") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#F8FAFC] p-8 text-center">
        <PrototypeDisclosure />
        <div className="glass-card mx-auto w-full max-w-lg space-y-4 p-8">
          <h1 className="text-xl font-extrabold tracking-tight text-emerald-700">{t("signature.completed")}</h1>
          <p className="text-sm font-medium text-slate-500">{formatDate(data.signer.signed_at, lang)}</p>
        </div>
      </div>
    );
  }

  if (data.waiting_for_prior) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-[#F8FAFC] p-8 text-center">
        <PrototypeDisclosure />
        <div className="glass-card mx-auto w-full max-w-lg space-y-4 p-8">
          <p className="text-sm font-medium text-slate-600">{t("signature.waitingPrior")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen bg-[#F8FAFC] pb-24">
      {/* Same ambient wash the authenticated shell uses, so the public signing
          page reads as the same product rather than a bare form. */}
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden>
        <div className="absolute -top-40 end-[-6rem] h-96 w-96 rounded-full bg-emerald-100/50 blur-[100px]" />
        <div className="absolute bottom-[-10rem] start-[-8rem] h-[28rem] w-[28rem] rounded-full bg-teal-50/60 blur-[120px]" />
      </div>

      <PrototypeDisclosure />
      <header className="border-b border-white bg-white/70 px-4 py-6 backdrop-blur-2xl">
        <div className="mx-auto max-w-4xl space-y-3">
          <div className="flex items-center justify-between gap-4">
            <Logo size="sm" tone="brand" />
            <Badge tone="subtle">{t("signature.demoLabel")}</Badge>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">{data.subject}</h1>
          <p className="text-sm font-medium text-slate-500">
            {data.sender_name} · {data.contract_title}
          </p>
          <div className="flex flex-wrap gap-2">
            <span className="chip chip-active tnum">
              {formatNum(data.progress.completed, lang)}/{formatNum(data.progress.total, lang)}
            </span>
            <span className="chip">{data.signer.name}</span>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-8">
      <Card>
        <CardBody className="space-y-2 p-2">
          <p className="mb-2 px-2 text-xs text-gray-500">{t("signature.tab")}</p>
          <SignerDocumentViewer
            documentUrl={publicSignDocumentUrl(token)}
            fields={data.fields}
            onAllFieldsViewed={() => setAllFieldsViewed(true)}
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
                className="w-full rounded-xl border border-slate-200 bg-white/80 px-3.5 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/20"
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
            className="w-full rounded-xl border border-slate-200 bg-white/80 px-3.5 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/20"
            placeholder={t("signature.nameConfirm")}
            value={nameConfirm}
            onChange={(e) => setNameConfirm(e.target.value)}
          />
          {data.fields.length > 0 && !allFieldsViewed && (
            <p className="text-xs font-medium text-amber-700">{t("signature.fields.viewAllFirst")}</p>
          )}
          <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-white/95 p-4 shadow-lg backdrop-blur md:static md:border-0 md:bg-transparent md:p-0 md:shadow-none">
            <Button
              variant="primary"
              className="w-full md:w-auto"
              loading={busy}
              disabled={data.fields.length > 0 && !allFieldsViewed}
              onClick={submit}
            >
              {t("signature.signSubmit")}
            </Button>
          </div>
          <textarea
            className="w-full rounded-xl border border-slate-200 bg-white/80 px-3.5 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-emerald-400 focus:ring-2 focus:ring-emerald-500/20"
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
