"use client";

import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";

import { fetchContractFileBlob } from "@/lib/api";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { formatNum } from "@/lib/utils";
import type { LayoutBlock, SourceTarget } from "@/lib/types";

interface RawPage {
  page: number;
  text: string;
  char_start: number;
  total_pages: number;
  blocks?: LayoutBlock[];
  width?: number;
  height?: number;
  file_type?: string;
}

function highlightBlocks(data: RawPage, target: SourceTarget | null): LayoutBlock[] {
  if (!target || !data.blocks?.length) return [];
  const relStart = target.char_start - data.char_start;
  const relEnd = target.char_end - data.char_start;
  let snippet = target.quote?.trim() || "";
  if (!snippet && relStart >= 0 && relEnd <= data.text.length && relStart < relEnd) {
    snippet = data.text.slice(relStart, relEnd);
  }
  if (!snippet) return [];
  return data.blocks.filter((b) => b.text.includes(snippet) || snippet.includes(b.text.slice(0, 40)));
}

export default function SourceViewer({ contractId, target }: { contractId: string; target: SourceTarget | null }) {
  const { t, lang } = useI18n();
  const [page, setPage] = useState<number>(target?.page ?? 1);
  const [data, setData] = useState<RawPage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [pdfLoading, setPdfLoading] = useState(true);
  const [pdfError, setPdfError] = useState(false);
  const [isPdf, setIsPdf] = useState(true);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const markRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (target?.page) setPage(target.page);
  }, [target?.page, target?.char_start, target?.char_end, target?.quote]);

  useEffect(() => {
    let alive = true;
    setPdfLoading(true);
    setPdfError(false);
    fetchContractFileBlob(contractId)
      .then(async (blob) => {
        if (!alive) return;
        const pdf = blob.type.includes("pdf") || blob.type === "application/octet-stream";
        setIsPdf(pdf);
        if (!pdf) {
          setPdfDoc(null);
          return;
        }
        const buf = await blob.arrayBuffer();
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        const doc = await pdfjs.getDocument({ data: buf }).promise;
        if (alive) setPdfDoc(doc);
      })
      .catch(() => {
        if (alive) setPdfError(true);
      })
      .finally(() => {
        if (alive) setPdfLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [contractId]);

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
    if (!pdfDoc || !canvasRef.current || pdfError || !isPdf) return;
    let cancelled = false;
    (async () => {
      const pdfPage = await pdfDoc.getPage(page);
      const viewport = pdfPage.getViewport({ scale: 1.2 });
      const canvas = canvasRef.current!;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      canvas.height = viewport.height;
      canvas.width = viewport.width;
      setScale(viewport.scale);
      await pdfPage.render({ canvasContext: ctx, viewport, canvas }).promise;
      if (!cancelled) setScale(viewport.scale);
    })();
    return () => {
      cancelled = true;
    };
  }, [pdfDoc, page, pdfError, isPdf]);

  useEffect(() => {
    markRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [data, target]);

  const hlBlocks = data ? highlightBlocks(data, target) : [];
  const showCitationPanel =
    target &&
    target.page === page &&
    (target.quote || (target.char_start > 0 && target.char_end > target.char_start)) &&
    hlBlocks.length === 0;

  let textFallback: React.ReactNode = null;
  if (data && !pdfLoading && (!isPdf || pdfError || !pdfDoc)) {
    const blocks = data.blocks?.length ? data.blocks : [{ text: data.text, bbox: [0, 0, 0, 0], direction: "ltr" as const, column: 1 }];
    const highlight =
      target && target.page === data.page && target.char_start >= data.char_start && target.char_end <= data.char_start + data.text.length
        ? { start: target.char_start - data.char_start, end: target.char_end - data.char_start }
        : null;
    textFallback = (
      <div className="space-y-3">
        {blocks.map((b, i) => (
          <div
            key={i}
            dir="auto"
            className="bidi-plaintext text-sm leading-7 text-gray-800"
            style={{ textAlign: b.direction === "rtl" ? "right" : b.direction === "ltr" ? "left" : "start" }}
          >
            {b.text}
          </div>
        ))}
        {highlight && highlight.start >= 0 && highlight.end <= data.text.length && highlight.start < highlight.end && (
          <mark ref={markRef as any} className="block rounded bg-yellow-200 p-2 text-sm">
            {data.text.slice(highlight.start, highlight.end)}
          </mark>
        )}
      </div>
    );
  }

  const pageW = data?.width ?? 595;
  const pageH = data?.height ?? 842;

  return (
    <div className="flex h-full flex-col rounded-xl border bg-white shadow-sm">
      <div className="flex items-center justify-between border-b px-4 py-2">
        <h3 className="text-sm font-semibold text-gray-700">{t("detail.viewer.title")}</h3>
        {data && (
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <button
              type="button"
              className="rounded border px-2 py-0.5 hover:bg-gray-50 disabled:opacity-40"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              {t("detail.viewer.prev")}
            </button>
            <span>
              {t("detail.viewer.page")} {formatNum(page, lang)} / {formatNum(data.total_pages, lang)}
            </span>
            <button
              type="button"
              className="rounded border px-2 py-0.5 hover:bg-gray-50 disabled:opacity-40"
              disabled={page >= data.total_pages}
              onClick={() => setPage((p) => p + 1)}
            >
              {t("detail.viewer.next")}
            </button>
          </div>
        )}
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4 lg:flex-row">
        <div className="min-w-0 flex-1">
          {(loading || pdfLoading) && <p className="text-sm text-gray-400">{t("common.loading")}</p>}
          {error && <p className="text-sm text-red-500">{t("common.error")}</p>}
          {pdfError && (
            <p role="alert" className="mb-3 rounded border border-amber-200 bg-amber-50 p-2 text-sm text-amber-800">
              {t("detail.viewer.pdfFallback")}
            </p>
          )}
          {!loading && !pdfLoading && !error && isPdf && pdfDoc && !pdfError && (
            <div ref={wrapRef} className="relative inline-block max-w-full">
              <canvas ref={canvasRef} className="max-w-full border border-gray-100 shadow-sm" />
              {hlBlocks.map((b, i) => {
                const [x0, y0, x1, y1] = b.bbox;
                const left = x0 * scale;
                const top = y0 * scale;
                const width = (x1 - x0) * scale;
                const height = (y1 - y0) * scale;
                return (
                  <div
                    key={i}
                    className="pointer-events-none absolute rounded bg-yellow-300/40 ring-1 ring-yellow-500/60"
                    style={{ left, top, width, height }}
                  />
                );
              })}
            </div>
          )}
          {!loading && !error && textFallback}
        </div>
        {showCitationPanel && (
          <aside className="w-full shrink-0 rounded-lg border border-brand-200 bg-brand-50/50 p-3 lg:w-72">
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-brand-800">{t("detail.viewer.citation")}</h4>
            <p dir="auto" className="bidi-plaintext text-sm text-gray-800">
              {target!.quote ||
                (data &&
                  target!.char_end > target!.char_start &&
                  data.text.slice(
                    Math.max(0, target!.char_start - data.char_start),
                    Math.max(0, target!.char_end - data.char_start)
                  ))}
            </p>
          </aside>
        )}
      </div>
    </div>
  );
}
