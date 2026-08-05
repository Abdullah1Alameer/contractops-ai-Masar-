"use client";
import Link from "next/link";
import { useState } from "react";

import Button from "@/components/ui/Button";
import { useI18n, type TKey } from "@/lib/i18n";
import { SUPPORTED_CATEGORY_KEYS, contractCategoryLabelKey, cn } from "@/lib/utils";

const RECLASSIFY_CATEGORIES = [
  "Other Legal Consent",
  "Consent Agreement",
  "Employment Screening Consent",
  "Background Check Authorization",
  "Data Processing Consent",
  "Privacy Consent",
  "NDA",
  "Service Agreement",
  "Employment Agreement",
  "Software/SaaS Agreement",
  "Other Commercial Contract",
] as const;

export default function UnsupportedContractWarning({
  category,
  message,
  confidence,
  contractId,
  onReclassify,
  reclassifying,
}: {
  category: string;
  message?: string;
  confidence?: number;
  contractId?: string;
  onReclassify?: (category: string) => void | Promise<void>;
  reclassifying?: boolean;
}) {
  const { t } = useI18n();
  const catKey = contractCategoryLabelKey(category);
  const needsReview = message === "needs_classification_review";
  const [supportedOpen, setSupportedOpen] = useState(true);
  const [pick, setPick] = useState<string>(RECLASSIFY_CATEGORIES[0]);

  const titleKey: TKey = needsReview ? "unsupported.needsReviewTitle" : "unsupported.title";

  return (
    <div className="mx-auto max-w-2xl rounded-xl border border-amber-200 bg-amber-50 p-6 shadow-sm">
      <div className="mb-4 flex items-start gap-3">
        <span className="text-2xl" aria-hidden>
          ⚠
        </span>
        <div>
          <h1 className="text-xl font-bold text-amber-900">{t(titleKey)}</h1>
          {!needsReview && <p className="mt-1 text-sm text-amber-900/90">{t("unsupported.body")}</p>}
        </div>
      </div>

      <div className="mb-4 rounded-lg border border-amber-200/80 bg-white p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{t("unsupported.detected")}</p>
        <p className="mt-1 text-lg font-semibold text-gray-900">{t(catKey)}</p>
        {message && message !== "needs_classification_review" && (
          <p className="mt-2 text-sm text-gray-600">{message}</p>
        )}
        {needsReview && <p className="mt-2 text-sm text-amber-800">{t("unsupported.needsReviewHint")}</p>}
        {confidence != null && confidence < 0.8 && !needsReview && (
          <p className="mt-2 text-sm text-amber-800">{t("unsupported.lowConfidence")}</p>
        )}
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {contractId && onReclassify && (
          <Button
            variant="primary"
            loading={reclassifying}
            onClick={() => onReclassify("Other Legal Consent")}
          >
            {t("unsupported.analyzeAnyway")}
          </Button>
        )}
        <Link
          href="/contracts"
          className="inline-flex items-center rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-semibold text-gray-800 hover:bg-gray-50"
        >
          {t("unsupported.backToList")}
        </Link>
      </div>

      {contractId && onReclassify && (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <label className="text-sm font-medium text-gray-700">{t("unsupported.reclassify")}</label>
          <select
            className="rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm"
            value={pick}
            onChange={(e) => setPick(e.target.value)}
          >
            {RECLASSIFY_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t(contractCategoryLabelKey(c))}
              </option>
            ))}
          </select>
          <Button variant="secondary" size="sm" loading={reclassifying} onClick={() => onReclassify(pick)}>
            {t("unsupported.applyCategory")}
          </Button>
        </div>
      )}

      <div className="border-t border-amber-200/60 pt-3">
        <button
          type="button"
          className="flex w-full items-center justify-between text-sm font-semibold text-gray-800"
          onClick={() => setSupportedOpen((o) => !o)}
        >
          {t("unsupported.supportedList")}
          <span className={cn("text-xs transition-transform", supportedOpen ? "rotate-180" : "")}>▼</span>
        </button>
        {supportedOpen && (
          <ul className="mt-2 max-h-48 list-inside list-disc space-y-1 overflow-y-auto text-sm text-gray-700">
            {SUPPORTED_CATEGORY_KEYS.map((k) => (
              <li key={k}>{t(k)}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
