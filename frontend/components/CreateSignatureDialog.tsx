"use client";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import Button from "@/components/ui/Button";
import { useI18n } from "@/lib/i18n";

type SignerDraft = { name: string; email: string; role: string; order: number };

const ROLES = ["company_signatory", "client_signatory", "witness", "reviewer", "other"] as const;

export default function CreateSignatureDialog({
  open,
  onClose,
  onSubmit,
  busy,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (body: {
    subject: string;
    message: string;
    expires_at: string;
    signing_order_enabled: boolean;
    signers: SignerDraft[];
  }) => void;
  busy?: boolean;
}) {
  const { t } = useI18n();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [orderEnabled, setOrderEnabled] = useState(true);
  const [signers, setSigners] = useState<SignerDraft[]>([
    { name: "", email: "", role: "company_signatory", order: 1 },
    { name: "", email: "", role: "client_signatory", order: 2 },
  ]);
  // Portal target isn't available during SSR/first paint — see the
  // rendering-fix note below.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!open || !mounted) return null;

  const defaultExpiry = () => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return d.toISOString();
  };

  const addSigner = () =>
    setSigners((s) => [...s, { name: "", email: "", role: "witness", order: s.length + 1 }]);

  // Rendering fix (layout/positioning only — no signature workflow logic
  // touched): this dialog used `position: fixed`, but was mounted inline
  // inside the contract page tree, under <PageTransition>'s framer-motion
  // wrapper (components/shell/PageTransition.tsx). A CSS `transform` on
  // any ancestor — which framer-motion applies to that wrapper for the
  // route entrance animation — creates a new containing block for
  // `position: fixed` descendants (CSS spec), so the dialog was being
  // positioned/clipped relative to that (possibly scrolled, shorter-than-viewport)
  // ancestor box instead of the real viewport: the backdrop still filled
  // whatever it was contained by (looked "correct"), but the centered
  // panel's top got clipped above the fold. Rendering through a portal to
  // document.body — the same fix already used by ConfirmDialog
  // (components/feedback/ConfirmDialog.tsx) — escapes that containing
  // block entirely, so `fixed inset-0` is always relative to the real
  // viewport regardless of any ancestor's transform/overflow/stacking
  // context. z-[110] matches ConfirmDialog's tier so stacking order stays
  // consistent across the app's portal-rendered dialogs.
  return createPortal(
    <div className="fixed inset-0 z-[110] flex items-center justify-center overflow-y-auto bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-signature-title"
        className="my-auto max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
      >
        <h3 id="create-signature-title" className="mb-4 text-lg font-bold">{t("signature.create")}</h3>
        <label className="block text-sm font-medium">{t("signature.subject")}</label>
        <input className="mb-3 w-full rounded border px-3 py-2 text-sm" value={subject} onChange={(e) => setSubject(e.target.value)} />
        <label className="block text-sm font-medium">{t("signature.message")}</label>
        <textarea className="mb-3 w-full rounded border px-3 py-2 text-sm" rows={2} value={message} onChange={(e) => setMessage(e.target.value)} />
        <label className="mb-3 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={orderEnabled} onChange={(e) => setOrderEnabled(e.target.checked)} />
          {t("signature.signingOrder")}
        </label>
        <p className="mb-2 text-sm font-semibold">{t("signature.signers")}</p>
        {signers.map((s, i) => (
          <div key={i} className="mb-2 grid gap-2 rounded border p-2 sm:grid-cols-2">
            <input
              placeholder={t("review.dashboard.recipient")}
              className="rounded border px-2 py-1 text-sm"
              value={s.name}
              onChange={(e) => setSigners((rows) => rows.map((r, j) => (j === i ? { ...r, name: e.target.value } : r)))}
            />
            <input
              type="email"
              placeholder="email"
              className="rounded border px-2 py-1 text-sm"
              value={s.email}
              onChange={(e) => setSigners((rows) => rows.map((r, j) => (j === i ? { ...r, email: e.target.value } : r)))}
            />
            <select
              className="rounded border px-2 py-1 text-sm sm:col-span-2"
              value={s.role}
              onChange={(e) => setSigners((rows) => rows.map((r, j) => (j === i ? { ...r, role: e.target.value } : r)))}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {t(`signature.role.${r}` as import("@/lib/i18n").TKey)}
                </option>
              ))}
            </select>
          </div>
        ))}
        <Button variant="secondary" size="sm" className="mb-4" onClick={addSigner}>
          +
        </Button>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            variant="primary"
            loading={busy}
            onClick={() =>
              onSubmit({
                subject,
                message,
                expires_at: defaultExpiry(),
                signing_order_enabled: orderEnabled,
                signers: signers.map((s, idx) => ({ ...s, order: idx + 1 })),
              })
            }
          >
            {t("signature.create")}
          </Button>
        </div>
      </div>
    </div>,
    document.body
  );
}
