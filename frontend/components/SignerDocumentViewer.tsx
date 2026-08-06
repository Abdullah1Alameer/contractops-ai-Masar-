"use client";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { useEffect, useRef, useState } from "react";

import { useI18n } from "@/lib/i18n";
import type { SignatureField } from "@/lib/types";
import { cn } from "@/lib/utils";

// Public signer-side document viewer: renders the actual approved PDF (not
// an opaque iframe) with the signer's own confirmed field(s) highlighted, a
// "field X of N" progress indicator, and a jump-to-field control — so the
// signer can see exactly where their mark will land before signing. See
// docs/signature-placement-and-template-flow-report.md.
export default function SignerDocumentViewer({
  documentUrl,
  fields,
  onAllFieldsViewed,
}: {
  documentUrl: string;
  fields: SignatureField[];
  onAllFieldsViewed?: () => void;
}) {
  const { t } = useI18n();
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [pdfError, setPdfError] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(true);
  const [page, setPage] = useState(fields[0]?.page_number ?? 1);
  const [activeIndex, setActiveIndex] = useState(0);
  const [viewed, setViewed] = useState<Set<number>>(new Set());
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let alive = true;
    setPdfLoading(true);
    fetch(documentUrl)
      .then((res) => {
        if (!res.ok) throw new Error("fetch_failed");
        return res.arrayBuffer();
      })
      .then(async (buf) => {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        const doc = await pdfjs.getDocument({ data: buf }).promise;
        if (alive) setPdfDoc(doc);
      })
      .catch(() => alive && setPdfError(true))
      .finally(() => alive && setPdfLoading(false));
    return () => {
      alive = false;
    };
  }, [documentUrl]);

  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;
    let cancelled = false;
    (async () => {
      const pdfPage = await pdfDoc.getPage(page);
      if (cancelled || !canvasRef.current) return;
      const viewport = pdfPage.getViewport({ scale: 1.2 });
      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await pdfPage.render({ canvasContext: ctx, viewport, canvas }).promise;
    })();
    return () => {
      cancelled = true;
    };
  }, [pdfDoc, page]);

  useEffect(() => {
    if (fields.length === 0) return;
    setViewed((prev) => {
      if (prev.has(activeIndex)) return prev;
      const next = new Set(prev).add(activeIndex);
      if (next.size === fields.length) onAllFieldsViewed?.();
      return next;
    });
  }, [activeIndex, fields.length, onAllFieldsViewed]);

  const jumpTo = (index: number) => {
    const f = fields[index];
    if (!f) return;
    setActiveIndex(index);
    setPage(f.page_number);
  };

  if (fields.length === 0) {
    // No confirmed field for this signer yet — should not normally happen
    // once send_request() has enforced placement, but fail honestly rather
    // than pretending a location exists.
    return <p className="text-sm text-warning-800">{t("signature.fields.viewerUnavailable")}</p>;
  }

  const fieldsOnPage = fields.filter((f) => f.page_number === page);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="chip chip-active tnum">
          {t("signature.fields.progressLabel")} {activeIndex + 1}/{fields.length}
        </span>
        <button
          type="button"
          className="rounded-lg border border-brand-300 bg-brand-50 px-3 py-1 text-sm font-semibold text-brand-800 hover:bg-brand-100"
          onClick={() => jumpTo(activeIndex)}
        >
          {t("signature.fields.jumpTo")}
        </button>
      </div>
      {pdfLoading && <p className="text-sm text-gray-400">{t("common.loading")}</p>}
      {pdfError && <p className="text-sm text-danger-600">{t("detail.viewer.pdfFallback")}</p>}
      {!pdfLoading && !pdfError && pdfDoc && (
        <>
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
              {t("detail.viewer.page")} {page}
            </span>
            <button
              type="button"
              className="rounded border px-2 py-0.5 hover:bg-gray-50 disabled:opacity-40"
              onClick={() => setPage((p) => p + 1)}
            >
              {t("detail.viewer.next")}
            </button>
          </div>
          <div className="relative inline-block max-w-full">
            <canvas ref={canvasRef} className="max-w-full rounded-xl border-2 border-gray-200 shadow-inner" />
            {fieldsOnPage.map((f) => {
              const idx = fields.indexOf(f);
              const active = idx === activeIndex;
              return (
                <div
                  key={f.id}
                  className={cn(
                    "absolute flex items-center justify-center rounded border-2 text-[10px] font-semibold",
                    active
                      ? "border-brand-600 bg-brand-200/60 text-brand-900 ring-2 ring-brand-500/60"
                      : "border-gray-400 bg-gray-100/60 text-gray-600"
                  )}
                  style={{
                    left: `${f.x * 100}%`,
                    top: `${f.y * 100}%`,
                    width: `${f.width * 100}%`,
                    height: `${f.height * 100}%`,
                  }}
                >
                  {t(`signature.fields.type.${f.field_type}` as import("@/lib/i18n").TKey)}
                </div>
              );
            })}
          </div>
          {fields.length > 1 && (
            <div className="flex flex-wrap gap-2">
              {fields.map((f, i) => (
                <button
                  key={f.id}
                  type="button"
                  className={cn(
                    "rounded border px-2 py-1 text-xs",
                    i === activeIndex ? "border-brand-600 bg-brand-50 text-brand-800" : "border-gray-200 text-gray-600"
                  )}
                  onClick={() => jumpTo(i)}
                >
                  {i + 1}. {t(`signature.fields.type.${f.field_type}` as import("@/lib/i18n").TKey)} (p.{f.page_number})
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
