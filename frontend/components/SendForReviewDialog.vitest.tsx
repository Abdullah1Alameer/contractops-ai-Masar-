/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SendForReviewDialog from "@/components/SendForReviewDialog";
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

const sendContractForReview = vi.fn();

const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  apiErrorCode: (error: unknown, fallback: string) =>
    error instanceof FakeApiError ? error.code : fallback,
  sendContractForReview: (...args: unknown[]) => sendContractForReview(...args),
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

const CONTRACT_ID = "00000000-0000-0000-0000-000000000010";

function response(deliveryStatus: "sent" | "failed") {
  return {
    review_link: "https://demo.local/review/abc123token",
    email: { subject: "Please review", body: "body", review_link: "https://demo.local/review/abc123token" },
    request: { id: "review-1" },
    delivery: {
      id: "d1",
      message_type: "review_invitation",
      recipient: "client@example.invalid",
      subject: "Please review",
      contract_id: CONTRACT_ID,
      review_request_id: "review-1",
      signature_request_id: null,
      signer_id: null,
      status: deliveryStatus,
      attempt_count: 1,
      provider_message_id: deliveryStatus === "sent" ? "message-1" : null,
      safe_error_code: deliveryStatus === "failed" ? "smtp_connection_failed" : null,
      created_at: "2026-08-01T10:00:00+00:00",
      sent_at: deliveryStatus === "sent" ? "2026-08-01T10:00:01+00:00" : null,
      failed_at: deliveryStatus === "failed" ? "2026-08-01T10:00:01+00:00" : null,
    },
  };
}

function renderDialog() {
  return render(
    <I18nProvider>
      <SendForReviewDialog contractId={CONTRACT_ID} />
    </I18nProvider>
  );
}

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SendForReviewDialog delivery honesty", () => {
  it("never reports a notified success when the invitation email failed to send", async () => {
    sendContractForReview.mockResolvedValue(response("failed"));
    renderDialog();

    fireEvent.click(screen.getByText("إرسال للمراجعة"));
    fireEvent.change(screen.getByRole("textbox", { name: "اسم المستلم" }), {
      target: { value: "Client Contact" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "البريد الإلكتروني" }), {
      target: { value: "client@example.invalid" },
    });
    fireEvent.click(screen.getByText("إنشاء رابط المراجعة"));

    await waitFor(() => expect(sendContractForReview).toHaveBeenCalled());
    expect(await screen.findByText("تم إنشاء رابط المراجعة، لكن تعذّر إرسال البريد الإلكتروني. استخدم إعادة الإرسال أو انسخ الرابط يدويًا")).toBeTruthy();
    expect(screen.queryByText("تم إنشاء رابط المراجعة وإرسال البريد الإلكتروني بنجاح")).toBeNull();
    expect(toastError).toHaveBeenCalledWith("تم إنشاء رابط المراجعة، لكن تعذّر إرسال البريد الإلكتروني. استخدم إعادة الإرسال أو انسخ الرابط يدويًا");
    expect(toastSuccess).not.toHaveBeenCalled();
    // Copy Link must remain available even though delivery failed.
    expect(screen.getByText("نسخ الرابط")).toBeTruthy();
    expect(screen.getByText("https://demo.local/review/abc123token")).toBeTruthy();
  });

  it("reports a real notified success only when the email was actually sent", async () => {
    sendContractForReview.mockResolvedValue(response("sent"));
    renderDialog();

    fireEvent.click(screen.getByText("إرسال للمراجعة"));
    fireEvent.change(screen.getByRole("textbox", { name: "اسم المستلم" }), {
      target: { value: "Client Contact" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "البريد الإلكتروني" }), {
      target: { value: "client@example.invalid" },
    });
    fireEvent.click(screen.getByText("إنشاء رابط المراجعة"));

    expect(await screen.findByText("تم إنشاء رابط المراجعة وإرسال البريد الإلكتروني بنجاح")).toBeTruthy();
    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith("تم إنشاء رابط المراجعة وإرسال البريد الإلكتروني بنجاح")
    );
    expect(toastError).not.toHaveBeenCalled();
    expect(screen.getByText("نسخ الرابط")).toBeTruthy();
  });

  it("surfaces the deterministic API error code when the request itself fails", async () => {
    sendContractForReview.mockRejectedValue(new FakeApiError(422, "invalid_email"));
    renderDialog();

    fireEvent.click(screen.getByText("إرسال للمراجعة"));
    fireEvent.change(screen.getByRole("textbox", { name: "اسم المستلم" }), {
      target: { value: "Client Contact" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "البريد الإلكتروني" }), {
      target: { value: "client@example.invalid" },
    });
    fireEvent.click(screen.getByText("إنشاء رابط المراجعة"));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("invalid_email"));
    expect(toastSuccess).not.toHaveBeenCalled();
  });
});
