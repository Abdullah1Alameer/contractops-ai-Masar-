/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: (opts: { data: ArrayBuffer }) => ({
    promise:
      // The "broken PDF" tests feed a buffer tagged with a sentinel byte
      // pattern so this mock can simulate a genuine parse failure without
      // needing a real corrupt-PDF fixture.
      new Uint8Array(opts.data).length > 0 && new Uint8Array(opts.data)[0] === 0xff
        ? Promise.reject(new Error("invalid PDF structure"))
        : Promise.resolve({
            numPages: 2,
            getPage: () =>
              Promise.resolve({
                getViewport: () => ({ width: 595, height: 842, scale: 1.2 }),
                render: () => ({ promise: Promise.resolve() }),
              }),
          }),
  }),
}));

const fetchSignatureRequestDocumentBlob = vi.fn();
const suggestSignatureFields = vi.fn();
const saveSignatureFields = vi.fn();
const api = vi.fn();

vi.mock("@/lib/api", () => ({
  apiErrorCode: (_error: unknown, fallback: string) => fallback,
  api: (...args: unknown[]) => api(...args),
  fetchSignatureRequestDocumentBlob: (...args: unknown[]) => fetchSignatureRequestDocumentBlob(...args),
  suggestSignatureFields: (...args: unknown[]) => suggestSignatureFields(...args),
  saveSignatureFields: (...args: unknown[]) => saveSignatureFields(...args),
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();
const toastInfo = vi.fn();

vi.mock("@/components/feedback/ToastProvider", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError, warning: vi.fn(), info: toastInfo, toast: vi.fn() }),
}));

import SignatureFieldPlacer from "@/components/SignatureFieldPlacer";
import { I18nProvider } from "@/lib/i18n";
import type { SignatureSignerRow } from "@/lib/types";

const SIGNERS: SignatureSignerRow[] = [
  { id: "signer-1", signer_order: 1, name: "Signer One", email: "one@example.invalid", role: "company_signatory", status: "waiting", opened_at: null, signed_at: null },
  { id: "signer-2", signer_order: 2, name: "Signer Two", email: "two@example.invalid", role: "client_signatory", status: "waiting", opened_at: null, signed_at: null },
];

function renderPlacer(props: Partial<React.ComponentProps<typeof SignatureFieldPlacer>> = {}) {
  return render(
    <I18nProvider>
      <SignatureFieldPlacer
        contractId="contract-1"
        requestId="request-1"
        signers={SIGNERS}
        initialFields={[]}
        locked={false}
        onSaved={vi.fn()}
        {...props}
      />
    </I18nProvider>
  );
}

afterEach(cleanup);

// jsdom's Blob shim has no arrayBuffer() implementation — stub one so the
// component's `await blob.arrayBuffer()` resolves instead of throwing.
// `firstByte` lets a test simulate a genuinely broken/corrupt PDF (see the
// pdfjs mock above).
function fakePdfBlob(firstByte = 0x25 /* '%' as in %PDF */): Blob {
  const blob = new Blob(["%PDF-1.4"], { type: "application/pdf" });
  (blob as unknown as { arrayBuffer: () => Promise<ArrayBuffer> }).arrayBuffer = () =>
    Promise.resolve(new Uint8Array([firstByte, 0, 0, 0]).buffer);
  return blob;
}

const RAW_PAGE_1 = {
  page: 1,
  text: "البند الأول: يلتزم الطرف الأول بتقديم الخدمات المتفق عليها.",
  char_start: 0,
  total_pages: 2,
  blocks: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  fetchSignatureRequestDocumentBlob.mockResolvedValue(fakePdfBlob());
});

