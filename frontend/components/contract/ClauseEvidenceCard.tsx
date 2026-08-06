"use client";
import { useState } from "react";

import ConfidenceChip from "@/components/ConfidenceChip";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { useI18n, type TKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

// Shared "why/what/where" traceability block for every extracted analysis
// item (Obligations, Notification Clauses, Timeline/Deadlines, Risk
// findings). Fixes the audited gap where every item was an isolated card
// with a description and, at best, a tooltip — a legal user could not see
// the original clause text, why an item was extracted, or jump back to
// its source without leaving the app's normal flow. See
// docs/analysis-traceability-audit.md.
//
// Deliberately read-only: no new write/edit endpoints are called here.
// "Accept"/mark-reviewed actions reuse whatever mutation already exists on
// the calling tab (e.g. the obligation status toggle) — this component
// never invents new persistence.
export interface EvidenceMetadataItem {
  label: TKey;
  value: React.ReactNode;
}

export default function ClauseEvidenceCard({
  quote,
  clauseRef,
  page,
  confidence,
  verified,
  reasoning,
  metadata,
  onJump,
  defaultOpen = false,
  actions,
}: {
  quote: string | null;
  clauseRef: string | null;
  page: number | null;
  confidence: number | null;
  verified: boolean;
  reasoning: string | null;
  metadata: EvidenceMetadataItem[];
  onJump?: () => void;
  defaultOpen?: boolean;
  actions?: React.ReactNode;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:underline focus-visible:focus-ring"
        aria-expanded={open}
      >
        <span className={cn("inline-block transition-transform", open && "rotate-90")}>›</span>
        {open ? t("evidence.hideDetails") : t("evidence.showDetails")}
      </button>

      {open && (
        <div className="mt-2 space-y-3 rounded-lg border border-gray-200 bg-gray-50/60 p-3">
          <section>
            <h5 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-500">
              {t("evidence.originalClause")}
            </h5>
            {quote ? (
              <p dir="auto" className="bidi-plaintext whitespace-pre-wrap rounded border border-gray-200 bg-white p-2 text-sm text-gray-800">
                {quote}
              </p>
            ) : (
              <p className="text-sm italic text-gray-400">{t("evidence.noQuote")}</p>
            )}
          </section>

          <section>
            <h5 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-500">
              {t("evidence.reasoning")}
            </h5>
            <p dir="auto" className="bidi-plaintext text-sm text-gray-700">
              {reasoning || t("evidence.reasoningUnavailable")}
            </p>
          </section>

          <section>
            <h5 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-500">
              {t("evidence.metadata")}
            </h5>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600 sm:grid-cols-3">
              <div>
                <dt className="inline font-medium text-gray-500">{t("evidence.page")}: </dt>
                <dd className="inline">{page ?? "—"}</dd>
              </div>
              <div>
                <dt className="inline font-medium text-gray-500">{t("detail.clause")}: </dt>
                <dd className="inline">{clauseRef ?? "—"}</dd>
              </div>
              <div className="flex items-center gap-1">
                <dt className="font-medium text-gray-500">{t("evidence.confidence")}: </dt>
                <dd>{confidence != null ? <ConfidenceChip confidence={confidence} /> : <span>{t("evidence.notScored")}</span>}</dd>
              </div>
              {metadata.map((m, i) => (
                <div key={i}>
                  <dt className="inline font-medium text-gray-500">{t(m.label)}: </dt>
                  <dd className="inline">{m.value ?? "—"}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section className="flex flex-wrap items-center gap-2">
            {verified && onJump ? (
              <Button variant="secondary" size="sm" onClick={onJump}>
                {t("evidence.jumpToClause")}
              </Button>
            ) : (
              <Badge tone="neutral">{t("detail.sourceUnverified")}</Badge>
            )}
            {actions}
          </section>
        </div>
      )}
    </div>
  );
}
