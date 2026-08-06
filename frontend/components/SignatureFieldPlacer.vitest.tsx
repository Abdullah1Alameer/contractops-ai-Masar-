/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: () => ({
    promise: Promise.resolve({
      numPages: 2,
      getPage: () =>
        Promise.resolve({
          getViewport: () => ({ width: 595, height: 842, scale: 1.2 }),
          render: () => ({ promise: Promise.resolve() }),
        }),
    }),
  }),
}));

const fetchContractFileBlob = vi.fn();
const suggestSignatureFields = vi.fn();
const saveSignatureFields = vi.fn();

vi.mock("@/lib/api", () => ({
  apiErrorCode: (_error: unknown, fallback: string) => fallback,
  fetchContractFileBlob: (...args: unknown[]) => fetchContractFileBlob(...args),
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

function fakePdfBlob(): Blob {
  // jsdom's Blob shim has no arrayBuffer() implementation — stub one so the
  // component's `await blob.arrayBuffer()` resolves instead of throwing.
  const blob = new Blob(["%PDF-1.4"], { type: "application/pdf" });
  (blob as unknown as { arrayBuffer: () => Promise<ArrayBuffer> }).arrayBuffer = () =>
    Promise.resolve(new ArrayBuffer(8));
  return blob;
}

beforeEach(() => {
  vi.clearAllMocks();
  fetchContractFileBlob.mockResolvedValue(fakePdfBlob());
});

describe("SignatureFieldPlacer", () => {
  it("warns that a signature field is missing until every signer has one", async () => {
    renderPlacer();
    expect(await screen.findByText("كل موقّع يحتاج حقل توقيع واحد على الأقل قبل الإرسال")).toBeTruthy();
  });

  it("adds a field on canvas click for the active signer and persists it on save", async () => {
    saveSignatureFields.mockResolvedValue({ fields: [] });
    renderPlacer();

    const canvas = await screen.findByRole("img", { hidden: true }).catch(() => null);
    // Fall back to querying the canvas directly since <canvas> has no default role.
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