describe("SignatureFieldPlacer — document source (the viewer bug fix)", () => {
  it("fetches the signature request's own document, not the contract's raw upload", async () => {
    renderPlacer();
    await waitFor(() => expect(fetchSignatureRequestDocumentBlob).toHaveBeenCalledWith("request-1"));
  });

  it("uploaded-PDF-sourced request: renders the PDF in the placement view", async () => {
    renderPlacer();

    await waitFor(() => expect(document.querySelector("canvas")).toBeTruthy());
    expect(screen.queryByText("تعذّر عرض المستند: لا يوجد ملف PDF صالح ولا نص مستخرج لهذا العقد. يرجى إعادة استخراج النص أو رفع نسخة صالحة من المستند قبل تحديد مواضع التوقيع.")).toBeNull();
  });

  it("DOCX-sourced / template-generated request: the endpoint already returns a real PDF, so it renders identically — no special-casing needed on the frontend", async () => {
    // Whether the original upload was PDF, DOCX, or a generated template
    // document, /api/signature-requests/{id}/document always returns a
    // real, renderable PDF (backend-guaranteed) — the frontend doesn't
    // need to know or care which source it came from.
    fetchSignatureRequestDocumentBlob.mockResolvedValue(fakePdfBlob());
    renderPlacer();

    await waitFor(() => expect(document.querySelector("canvas")).toBeTruthy());
  });

  it("broken PDF: falls back to real extracted text, not a blank area with a misleading claim", async () => {
    fetchSignatureRequestDocumentBlob.mockResolvedValue(fakePdfBlob(0xff));
    api.mockResolvedValue(RAW_PAGE_1);
    renderPlacer();

    await screen.findByText(RAW_PAGE_1.text);
    // The fallback disclosure is shown *alongside* real, visible content —
    // never alone over a blank area.
    expect(screen.getByText("تعذّر عرض ملف PDF. يتم عرض النص المستخرج الآمن بدلاً منه.")).toBeTruthy();
    expect(document.querySelector("canvas")).toBeNull();
  });

  it("text fallback includes the actual extracted contract content, not placeholder text", async () => {
    fetchSignatureRequestDocumentBlob.mockResolvedValue(fakePdfBlob(0xff));
    api.mockResolvedValue({
      ...RAW_PAGE_1,
      text: "المادة الخامسة: يُحظر على الطرف الثاني التنازل عن هذا العقد دون موافقة كتابية مسبقة.",
    });
    renderPlacer();

    expect(await screen.findByText("المادة الخامسة: يُحظر على الطرف الثاني التنازل عن هذا العقد دون موافقة كتابية مسبقة.")).toBeTruthy();
  });

  it("text fallback renders clause blocks (heading/content layout) when block data is available", async () => {
    fetchSignatureRequestDocumentBlob.mockResolvedValue(fakePdfBlob(0xff));
    api.mockResolvedValue({
      page: 1,
      text: "ignored when blocks are present",
      char_start: 0,
      total_pages: 1,
      blocks: [
        { text: "البند الأول — نطاق العمل", bbox: [0, 0, 100, 20], direction: "rtl", column: 1 },
        { text: "يلتزم مقدم الخدمة بتنفيذ الأعمال وفق الجدول الزمني المتفق عليه.", bbox: [0, 20, 100, 40], direction: "rtl", column: 1 },
      ],
    });
    renderPlacer();

    expect(await screen.findByText("البند الأول — نطاق العمل")).toBeTruthy();
    expect(screen.getByText("يلتزم مقدم الخدمة بتنفيذ الأعمال وفق الجدول الزمني المتفق عليه.")).toBeTruthy();
  });

  it("no-document state: shows an honest, deterministic error — never claims a fallback that isn't there", async () => {
    fetchSignatureRequestDocumentBlob.mockRejectedValue(new Error("not_found"));
    api.mockRejectedValue(new Error("not_found"));
    renderPlacer();

    expect(
      await screen.findByText(
        "تعذّر عرض المستند: لا يوجد ملف PDF صالح ولا نص مستخرج لهذا العقد. يرجى إعادة استخراج النص أو رفع نسخة صالحة من المستند قبل تحديد مواضع التوقيع."
      )
    ).toBeTruthy();
    // Never the misleading "showing extracted text" claim when nothing is shown.
    expect(screen.queryByText("تعذّر عرض ملف PDF. يتم عرض النص المستخرج الآمن بدلاً منه.")).toBeNull();
  });

  it("fields cannot be saved while the viewer shows no document (empty state)", async () => {
    fetchSignatureRequestDocumentBlob.mockRejectedValue(new Error("not_found"));
    api.mockRejectedValue(new Error("not_found"));
    renderPlacer();

    await screen.findByText("يجب تحميل نسخة مرئية من المستند قبل حفظ مواضع الحقول");
    const saveButton = screen.getByText("حفظ مواضع الحقول").closest("button") as HTMLButtonElement;
    expect(saveButton.disabled).toBe(true);
  });

  it("fields cannot be saved while the document is still loading", () => {
    fetchSignatureRequestDocumentBlob.mockReturnValue(new Promise(() => {})); // never resolves
    renderPlacer();

    const saveButton = screen.getByText("حفظ مواضع الحقول").closest("button") as HTMLButtonElement;
    expect(saveButton.disabled).toBe(true);
  });

  it("switching to a different signature request refetches and refreshes the displayed document", async () => {
    const { rerender } = renderPlacer({ requestId: "request-1" });
    await waitFor(() => expect(fetchSignatureRequestDocumentBlob).toHaveBeenCalledWith("request-1"));

    rerender(
      <I18nProvider>
        <SignatureFieldPlacer
          contractId="contract-1"
          requestId="request-2"
          signers={SIGNERS}
          initialFields={[]}
          locked={false}
          onSaved={vi.fn()}
        />
      </I18nProvider>
    );

    await waitFor(() => expect(fetchSignatureRequestDocumentBlob).toHaveBeenCalledWith("request-2"));
  });
});

