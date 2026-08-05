/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ReviewHistoryPanel from "@/components/ReviewHistoryPanel";
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

const fetchContractReviews = vi.fn();
const fetchVersions = vi.fn();
const resendContractReview = vi.fn();

const toastSuccess = vi.fn();
const toastError = vi.fn();
const toastInfo = vi.fn();

vi.mock("@/lib/api", () => ({
  apiErrorCode: (error: unknown, fallback: string) =>
    error instanceof FakeApiError ? error.code : fallback,
  fetchContractReviews: (...args: unknown[]) => fetchContractReviews(...args),
  fetchVersions: (...args: unknown[]) => fetchVersions(...args),
  resendContractReview: (...args: unknown[]) => resendContractReview(...args),
  sendContractForReview: vi.fn(),
}));

vi.mock("@/components/feedback/ToastProvider", () => ({
  useToast: () => ({
    success: toastSuccess,
    error: toastError,
    warning: vi.fn(),
    info: (...args: unknown[]) => toastInfo(...args),
    toast: vi.fn(),
  }),
}));

const CONTRACT_ID = "00000000-0000-0000-0000-000000000020";
const REVIEW_ID = "22222222-2222-2222-2222-222222222222";

function row(overrides: Record<string, unknown> = {}) {
  return {
    id: REVIEW_ID,
    contract_id: CONTRACT_ID,
    recipient_name: "Jane Client",
    recipient_email: "jane@example.invalid",
    sender_name: null,
    sender_email: null,
    message: null,
    status: "sent",
    expires_at: "2026-12-01T00:00:00+00:00",
    opened_at: null,
    responded_at: null,
    created_at: "2026-08-01T10:00:00+00:00",
    comments: [],
    decision: null,
    overall_comment: null,
    review_link: "https://demo.local/review/abc123token",
    token: "abc123token",
    is_stale: false,
    actionable: true,
    delivery: {
      id: "d1",
      message_type: "review_invitation",
      recipient: "jane@example.invalid",
      subject: "Please review",
      contract_id: CONTRACT_ID,
      review_request_id: REVIEW_ID,
      signature_request_id: null,
      signer_id: null,
      status: "failed",
      attempt_count: 1,
      provider_message_id: null,
      safe_error_code: "smtp_connection_failed",
      created_at: "2026-08-01T10:00:00+00:00",
      sent_at: null,
      failed_at: "2026-08-01T10:00:01+00:00",
    },
    ...overrides,
  };
}

function renderPanel() {
  return render(
    <I18nProvider>
      <ReviewHistoryPanel contractId={CONTRACT_ID} />
    </I18nProvider>
  );
}

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  fetchVersions.mockResolvedValue({ versions: [], current_version_number: null, total_versions: 0 });
});

describe("ReviewHistoryPanel persisted delivery", () => {
  it("shows recipient, failed delivery status, attempts, and failed timestamp after refresh", async () => {
    fetchContractReviews.mockResolvedValue([row()]);
    renderPanel();

    expect(await screen.findByText(/jane@example.invalid/)).toBeTruthy();
    expect(screen.getByText("فشل الإرسال")).toBeTruthy();
    expect(screen.getByText(/عدد المحاولات: 1/)).toBeTruthy();
    expect(screen.getByText(/وقت الفشل/)).toBeTruthy();
    expect(screen.getByText(/smtp_connection_failed/)).toBeTruthy();
    // Copy Review Link remains available for a failed delivery.
    expect(screen.getByText("نسخ الرابط")).toBeTruthy();
  });

  it("shows sent delivery status, attempts, and sent timestamp after refresh", async () => {
    fetchContractReviews.mockResolvedValue([
      row({
        delivery: {
          id: "d2",
          message_type: "review_invitation",
          recipient: "jane@example.invalid",
          subject: "Please review",
          contract_id: CONTRACT_ID,
          review_request_id: REVIEW_ID,
          signature_request_id: null,
          signer_id: null,
          status: "sent",
          attempt_count: 2,
          provider_message_id: "message-2",
          safe_error_code: null,
          created_at: "2026-08-01T10:05:00+00:00",
          sent_at: "2026-08-01T10:05:01+00:00",
          failed_at: null,
        },
      }),
    ]);
    renderPanel();

    expect(await screen.findByText("تم الإرسال")).toBeTruthy();
    expect(screen.getByText(/عدد المحاولات: 2/)).toBeTruthy();
    expect(screen.getByText(/وقت الإرسال/)).toBeTruthy();
  });

  it("calls resend when Retry Email is clicked and reports the delivery outcome", async () => {
    fetchContractReviews.mockResolvedValue([row()]);
    resendContractReview.mockResolvedValue({
      review_link: "https://demo.local/review/abc123token",
      email: { subject: "Please review", body: "body", review_link: "https://demo.local/review/abc123token" },
      request: row(),
      delivery: { status: "sent" },
    });
    renderPanel();

    fireEvent.click(await screen.findByText("إعادة إرسال البريد"));

    await waitFor(() => expect(resendContractReview).toHaveBeenCalledWith(CONTRACT_ID, REVIEW_ID));
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith("تمت إعادة إرسال البريد الإلكتروني"));
  });

  it("does not offer Retry Email for a non-actionable review", async () => {
    fetchContractReviews.mockResolvedValue([row({ actionable: false })]);
    renderPanel();

    await screen.findByText(/jane@example.invalid/);
    expect(screen.queryByText("إعادة إرسال البريد")).toBeNull();
  });

  it("copies the review link when Copy Link is clicked", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    fetchContractReviews.mockResolvedValue([row()]);
    renderPanel();

    fireEvent.click(await screen.findByText("نسخ الرابط"));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith("https://demo.local/review/abc123token"));
  });

  it("surfaces a deterministic error code when retry itself fails", async () => {
    fetchContractReviews.mockResolvedValue([row()]);
    resendContractReview.mockRejectedValue(new FakeApiError(429, "email_resend_cooldown"));
    renderPanel();

    fireEvent.click(await screen.findByText("إعادة إرسال البريد"));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("email_resend_cooldown"));
  });

  it("never claims a real resend when the retry delivery is still pending/sending/cancelled", async () => {
    fetchContractReviews.mockResolvedValue([row()]);
    resendContractReview.mockResolvedValue({
      review_link: "https://demo.local/review/abc123token",
      email: { subject: "Please review", body: "body", review_link: "https://demo.local/review/abc123token" },
      request: row(),
      delivery: { status: "cancelled" },
    });
    renderPanel();

    fireEvent.click(await screen.findByText("إعادة إرسال البريد"));

    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith("إعادة إرسال البريد قيد المعالجة"));
    expect(toastSuccess).not.toHaveBeenCalled();
    expect(toastError).not.toHaveBeenCalled();
  });

  it("surfaces a deterministic error when copying the review link fails instead of failing silently", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    Object.assign(navigator, { clipboard: { writeText } });
    fetchContractReviews.mockResolvedValue([row()]);
    renderPanel();

    fireEvent.click(await screen.findByText("نسخ الرابط"));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("تعذّر نسخ الرابط"));
  });
});
