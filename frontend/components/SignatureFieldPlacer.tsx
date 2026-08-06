"use client";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { useEffect, useRef, useState } from "react";

import { useToast } from "@/components/feedback/ToastProvider";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import {
  api,
  apiErrorCode,
  fetchSignatureRequestDocumentBlob,
  saveSignatureFields,
  suggestSignatureFields,
} from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { LayoutBlock, SignatureField, SignatureFieldInput, SignatureFieldType, SignatureSignerRow } from "@/lib/types";
import { cn } from "@/lib/utils";

// Internal field-placement UI backing the "signature location inside the
// actual document" fix — an internal user places one or more fields per
// signer directly on the rendered document, optionally starting from an
// AI-suggested default, before the request can be sent. See
// docs/signature-placement-and-template-flow-report.md and
// docs/signature-placement-viewer-fix-report.md (the document-source and
// fallback-rendering fix).

const FIELD_TYPES: SignatureFieldType[] = ["signature", "initials", "name", "date"];

type DraftField = SignatureFieldInput & { id: string; ai_suggested: boolean };

// Bug fix: this viewer used to fetch the CONTRACT's raw uploaded file
// (/api/contracts/{id}/file) — for a DOCX-sourced contract that is a Word
// document, not a PDF, so pdfjs always failed to parse it, and the only
// thing rendered was a static sentence claiming a text fallback was shown
// (it never actually was). It now fetches the signature REQUEST's own
// document (/api/signature-requests/{id}/document) — the same
// guaranteed-renderable PDF snapshot (real PDF pass-through, or a PDF
// generated from the extracted text when the source wasn't a PDF) the
// public signer portal already relies on, tied to the exact version the
// request was created against. If that PDF genuinely fails to render
// (corrupted blob, worker failure), a real extracted-text fallback is
// fetched and rendered — not just claimed.
type ViewerState = "loading" | "pdf" | "text" | "empty";

interface RawPage {
  page: number;
  text: string;
  char_start: number;
  total_pages: number;
  blocks?: LayoutBlock[];
}

function toDraft(f: SignatureField): DraftField {
  return { id: f.id, signer_id: f.signer_id, page_number: f.page_number, x: f.x, y: f.y, width: f.width, height: f.height, field_type: f.field_type, required: f.required, ai_suggested: f.ai_suggested };
}

