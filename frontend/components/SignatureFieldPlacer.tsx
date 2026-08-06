"use client";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { useEffect, useRef, useState } from "react";

import { useToast } from "@/components/feedback/ToastProvider";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { apiErrorCode, fetchContractFileBlob, saveSignatureFields, suggestSignatureFields } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { SignatureField, SignatureFieldInput, SignatureFieldType, SignatureSignerRow } from "@/lib/types";
import { cn } from "@/lib/utils";

// Internal field-placement UI backing the "signature location inside the
// actual document" fix — an internal user places one or more fields per
// signer directly on the rendered PDF page, optionally starting from an
// AI-suggested default, before the request can be sent. See
// docs/signature-placement-and-template-flow-report.md.

const FIELD_TYPES: SignatureFieldType[] = ["signature", "initials", "name", "date"];

type DraftField = SignatureFieldInput & { id: string; ai_suggested: boolean };

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
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [pdfError, setPdfError] = useState(false);
  const [page, setPage] = useState(1);
  const [pageCount, setPageCount] = useState(1);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [scale, setScale] = useState(1);
  const [fields, setFields] = useState<DraftField[]>(initialFields.map(toDraft));
  const [activeSigner, setActiveSigner] = useState<string>(signers[0]?.id ?? "");
  const [activeType, setActiveType] = useState<SignatureFieldType>("signature");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setFields(initialFields.map(toDraft));
  }, [initialFields]);

  useEffect(() => {
    let alive = true;
    fetchContractFileBlob(contractId)
      .then(async (blob) => {
        const buf = await blob.arrayBuffer();
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        const doc = await pdfjs.getDocument({ data: buf }).promise;
        if (!alive) return;
        setPdfDoc(doc);
        setPageCount(doc.numPages);
      })
      .catch(() => alive && setPdfError(true));
    return () => {
      alive = false;
    };
  }, [contractId]);

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
      if (!cancelled) setScale(viewport.scale);
    })();
    return () => {
      cancelled = true;
    };
  }, [pdfDoc, page]);

  const placeAt = (e: React.MouseEvent<HTMLDivElement>) => {
    if (locked || !activeSigner) return;
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
              <Button variant="secondary" size="sm" loading={busy} onClick={suggest}>
                {t("signature.fields.suggest")}
              </Button>
            </div>
          </>
        )}

        {pdfError ? (
          <p className="text-sm text-danger-600">{t("detail.viewer.pdfFallback")}</p>
        ) : (
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
            <div
              className={cn("relative inline-block max-w-full", !locked && "cursor-crosshair")}
              onClick={placeAt}
            >
              <canvas ref={canvasRef} className="max-w-full border border-gray-100 shadow-sm" />
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
            </div>
          </>
        )}

        {!locked && (
          <>
            {!everySignerHasSignatureField && (
              <p className="text-xs font-medium text-warning-700">{t("signature.fields.missingWarning")}</p>
            )}
            <Button variant="primary" size="sm" loading={busy} disabled={fields.length === 0} onClick={save}>
              {t("signature.fields.save")}
            </Button>
          </>
        )}
      </CardBody>
    </Card>
  );
}
