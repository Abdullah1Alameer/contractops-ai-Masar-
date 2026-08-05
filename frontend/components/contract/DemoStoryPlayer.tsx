"use client";

import { useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Drawer from "@/components/ui/Drawer";
import { lineageDeepLink } from "@/lib/lineageLinks";
import { useI18n, type TKey } from "@/lib/i18n";
import type { VersionLineageEvent, VersionLineageResponse } from "@/lib/types";
import Link from "next/link";

const STORY_ORDER: { types: string[]; stepKey: TKey }[] = [
  { types: ["version_created"], stepKey: "demoStory.step.upload" },
  { types: ["extraction_completed"], stepKey: "demoStory.step.extraction" },
  { types: ["review_sent", "version_sent_for_review"], stepKey: "demoStory.step.reviewSent" },
  { types: ["review_changes_requested", "review_rejected"], stepKey: "demoStory.step.reviewChanges" },
  { types: ["negotiation_generated", "negotiation_analyzed"], stepKey: "demoStory.step.negotiation" },
  { types: ["counter_version_created", "version_created"], stepKey: "demoStory.step.newVersion" },
  { types: ["versions_compared", "version_compared", "ai_comparison_generated"], stepKey: "demoStory.step.compare" },
  { types: ["approval_completed", "approval_workflow_completed"], stepKey: "demoStory.step.approval" },
  { types: ["signature_request_sent", "version_sent_for_signature"], stepKey: "demoStory.step.signatureSent" },
  { types: ["signature_completed", "signature_request_completed", "signer_signed"], stepKey: "demoStory.step.signatureDone" },
  { types: ["contract_activated"], stepKey: "demoStory.step.activated" },
];

export default function DemoStoryPlayer({
  contractId,
  lineage,
  onHighlight,
}: {
  contractId: string;
  lineage: VersionLineageResponse;
  onHighlight: (eventId: string | null) => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [idx, setIdx] = useState(0);

  const steps = useMemo(() => {
    const all: VersionLineageEvent[] = [];
    lineage.versions.forEach((v) => all.push(...v.events));
    all.sort((a, b) => (a.timestamp ?? "").localeCompare(b.timestamp ?? ""));

    const picked: { event: VersionLineageEvent; stepKey: TKey }[] = [];
    for (const spec of STORY_ORDER) {
      const hit = all.find((e) => spec.types.includes(e.event_type));
      if (hit) picked.push({ event: hit, stepKey: spec.stepKey });
    }
    return picked;
  }, [lineage]);

  const current = steps[idx];
  const href = current ? lineageDeepLink(contractId, current.event) : null;

  const go = (next: number) => {
    const n = Math.max(0, Math.min(steps.length - 1, next));
    setIdx(n);
    onHighlight(steps[n]?.event.event_id ?? null);
  };

  if (steps.length === 0) return null;

  return (
    <>
      <Button variant="secondary" size="sm" onClick={() => { setOpen(true); setIdx(0); onHighlight(steps[0]?.event.event_id ?? null); }}>
        {t("versions.lifecycleStory")}
      </Button>
      <Drawer open={open} onClose={() => { setOpen(false); onHighlight(null); }} title={t("versions.lifecycleStory")} size="md">
        <p className="text-sm text-neutral-800">{current ? t(current.stepKey) : t("common.empty")}</p>
        <p className="mt-2 text-xs text-neutral-500">
          {current?.event.timestamp?.slice(0, 16) ?? ""} · {current?.event.actor ?? "—"}
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" disabled={idx <= 0} onClick={() => go(idx - 1)}>
            {t("demoStory.prev")}
          </Button>
          <Button variant="secondary" size="sm" disabled={idx >= steps.length - 1} onClick={() => go(idx + 1)}>
            {t("demoStory.next")}
          </Button>
          {href && (
            <Link href={href}>
              <Button variant="primary" size="sm">{t("versions.viewRelated")}</Button>
            </Link>
          )}
        </div>
        {idx >= steps.length - 1 && (
          <p className="mt-6 rounded-lg bg-brand-50 p-3 text-sm text-brand-900">{t("demoStory.presenterNote")}</p>
        )}
      </Drawer>
    </>
  );
}