describe("SignatureFieldPlacer — existing behavior preserved", () => {
  it("warns that a signature field is missing until every signer has one", async () => {
    renderPlacer();
    expect(await screen.findByText("كل موقّع يحتاج حقل توقيع واحد على الأقل قبل الإرسال")).toBeTruthy();
  });

  it("adds a field on canvas click for the active signer and persists it on save", async () => {
    saveSignatureFields.mockResolvedValue({ fields: [] });
    renderPlacer();

    await waitFor(() => expect(document.querySelector("canvas")).toBeTruthy());
    const surface = document.querySelector("canvas")!.parentElement!;
    fireEvent.click(surface, { clientX: 100, clientY: 100 });

    expect(screen.getAllByText(/Signer One/).length).toBeGreaterThan(1); // select option + new marker

    fireEvent.click(screen.getByText("حفظ مواضع الحقول"));

    await waitFor(() =>
      expect(saveSignatureFields).toHaveBeenCalledWith(
        "request-1",
        expect.arrayContaining([expect.objectContaining({ signer_id: "signer-1", field_type: "signature" })])
      )
    );
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("suggested fields are visually marked and only sent to the backend on explicit save", async () => {
    suggestSignatureFields.mockResolvedValue({
      fields: [
        { signer_id: "signer-1", page_number: 1, x: 0.1, y: 0.8, width: 0.36, height: 0.06, field_type: "signature", required: true, ai_suggested: true },
      ],
    });
    renderPlacer();
    await waitFor(() => expect(document.querySelector("canvas")).toBeTruthy());

    fireEvent.click(await screen.findByText("اقتراح مواضع بالذكاء الاصطناعي"));

    expect(await screen.findByText(/اقتراح ذكاء اصطناعي/)).toBeTruthy();
    expect(saveSignatureFields).not.toHaveBeenCalled();
  });

  it("locks placement once the request has been sent", async () => {
    renderPlacer({
      locked: true,
      initialFields: [
        { id: "f1", signer_id: "signer-1", page_number: 1, x: 0.1, y: 0.1, width: 0.36, height: 0.06, field_type: "signature", required: true, ai_suggested: false },
        { id: "f2", signer_id: "signer-2", page_number: 1, x: 0.1, y: 0.3, width: 0.36, height: 0.06, field_type: "signature", required: true, ai_suggested: false },
      ],
    });

    expect(await screen.findByText("تم إرسال الطلب — لا يمكن تعديل مواضع الحقول")).toBeTruthy();
    expect(screen.queryByText("حفظ مواضع الحقول")).toBeNull();
    expect(screen.queryByText("اقتراح مواضع بالذكاء الاصطناعي")).toBeNull();
  });
});
