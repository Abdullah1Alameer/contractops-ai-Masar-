/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SignPage from "@/app/sign/[token]/page";
import { I18nProvider } from "@/lib/i18n";

class FakeApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

const openSignerPortal = vi.fn();
const submitSignerPortal = vi.fn();
const declineSignerPortal = vi.fn();

const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ token: "demo-token" }),
}));

vi.mock("@/lib/api", () => ({
  apiErrorCode: (error: unknown, fallback: string) =>
    error instanceof FakeApiError ? error.code : fallback,
  openSignerPortal: (...args: unknown[]) => openSignerPortal(...args),
  submitSignerPortal: (...args: unknown[]) => submitSignerPortal(...args),
  declineSignerPortal: (...args: unknown[]) => declineSignerPortal(...args),
  publicSignDocumentUrl: (token: string) => `https://demo.local/api/public/sign/${token}/document`,
}));

vi.mock("@/components/feedback/ToastProvider", () => ({
  useToast: () => ({
    success: toastSuccess,
    error: toastError,
    warning: vi.fn(),
    info: vi.fn(),
    toast: vi.fn(),
  }),
}));

vi.mock("@/components/SignatureCanvas", () => ({ default: () => null }));
vi.mock("@/components/TypedSignaturePreview", () => ({ default: () => null }));
vi.mock("@/components/SignerDocumentViewer", () => ({ default: () => null }));

const DISCLOSURE_TEXT =
  "Demo electronic signature / توقيع إلكتروني تجريبي — هذا نموذج تجريبي وليس مزود توقيع إلكتروني معتمد قانونًا / this is a demo prototype, not a certified legally binding e-signature provider.";

function renderPage() {
  return render(
    <I18nProvider>
      <SignPage />
    </I18nProvider>
  );
}

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Public sign page — deterministic errors and disclosure", () => {
  it("shows the bilingual demo disclosure while loading", () => {
    openSignerPortal.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByText(DISCLOSURE_TEXT)).toBeTruthy();
  });

  it("surfaces the deterministic API error code instead of a generic silent failure", async () => {
    openSignerPortal.mockRejectedValue(new FakeApiError(410, "expired"));
    renderPage();

    expect(await screen.findByText(/expired/)).toBeTruthy();
    expect(screen.getByText(DISCLOSURE_TEXT)).toBeTruthy();
  });

  it("shows the workflow_stale error and hides/disables the signing form instead of masking it with a second call", async () => {
    openSignerPortal.mockRejectedValue(new FakeApiError(409, "workflow_stale"));
    renderPage();

    expect(await screen.findByText(/workflow_stale/)).toBeTruthy();
    // The active signing form (submit button, name-confirmation field) must never
    // render while the open call is rejected — no fallback read may mask this.
    expect(screen.queryByText("توقيع وإرسال")).toBeNull();
    expect(screen.queryByPlaceholderText("تأكيد الاسم كما في الدعوة")).toBeNull();
    expect(openSignerPortal).toHaveBeenCalledTimes(1);
  });

  it("retries through the same deterministic open call, not a separate less-strict read", async () => {
    openSignerPortal.mockRejectedValue(new FakeApiError(409, "workflow_stale"));
    renderPage();

    await screen.findByText(/workflow_stale/);
    fireEvent.click(screen.getByText("إعادة المحاولة"));

    await waitFor(() => expect(openSignerPortal).toHaveBeenCalledTimes(2));
  });

  it("keeps the disclosure visible on the declined state", async () => {
    openSignerPortal.mockResolvedValue({
      contract_title: "Contract",
      sender_name: "Ops",
      subject: "Please sign",
      message: null,
      signer: { name: "Signer One", role: "company_signatory", order: 1, status: "declined", opened_at: null, signed_at: null },
      progress: { completed: 0, total: 1, order_enabled: true },
      expires_at: "2026-12-01T00:00:00+00:00",
      consent_text: { en: "I agree", ar: "أوافق" },
      document_url: "doc",
      provider_label: "simulated",
      request_status: "declined",
      waiting_for_prior: false,
      read_only: true,
      declined: true,
    });
    renderPage();

    expect(await screen.findByText("تم رفض التوقيع")).toBeTruthy();
    expect(screen.getByText(DISCLOSURE_TEXT)).toBeTruthy();
  });

  it("keeps the disclosure visible while waiting for a prior signer", async () => {
    openSignerPortal.mockResolvedValue({
      contract_title: "Contract",
      sender_name: "Ops",
      subject: "Please sign",
      message: null,
      signer: { name: "Signer Two", role: "client_signatory", order: 2, status: "waiting", opened_at: null, signed_at: null },
      progress: { completed: 0, total: 2, order_enabled: true },
      expires_at: "2026-12-01T00:00:00+00:00",
      consent_text: { en: "I agree", ar: "أوافق" },
      document_url: "doc",
      provider_label: "simulated",
      request_status: "sent",
      waiting_for_prior: true,
      read_only: false,
      declined: false,
    });
    renderPage();

    expect(await screen.findByText("هذا المستند غير جاهز لتوقيعك بعد.")).toBeTruthy();
    expect(screen.getByText(DISCLOSURE_TEXT)).toBeTruthy();
  });

  it("keeps the disclosure visible on the active signing form", async () => {
    openSignerPortal.mockResolvedValue({
      contract_title: "Contract",
      sender_name: "Ops",
      subject: "Please sign",
      message: null,
      signer: { name: "Signer One", role: "company_signatory", order: 1, status: "invited", opened_at: null, signed_at: null },
      progress: { completed: 0, total: 1, order_enabled: true },
      expires_at: "2026-12-01T00:00:00+00:00",
      consent_text: { en: "I agree", ar: "أوافق" },
      document_url: "doc",
      provider_label: "simulated",
      request_status: "sent",
      waiting_for_prior: false,
      read_only: false,
      declined: false,
      fields: [],
    });
    renderPage();

    expect(await screen.findByText("Please sign")).toBeTruthy();
    expect(screen.getByText(DISCLOSURE_TEXT)).toBeTruthy();
  });

  it("reports a deterministic error code via toast when decline fails instead of failing silently", async () => {
    openSignerPortal.mockResolvedValue({
      contract_title: "Contract",
      sender_name: "Ops",
      subject: "Please sign",
      message: null,
      signer: { name: "Signer One", role: "company_signatory", order: 1, status: "invited", opened_at: null, signed_at: null },
      progress: { completed: 0, total: 1, order_enabled: true },
      expires_at: "2026-12-01T00:00:00+00:00",
      consent_text: { en: "I agree", ar: "أوافق" },
      document_url: "doc",
      provider_label: "simulated",
      request_status: "sent",
      waiting_for_prior: false,
      read_only: false,
      declined: false,
      fields: [],
    });
    declineSignerPortal.mockRejectedValue(new FakeApiError(409, "not_active_signer"));
    renderPage();

    await screen.findByText("Please sign");
    fireEvent.change(screen.getByPlaceholderText("رفض التوقيع"), {
      target: { value: "Not the right signer" },
    });
    fireEvent.click(screen.getByText("رفض التوقيع"));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("تعذّر إتمام الإجراء — رمز الخطأ: not_active_signer")
    );
  });
});
