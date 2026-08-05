"use client";

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import { useCachedFetch } from "@/lib/cache";
import {
  approveNegotiationResponse,
  getNegotiationPackage,
  sendNegotiationResponse,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type Props = {
  packageId: string | null;
  threadId: string;
  onSent: () => void;
};

export default function ReviewPackagePanel({ packageId, onSent }: Props) {
  const { t } = useI18n();
  const { data, refresh } = useCachedFetch(
    packageId ? `negotiation:pkg:edit:${packageId}` : "none",
    () => (packageId ? getNegotiationPackage(packageId) : Promise.resolve(null)),
    { enabled: Boolean(packageId) }
  );
  const [tab, setTab] = useState<"en" | "ar">("ar");
  const [bodyEn, setBodyEn] = useState("");
  const [bodyAr, setBodyAr] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setBodyEn(data.draft_email_body_en ?? "");
      setBodyAr(data.draft_email_body_ar ?? "");
    }
  }, [data]);

  if (!packageId || !data) {
    return (
      <section className="surface-card p-4">
        <p className="text-hint">{t("monitor.reviewPackage")}</p>
      </section>
    );
  }

  const pid = packageId;
  const changes = ((data.package_json as Record<string, unknown>)?.changes ?? []) as Record<string, unknown>[];
  const needsFinance = changes.some((c) => c.required_approver === "finance");

  async function onApprove() {
    await approveNegotiationResponse(pid, {
      draft_email_body_en: bodyEn,
      draft_email_body_ar: bodyAr,
    });
    refresh();
  }

  async function onSend() {
    setError(null);
    try {
      await sendNegotiationResponse(pid);
      onSent();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "send_failed";
      setError(msg);
    }
  }

  async function onSendOverride() {
    setError(null);
    await sendNegotiationResponse(pid, "demo_override_finance");
    onSent();
  }

  return (
    <section className="surface-card space-y-4 p-4">
      <h3 className="font-bold">{t("monitor.reviewPackage")}</h3>
      <p className="text-sm text-neutral-700">{data.executive_summary}</p>
      <p className="text-sm">
        {t("monitor.filters.highRisk")}: {data.overall_risk_score ?? "—"} · {data.recommendation}
      </p>
      {needsFinance ? <p className="text-sm font-semibold text-amber-700">{t("monitor.requiresFinance")}</p> : null}
      <div className="flex gap-2">
        <Button size="sm" variant={tab === "ar" ? "primary" : "secondary"} onClick={() => setTab("ar")}>
          العربية
        </Button>
        <Button size="sm" variant={tab === "en" ? "primary" : "secondary"} onClick={() => setTab("en")}>
          English
        </Button>
      </div>
      <textarea
        className="min-h-[160px] w-full rounded-lg border border-neutral-200 p-3 text-sm"
        dir={tab === "ar" ? "rtl" : "ltr"}
        value={tab === "ar" ? bodyAr : bodyEn}
        onChange={(e) => (tab === "ar" ? setBodyAr(e.target.value) : setBodyEn(e.target.value))}
      />
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={onApprove}>
          {t("common.confirm")}
        </Button>
        <Button variant="primary" onClick={onSend}>
          {t("monitor.approveSend")}
        </Button>
        {error ? (
          <Button variant="secondary" onClick={onSendOverride}>
            {t("monitor.requiresFinance")} — override
          </Button>
        ) : null}
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
    </section>
  );
}
