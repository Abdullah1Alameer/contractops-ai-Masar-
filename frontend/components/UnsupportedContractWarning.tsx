"use client";
import Link from "next/link";

import { useI18n } from "@/lib/i18n";
import { SUPPORTED_CATEGORY_KEYS, contractCategoryLabelKey } from "@/lib/utils";

export default function UnsupportedContractWarning({
  category,
  message,
  confidence,
}: {
  category: string;
  message?: string;
  confidence?: number;
}) {
  const { t } = useI18n();
  const catKey = contractCategoryLabelKey(category);
  const lowConfidence = confidence != null && confidence < 0.8;

  return (
    <div className="mx-auto max-w-2xl rounded-xl border border-amber-200 bg-amber-50 p-8 shadow-sm">
      <div className="mb-4 flex items-start gap-3">
        <span className="text-2xl" aria-hidden>
          ⚠
        </span>
        <div>
          <h1 className="text-xl font-bold text-amber-900">{t("unsupported.title")}</h1>
          <p className="mt-2 text-sm text-amber-900/90">{t("unsupported.body")}</p>
        </div>
      </div>

      <div className="mb-6 rounded-lg border border-amber-200/80 bg-white p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">{t("unsupported.detected")}</p>
        <p className="mt-1 text-lg font-semibold text-gray-900">{t(catKey)}</p>
        {message && <p className="mt-2 text-sm text-gray-600">{message}</p>}
        {lowConfidence && !message?.includes("confident") && (
          <p className="mt-2 text-sm text-amber-800">{t("unsupported.lowConfidence")}</p>
        )}
      </div>

      <div className="mb-8">
        <p className="mb-2 text-sm font-semibold text-gray-800">{t("unsupported.supportedList")}</p>
        <ul className="list-inside list-disc space-y-1 text-sm text-gray-700">
          {SUPPORTED_CATEGORY_KEYS.map((k) => (
            <li key={k}>{t(k)}</li>
          ))}
        </ul>
      </div>

      <Link
        href="/contracts"
        className="inline-flex rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700"
      >
        {t("unsupported.backToList")}
      </Link>
    </div>
  );
}