export default function SignatureFieldPlacer({
  contractId,
  requestId,
  signers,
  initialFields,
  locked,
  onSaved,
}: {
  contractId: string;
  requestId: string;
  signers: SignatureSignerRow[];
  initialFields: SignatureField[];
  locked: boolean;
  onSaved: () => void;
}) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const [viewerState, setViewerState] = useState<ViewerState>("loading");
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [page, setPage] = useState(1);
  const [pageCount, setPageCount] = useState(1);
  const [textPage, setTextPage] = useState<RawPage | null>(null);
  const [textLoading, setTextLoading] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [fields, setFields] = useState<DraftField[]>(initialFields.map(toDraft));
  const [activeSigner, setActiveSigner] = useState<string>(signers[0]?.id ?? "");
  const [activeType, setActiveType] = useState<SignatureFieldType>("signature");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setFields(initialFields.map(toDraft));
  }, [initialFields]);

  // Refetches whenever the signature request changes — each request is
  // pinned to one contract version, so a new request (e.g. after a new
  // version was sent) always means a new document here too.
  useEffect(() => {
    let alive = true;
    setViewerState("loading");
    setPdfDoc(null);
    setTextPage(null);
    setPage(1);

    const tryTextFallback = async () => {
      try {
        const data = await api<RawPage>(`/api/contracts/${contractId}/raw?page=1`);
        if (!alive) return;
        if (!data.text?.trim() && !data.blocks?.length) {
          setViewerState("empty");
          return;
        }
        setTextPage(data);
        setPageCount(data.total_pages || 1);
        setViewerState("text");
      } catch {
        if (alive) setViewerState("empty");
      }
    };

    fetchSignatureRequestDocumentBlob(requestId)
      .then(async (blob) => {
        const buf = await blob.arrayBuffer();
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        const doc = await pdfjs.getDocument({ data: buf }).promise;
        if (!alive) return;
        setPdfDoc(doc);
        setPageCount(doc.numPages);
        setViewerState("pdf");
      })
      .catch(() => {
        if (alive) tryTextFallback();
      });

    return () => {
      alive = false;
    };
  }, [contractId, requestId]);

  useEffect(() => {
    if (viewerState !== "pdf" || !pdfDoc || !canvasRef.current) return;
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
  }, [viewerState, pdfDoc, page]);

  // Text-fallback pagination — refetches the requested page's extracted
  // text (same /raw endpoint the read-only source viewer uses).
  useEffect(() => {
    if (viewerState !== "text") return;
    if (textPage?.page === page) return;
    let alive = true;
    setTextLoading(true);
    api<RawPage>(`/api/contracts/${contractId}/raw?page=${page}`)
      .then((data) => alive && setTextPage(data))
      .catch(() => {
        /* keep showing the previous page rather than blanking it */
      })
      .finally(() => alive && setTextLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewerState, page, contractId]);

  const hasVisibleDocument = viewerState === "pdf" || viewerState === "text";

  const placeAt = (e: React.MouseEvent<HTMLDivElement>) => {
    if (locked || !activeSigner || !hasVisibleDocument) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 0.62);
    const y = Math.min(Math.max((e.clientY - rect.top) / rect.height, 0), 0.9);
    const newField: DraftField = {
      id: `draft-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      signer_id: activeSigner,
      page_number: page,
      x,
      y,
      width: 0.36,
      height: 0.06,
      field_type: activeType,
      required: true,
      ai_suggested: false,
    };
    setFields((prev) => [...prev, newField]);
  };

  const removeField = (id: string) => setFields((prev) => prev.filter((f) => f.id !== id));

  const suggest = async () => {
    setBusy(true);
    try {
      const { fields: suggested } = await suggestSignatureFields(requestId);
      setFields((prev) => [
        ...prev,
        ...suggested.map((f, i) => ({ ...f, id: `ai-${Date.now()}-${i}` })),
      ]);
      if (suggested.length) setPage(suggested[0].page_number);
      toast.info(t("signature.fields.suggested"));
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    try {
      const payload: SignatureFieldInput[] = fields.map(({ id, ai_suggested, ...rest }) => rest);
      await saveSignatureFields(requestId, payload);
      toast.success(t("signature.fields.saved"));
      onSaved();
    } catch (error) {
      toast.error(apiErrorCode(error, t("common.error")));
    } finally {
      setBusy(false);
    }
  };

  const signerName = (id: string) => signers.find((s) => s.id === id)?.name ?? "?";
  const fieldsOnPage = fields.filter((f) => f.page_number === page);
  const everySignerHasSignatureField = signers.every((s) => fields.some((f) => f.signer_id === s.id && f.field_type === "signature"));

  const fieldOverlay = (
    <>
      {fieldsOnPage.map((f) => (
        <div
          key={f.id}
          className={cn(
            "absolute flex items-center justify-center rounded border-2 text-[10px] font-semibold",
            f.ai_suggested ? "border-amber-500 bg-amber-100/70 text-amber-800" : "border-brand-600 bg-brand-100/70 text-brand-800"
          )}
          style={{
            left: `${f.x * 100}%`,
            top: `${f.y * 100}%`,
            width: `${f.width * 100}%`,
            height: `${f.height * 100}%`,
          }}
          onClick={(e) => {
            e.stopPropagation();
            if (!locked) removeField(f.id);
          }}
        >
          {signerName(f.signer_id)} — {t(`signature.fields.type.${f.field_type}` as TKey)}
          {f.ai_suggested && ` (${t("signature.fields.aiTag")})`}
        </div>
      ))}
    </>
  );

  return (
    <Card>
      <CardBody className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="font-semibold">{t("signature.fields.title")}</h4>
          {locked && <Badge tone="subtle">{t("signature.fields.locked")}</Badge>}
        </div>
        {!locked && (
          <>
            <p className="text-xs text-gray-500">{t("signature.fields.hint")}</p>
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="rounded border px-2 py-1 text-sm"
                value={activeSigner}
                onChange={(e) => setActiveSigner(e.target.value)}
              >
                {signers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.signer_order}. {s.name}
                  </option>
                ))}
              </select>
              <select
                className="rounded border px-2 py-1 text-sm"
                value={activeType}
                onChange={(e) => setActiveType(e.target.value as SignatureFieldType)}
              >
                {FIELD_TYPES.map((ft) => (
                  <option key={ft} value={ft}>
                    {t(`signature.fields.type.${ft}` as TKey)}
                  </option>
                ))}
              </select>
              <Button variant="secondary" size="sm" loading={busy} onClick={suggest} disabled={!hasVisibleDocument}>
                {t("signature.fields.suggest")}
              </Button>
            </div>
          </>
        )}

        {viewerState === "loading" && <p className="text-sm text-gray-500">{t("common.loading")}</p>}

        {viewerState === "empty" && (
          <p role="alert" className="text-sm text-danger-600">
            {t("signature.fields.noDocument")}
          </p>
        )}

        {(viewerState === "pdf" || viewerState === "text") && (
          <>
            {viewerState === "text" && (
              <p role="status" className="rounded border border-warning-200 bg-warning-50 p-2 text-xs text-warning-800">
                {t("detail.viewer.pdfFallback")}
              </p>
            )}
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
                {t("detail.viewer.page")} {page} / {pageCount}
              </span>
              <button
                type="button"
                className="rounded border px-2 py-0.5 hover:bg-gray-50 disabled:opacity-40"
                disabled={page >= pageCount}
                onClick={() => setPage((p) => p + 1)}
              >
                {t("detail.viewer.next")}
              </button>
            </div>

            {viewerState === "pdf" && (
              <div
                className={cn("relative inline-block max-w-full", !locked && "cursor-crosshair")}
                onClick={placeAt}
              >
                <canvas ref={canvasRef} className="max-w-full border border-gray-100 shadow-sm" />
                {fieldOverlay}
              </div>
            )}

            {viewerState === "text" && (
              <div
                className={cn(
                  "relative min-h-[240px] max-w-full space-y-3 overflow-auto border border-gray-100 bg-white p-4 shadow-sm",
                  !locked && "cursor-crosshair"
                )}
                onClick={placeAt}
              >
                {textLoading && <p className="text-xs text-gray-400">{t("common.loading")}</p>}
                {!textLoading && textPage && (textPage.blocks?.length ? (
                  textPage.blocks.map((b, i) => (
                    <p
                      key={i}
                      dir="auto"
                      className="bidi-plaintext text-sm leading-7 text-gray-800"
                      style={{ textAlign: b.direction === "rtl" ? "right" : b.direction === "ltr" ? "left" : "start" }}
                    >
                      {b.text}
                    </p>
                  ))
                ) : (
                  <p dir="auto" className="bidi-plaintext whitespace-pre-wrap text-sm leading-7 text-gray-800">
                    {textPage.text}
                  </p>
                ))}
                {fieldOverlay}
              </div>
            )}
          </>
        )}

        {!locked && (
          <>
            {!everySignerHasSignatureField && (
              <p className="text-xs font-medium text-warning-700">{t("signature.fields.missingWarning")}</p>
            )}
            {!hasVisibleDocument && (
              <p className="text-xs font-medium text-warning-700">{t("signature.fields.documentRequired")}</p>
            )}
            <Button
              variant="primary"
              size="sm"
              loading={busy}
              disabled={fields.length === 0 || !hasVisibleDocument}
              onClick={save}
            >
              {t("signature.fields.save")}
            </Button>
          </>
        )}
      </CardBody>
    </Card>
  );
}
