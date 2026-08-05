"use client";
import { useState } from "react";

import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { apiErrorCode, sendContractForReview } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { SendReviewResponse } from "@/lib/types";

export default function SendForReviewDialog({
  contractId,
  disabled,
  onSent,
  triggerLabel,
}: {
  contractId: string;
  disabled?: boolean;
  onSent?: () => void;
  triggerLabel?: string;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [recipientName, setRecipientName] = useState("");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [message, setMessage] = useState("");
  const [senderName, setSenderName] = useState("");
  const [senderEmail, setSenderEmail] = useState("");
  const [expiresIn, setExpiresIn] = useState(14);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SendReviewResponse | null>(null);
  const [copied, setCopied] = useState(false);

  const reset = () => {
    setResult(null);
    setRecipientName("");
    setRecipientEmail("");
    setMessage("");
    setCopied(false);
    setError(null);
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await sendContractForReview(contractId, {
        recipient_name: recipientName,
        recipient_email: recipientEmail,
        message: message || undefined,
        sender_name: senderName || undefined,
        sender_email: senderEmail || undefined,
        expires_in_days: expiresIn,
      });
      setResult(res);
      onSent?.();
    } catch (caught) {
      setError(apiErrorCode(caught));
    } finally {
      setBusy(false);
    }
  };

  const copyLink = async () => {
    if (!result?.review_link) return;
    await navigator.clipboard.writeText(result.review_link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!open) {
    return (
      <Button variant="secondary" size="sm" disabled={disabled} onClick={() => { reset(); setOpen(true); }}>
        {triggerLabel ?? t("review.send.title")}
      </Button>
    );
  }

  return (
    <Card className="mb-4">
      <CardBody className="space-y-4">
        <h3 className="font-bold text-gray-900">{t("review.send.title")}</h3>
        {result ? (
          <div className="space-y-3">
            <p className="text-sm text-success-700">{t("review.send.success")}</p>
            <div className="flex flex-wrap gap-2">
              <code className="flex-1 break-all rounded-lg bg-muted-50 px-3 py-2 text-xs">{result.review_link}</code>
              <Button variant="secondary" size="sm" onClick={copyLink}>
                {copied ? t("review.send.copied") : t("review.send.copyLink")}
              </Button>
            </div>
            <div>
              <p className="mb-1 text-xs font-semibold uppercase text-gray-500">{t("review.send.emailPreview")}</p>
              <p className="text-sm font-medium">{result.email.subject}</p>
              <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg border bg-white p-3 text-xs text-gray-700">
                {result.email.body}
              </pre>
            </div>
            <Button variant="secondary" size="sm" onClick={() => { setOpen(false); reset(); }}>
              {t("common.cancel")}
            </Button>
          </div>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1 text-sm">
                {t("review.send.recipientName")}
                <input
                  className="rounded-lg border-2 border-gray-200 px-2 py-2 focus-visible:focus-ring"
                  value={recipientName}
                  onChange={(e) => setRecipientName(e.target.value)}
                />
              </label>
              <label className="grid gap-1 text-sm">
                {t("review.send.recipientEmail")}
                <input
                  type="email"
                  className="rounded-lg border-2 border-gray-200 px-2 py-2 focus-visible:focus-ring"
                  value={recipientEmail}
                  onChange={(e) => setRecipientEmail(e.target.value)}
                />
              </label>
              <label className="grid gap-1 text-sm">
                {t("review.send.senderName")}
                <input
                  className="rounded-lg border-2 border-gray-200 px-2 py-2 focus-visible:focus-ring"
                  value={senderName}
                  onChange={(e) => setSenderName(e.target.value)}
                />
              </label>
              <label className="grid gap-1 text-sm">
                {t("review.send.senderEmail")}
                <input
                  type="email"
                  className="rounded-lg border-2 border-gray-200 px-2 py-2 focus-visible:focus-ring"
                  value={senderEmail}
                  onChange={(e) => setSenderEmail(e.target.value)}
                />
              </label>
              <label className="grid gap-1 text-sm">
                {t("review.send.expiresIn")}
                <input
                  type="number"
                  min={1}
                  max={90}
                  className="rounded-lg border-2 border-gray-200 px-2 py-2 focus-visible:focus-ring"
                  value={expiresIn}
                  onChange={(e) => setExpiresIn(Number(e.target.value))}
                />
              </label>
              <label className="grid gap-1 text-sm sm:col-span-2">
                {t("review.send.message")}
                <textarea
                  rows={3}
                  className="rounded-lg border-2 border-gray-200 px-2 py-2 focus-visible:focus-ring"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                />
              </label>
            </div>
            {error && <p className="text-sm text-danger-600">{error}</p>}
            <div className="flex gap-2">
              <Button
                variant="primary"
                size="sm"
                loading={busy}
                disabled={!recipientName.trim() || !recipientEmail.trim()}
                onClick={submit}
              >
                {t("review.send.submit")}
              </Button>
              <Button variant="secondary" size="sm" onClick={() => { setOpen(false); reset(); }}>
                {t("common.cancel")}
              </Button>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}

export function ReviewStatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const key = `review.status.${status}` as TKey;
  const tone =
    status === "approved"
      ? "success"
      : status === "rejected"
        ? "danger"
        : status === "changes_requested"
          ? "warning"
          : status === "expired" || status === "cancelled"
            ? "neutral"
            : "info";
  return <Badge tone={tone}>{t(key)}</Badge>;
}
