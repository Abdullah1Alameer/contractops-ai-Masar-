"use client";
// The trust anchor of the UI: shows the raw contract page and highlights the
// EXACT verified quote via char offsets. Values without a verified clause link
// never reach this component (they render a "source unverified" badge instead)
// — no wrong highlights, ever.
import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { SourceTarget } from "@/lib/types";

interface RawPage {
  page: number;
  text: string;
  char_start: number; // global offset in raw_text where `text` begins
  total_pages: number;
}

export default function SourceViewer({ contractId, target }: { contractId: string; target: SourceTarget | null }) {
  const { t } = useI18n();
  const [page, setPage] = useState<number>(target?.page ?? 1);
  const [data, setData] = useState<RawPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const markRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (target) setPage(target.page);
  }, [target]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(false);
    api<RawPage>(`/api/contracts/${contractId}/raw?page=${page}`)
      .then((d) => alive && setData(d))
      .catch(() => alive && setError(true))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [contractId, page]);

  useEffect(() => {
    markRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [data, target]);

  let content: React.ReactNode = null;
  if (data) {
    const highlight =
      target && target.page === data.page
        ? { start: target.char_start - data.char_start, end: target.char_end - data.char_start }
        : null;
    if (highlight && highlight.start >= 0 && highlight.end <= data.text.length && highlight.start < highlight.end) {
      content = (
        <>
          {data.text.slice(0, highlight.start)}
          <mark ref={markRef as any} className="rounded bg-yellow-200 px-0.5">
            {data.text.slice(highlight.start, highlight.end)}
          </mark>
          {data.text.slice(highlight.end)}
        </>
      );
    } else {
      content = data.text;
    }
  }

  return (
    <div className="flex h-full flex-col rounded-xl border bg-white shadow-sm">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <h3 className="text-sm font-semibold text-gray-700">{t("detail.viewer.title")}</h3>
        {data && (
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <button
              className="rounded border px-2 py-0.5 hover:bg-gray-50 disabled:opacity-40"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              {t("detail.viewer.prev")}
            </button>
            <span>
              {t("detail.viewer.page")} {page} / {data.total_pages}
            </span>
            <button
              className="rounded border px-2 py-0.5 hover:bg-gray-50 disabled:opacity-40"
              disabled={page >= data.total_pages}
              onClick={() => setPage((p) => p + 1)}
            >
              {t("detail.viewer.next")}
            </button>
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {loading && <p className="text-sm text-gray-400">{t("common.loading")}</p>}
        {error && <p className="text-sm text-red-500">{t("common.error")}</p>}
        {!loading && !error && !target && !data && (
          <p className="text-sm text-gray-400">{t("detail.viewer.empty")}</p>
        )}
        {!loading && !error && data && (
          <pre className="whitespace-pre-wrap break-words font-[inherit] text-sm leading-7 text-gray-800">{content}</pre>
        )}
      </div>
    </div>
  );
}
