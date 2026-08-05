"use client";

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import { fetchContractSummary, generateContractSummary } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { ContractSummaryPayload, SummaryCitation, SummarySections, SourceTarget } from "@/lib/types";

const SECTION_KEYS = [
  "purpose",
  "parties",
  "term_and_key_dates",
  "financial_terms",
  "key_obligations",
  "termination_renewal",
  "notable_risks",
  "next_steps",
] as const;

const SECTION_I18N: Record<(typeof SECTION_KEYS)[number], TKey> = {
  purpose: "summary.section.purpose",
  parties: "summary.section.parties",
  term_and_key_dates: "summary.section.term",
  financial_terms: "summary.section.financial",
  key_obligations: "summary.section.obligations",
  termination_renewal: "summary.section.termination",
  notable_risks: "summary.section.risks",
  next_steps: "summary.section.nextSteps",
};

export default function AiSummaryPanel({
  contractId,
  initialStatus,
  isStale,
  onCitation,
}: {
  contractId: string;
  initialStatus?: string;
  isStale?: boolean;
  onCitation: (target: SourceTarget & { quote?: string }) => void;
}) {
  const { t, lang: uiLang } = useI18n();
  const [data, setData] = useState<ContractSummaryPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [lang, setLang] = useState<"ar" | "en">(uiLang === "ar" ? "ar" : "en");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchContractSummary(contractId);
      setData(res);
    } catch {
      setData({
        status: "failed",
        summary_ar: null,
        summary_en: null,
        error_code: "unknown",
        error_detail: null,
        generated_at: null,
        model: null,
        is_stale: false,
      });
    } finally {
      setLoading(false);
    }
  }, [contractId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (data?.status !== "generating") return;
    const id = window.setInterval(load, 3000);
    return () => window.clearInterval(id);
  }, [data?.status, load]);

  const status = data?.status ?? initialStatus ?? "not_generated";
  const stale = data?.is_stale ?? isStale;

  const runGenerate = async (force: boolean) => {
    setBusy(true);
    try {
      await generateContractSummary(contractId, force);
      setData((d) => (d ? { ...d, status: "generating" } : { status: "generating", summary_ar: null, summary_en: null, error_code: null, error_detail: null, generated_at: null, model: null, is_stale: false }));
      await load();
    } finally {
      setBusy(false);
    }
  };

  const sections: SummarySections | null = lang === "ar" ? data?.summary_ar ?? null : data?.summary_en ?? null;

  const cite = (c: SummaryCitation) => {
    onCitation({
      page: c.page,
      char_start: 0,
      char_end: 0,
      quote: c.quote,
    });
  };

  if (loading && !data) {
    return <p className="text-sm text-gray-400">{t("common.loading")}</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1 rounded-lg border bg-gray-50 p-0.5 text-xs">
          <button
            type="button"
            className={`rounded-md px-3 py-1 ${lang === "ar" ? "bg-white shadow-sm" : ""}`}
            onClick={() => setLang("ar")}
          >
            {t("summary.lang.ar")}
          </button>
          <button
            type="button"
            className={`rounded-md px-3 py-1 ${lang === "en" ? "bg-white shadow-sm" : ""}`}
            onClick={() => setLang("en")}
          >
            {t("summary.lang.en")}
          </button>
        </div>
        <div className="flex gap-2">
          {status === "ready" && (
            <Button variant="secondary" size="sm" disabled={busy} onClick={() => runGenerate(true)}>
              {stale ? t("summary.regenerateStale") : t("summary.regenerate")}
            </Button>
          )}
          {status === "not_generated" && (
            <Button size="sm" disabled={busy} onClick={() => runGenerate(false)}>
              {t("summary.generate")}
            </Button>
          )}
          {status === "failed" && (
            <Button size="sm" disabled={busy} onClick={() => runGenerate(true)}>
              {t("summary.retry")}
            </Button>
          )}
        </div>
      </div>

      {status === "generating" && (
        <div className="space-y-3 animate-pulse">
          <div className="h-4 w-2/3 rounded bg-gray-200" />
          <div className="h-3 w-full rounded bg-gray-100" />
          <div className="h-3 w-5/6 rounded bg-gray-100" />
          <p className="text-sm text-gray-500">{t("summary.generating")}</p>
        </div>
      )}

      {status === "failed" && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <p className="font-medium">{t("summary.failed")}</p>
          {data?.error_detail && <p className="mt-1 text-red-700">{data.error_detail}</p>}
          {data?.error_code && (
            <p className="mt-1 text-xs text-red-600">
              {t("summary.errorCode")}: {data.error_code}
            </p>
          )}
        </div>
      )}

      {status === "not_generated" && (
        <p className="text-sm text-gray-500">{t("summary.empty")}</p>
      )}

      {status === "ready" && sections && (
        <div className="space-y-6">
          {SECTION_KEYS.map((key) => {
            const sec = sections[key];
            if (!sec) return null;
            return (
              <section key={key}>
                <h3 className="mb-2 text-sm font-semibold text-gray-800">{t(SECTION_I18N[key])}</h3>
                {sec.status === "not_stated" ? (
                  <p className="text-sm text-gray-500">{t("summary.notStated")}</p>
                ) : (
                  <>
                    {sec.overview && (
                      <p dir="auto" className="bidi-plaintext mb-2 text-sm leading-relaxed text-gray-800">
                        {sec.overview}
                      </p>
                    )}
                    <ul className="list-disc space-y-2 ps-5 text-sm text-gray-800">
                      {sec.items.map((item, i) => (
                        <li key={i} dir="auto" className="bidi-plaintext">
                          {item.text}
                          {item.citations?.length > 0 && (
                            <span className="mt-1 flex flex-wrap gap-1">
                              {item.citations.map((c, j) => (
                                <button
                                  key={j}
                                  type="button"
                                  className="rounded bg-brand-50 px-1.5 py-0.5 text-xs text-brand-700 hover:bg-brand-100"
                                  onClick={() => cite(c)}
                                >
                                  {t("summary.citation")} p.{c.page}
                                </button>
                              ))}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
