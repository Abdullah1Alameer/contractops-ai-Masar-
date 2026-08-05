/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SignaturePanel from "@/components/SignaturePanel";
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

const activateSignatureRequest = vi.fn();
const cancelSignatureRequest = vi.fn();
const fetchSignatureBundle = vi.fn();
const downloadSignedPdf = vi.fn();
const downloadSignatureCertificate = vi.fn();
const resendSignatureSigner = vi.fn();
const sendSignatureRequest = vi.fn();

const toastSuccess = vi.fn();
const toastError = vi.fn();
const toastInfo = vi.fn();

vi.mock("@/lib/api", () => ({
  apiErrorCode: (error: unknown, fallback: string) =>
    error instanceof FakeApiError ? error.code : fallback,
  activateSignatureRequest: (...args: unknown[]) => activateSignatureRequest(...args),
  cancelSignatureRequest: (...args: unknown[]) => cancelSignatureRequest(...args),
  createSignatureRequest: vi.fn(),
  downloadSignatureCertificate: (...args: unknown[]) => downloadSignatureCertificate(...args),
  downloadSignedPdf: (...args: unknown[]) => downloadSignedPdf(...args),
  fetchSignatureBundle: (...args: unknown[]) => fetchSignatureBundle(...args),
  resendSignatureSigner: (...args: unknown[]) => resendSignatureSigner(...args),
  sendSignatureRequest: (...args: unknown[]) => sendSignatureRequest(...args),
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

vi.mock("@/components/feedback/ConfirmDialog", () => ({
  useConfirm: () => ({
    confirm: async (opts: { onConfirm: () => void | Promise<void> }) => {
      await opts.onConfirm();
      return true;
    },
  }),
}));

vi.mock("@/components/CreateSignatureDialog", () => ({
  default: () => null,
}));

const CONTRACT_ID = "00000000-0000-0000-0000-000000000001";
const REQUEST_ID = "11111111-1111-1111-1111-111111111111";

function bundle(status: string) {
  return {
    request: {
      id: REQUEST_ID,
      contract_id: CONTRACT_ID,
      provider: "simulated",
      status,
      subject: "Please sign",
      message: null,
      signing_order_enabled: true,
      expires_at: "2026-12-01T00:00:00+00:00",
      sent_at: null,
      completed_at: null,
      signed_file_url: "signed.pdf",
      certificate_file_url: "cert.pdf",
      signers: [
        {
          id: "signer-1",
          signer_order: 1,
          name: "Signer One",
          email: "one@example.invalid",
          role: "company_signatory",
          status: "signed",
        },
      ],
      progress: { completed: 1, total: 1 },
      is_stale: false,
    },
    events: [],
    can_create: false,
  };
}

function renderPanel(contractStage: string, onLifecycleChange?: () => void | Promise<void>) {
  return render(
    <I18nProvider>
      <SignaturePanel
        contractId={CONTRACT_ID}
        contractStage={contractStage}
        onLifecycleChange={onLifecycleChange}
      />
    </I18nProvider>
  );
}

// The project vitest config does not enable globals, so auto-cleanup is not registered.
afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  fetchSignatureBundle.mockResolvedValue(bundle("completed"));
  activateSignatureRequest.mockResolvedValue(bundle("completed"));
  cancelSignatureRequest.mockResolvedValue(bundle("cancelled"));
  downloadSignedPdf.mockResolvedValue(new Blob(["signed"]));
  downloadSignatureCertificate.mockResolvedValue(new Blob(["cert"]));
});

describe("SignaturePanel artifacts and activation gating", () => {
  it("keeps signed artifact downloads on an active contract while hiding the activation form", async () => {
    renderPanel("active");

    expect(await screen.findByText("تنزيل العقد الموقّع")).toBeTruthy();
    expect(screen.getByText("تنزيل شهادة التوقيع")).toBeTruthy();
    expect(screen.queryByLabelText("سبب التفعيل")).toBeNull();
    expect(screen.queryByText("تفعيل العقد")).toBeNull();
  });

  it("keeps signed artifact downloads on a stage that follows activation", async () => {
    renderPanel("completed");

    expect(await screen.findByText("تنزيل العقد الموقّع")).toBeTruthy();
    expect(screen.getByText("تنزيل شهادة التوقيع")).toBeTruthy();
    expect(screen.queryByLabelText("سبب التفعيل")).toBeNull();
  });

  it("offers artifact downloads and the activation form on a signed contract", async () => {
    renderPanel("signed");

    expect(await screen.findByText("تنزيل العقد الموقّع")).toBeTruthy();
    expect(screen.getByText("تنزيل شهادة التوقيع")).toBeTruthy();
    expect(screen.getByLabelText("سبب التفعيل")).toBeTruthy();
    expect(screen.getByLabelText("دليل التفعيل")).toBeTruthy();
  });

  it("downloads the signed contract and the certificate for the completed request", async () => {
    const createObjectURL = vi.fn().mockReturnValue("blob:artifact");
    Object.defineProperty(URL, "createObjectURL", { value: createObjectURL, writable: true });
    Object.defineProperty(window, "open", { value: vi.fn(), writable: true });
    renderPanel("active");

    fireEvent.click(await screen.findByText("تنزيل العقد الموقّع"));
    await waitFor(() => expect(downloadSignedPdf).toHaveBeenCalledWith(REQUEST_ID));

    fireEvent.click(screen.getByText("تنزيل شهادة التوقيع"));
    await waitFor(() => expect(downloadSignatureCertificate).toHaveBeenCalledWith(REQUEST_ID));
  });
});

describe("SignaturePanel activation", () => {
  it("blocks activation and reports each missing field distinctly", async () => {
    renderPanel("signed");
    const activate = await screen.findByText("تفعيل العقد");

    fireEvent.click(activate);
    await waitFor(() => expect(toastError).toHaveBeenCalledWith("سبب التفعيل مطلوب قبل تفعيل العقد"));
    expect(activateSignatureRequest).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("سبب التفعيل"), {
      target: { value: "Counterparty countersigned" },
    });
    fireEvent.click(activate);
    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("دليل التفعيل مطلوب قبل تفعيل العقد")
    );
    expect(activateSignatureRequest).not.toHaveBeenCalled();
  });

  it("sends the trimmed reason and evidence, refreshes the lifecycle, and confirms success", async () => {
    const onLifecycleChange = vi.fn();
    renderPanel("signed", onLifecycleChange);

    fireEvent.change(await screen.findByLabelText("سبب التفعيل"), {
      target: { value: "  Counterparty countersigned  " },
    });
    fireEvent.change(screen.getByLabelText("دليل التفعيل"), {
      target: { value: "  Wet-ink scan filed  " },
    });
    fireEvent.click(screen.getByText("تفعيل العقد"));

    await waitFor(() =>
      expect(activateSignatureRequest).toHaveBeenCalledWith(
        REQUEST_ID,
        "Counterparty countersigned",
        "Wet-ink scan filed"
      )
    );
    await waitFor(() => expect(onLifecycleChange).toHaveBeenCalled());
    expect(toastSuccess).toHaveBeenCalledWith("تم تفعيل العقد");
    expect(toastError).not.toHaveBeenCalled();
  });

  it("surfaces the backend error code and leaves the lifecycle untouched", async () => {
    const onLifecycleChange = vi.fn();
    activateSignatureRequest.mockRejectedValue(new FakeApiError(409, "activation_not_ready"));
    renderPanel("signed", onLifecycleChange);

    fireEvent.change(await screen.findByLabelText("سبب التفعيل"), {
      target: { value: "Counterparty countersigned" },
    });
    fireEvent.change(screen.getByLabelText("دليل التفعيل"), {
      target: { value: "Wet-ink scan filed" },
    });
    fireEvent.click(screen.getByText("تفعيل العقد"));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("activation_not_ready"));
    expect(onLifecycleChange).not.toHaveBeenCalled();
    expect(toastSuccess).not.toHaveBeenCalled();
  });

  it("hides the activation form once the reloaded contract is active", async () => {
    const { rerender } = renderPanel("signed");
    expect(await screen.findByLabelText("سبب التفعيل")).toBeTruthy();

    rerender(
      <I18nProvider>
        <SignaturePanel contractId={CONTRACT_ID} contractStage="active" />
      </I18nProvider>
    );

    await waitFor(() => expect(screen.queryByLabelText("سبب التفعيل")).toBeNull());
    expect(screen.getByText("تنزيل العقد الموقّع")).toBeTruthy();
  });
});

describe("SignaturePanel cancellation", () => {
  it("requires a reason, then submits it and refreshes the lifecycle", async () => {
    const onLifecycleChange = vi.fn();
    fetchSignatureBundle.mockResolvedValue(bundle("sent"));
    renderPanel("ready_to_sign", onLifecycleChange);

    const cancel = await screen.findByText("إلغاء الطلب");
    fireEvent.click(cancel);
    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("سبب الإلغاء مطلوب قبل إلغاء الطلب")
    );
    expect(cancelSignatureRequest).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("سبب إلغاء طلب التوقيع"), {
      target: { value: "  Signer package replaced  " },
    });
    fireEvent.click(cancel);

    await waitFor(() =>
      expect(cancelSignatureRequest).toHaveBeenCalledWith(REQUEST_ID, "Signer package replaced")
    );
    await waitFor(() => expect(onLifecycleChange).toHaveBeenCalled());
    expect(toastSuccess).toHaveBeenCalledWith("تم إلغاء طلب التوقيع");
  });
});

function draftBundle() {
  return {
    request: {
      id: REQUEST_ID,
      contract_id: CONTRACT_ID,
      provider: "simulated",
      status: "draft",
      subject: "Please sign",
      message: null,
      signing_order_enabled: true,
      expires_at: "2026-12-01T00:00:00+00:00",
      sent_at: null,
      completed_at: null,
      signed_file_url: null,
      certificate_file_url: null,
      signers: [
        {
          id: "signer-1",
          signer_order: 1,
          name: "Signer One",
          email: "one@example.invalid",
          role: "company_signatory",
          status: "waiting",
        },
      ],
      progress: { completed: 0, total: 1 },
      is_stale: false,
    },
    events: [],
    can_create: false,
  };
}

describe("SignaturePanel send honesty", () => {
  it("reports a real sent success only when every delivery is sent", async () => {
    fetchSignatureBundle.mockResolvedValue(draftBundle());
    sendSignatureRequest.mockResolvedValue({ deliveries: [{ status: "sent" }] });
    renderPanel("ready_to_sign");

    fireEvent.click(await screen.findByText("إرسال طلب التوقيع"));

    await waitFor(() => expect(sendSignatureRequest).toHaveBeenCalledWith(REQUEST_ID));
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith("تم إرسال طلب التوقيع"));
    expect(toastError).not.toHaveBeenCalled();
    expect(toastInfo).not.toHaveBeenCalled();
  });

  it("never claims success when any delivery failed", async () => {
    fetchSignatureBundle.mockResolvedValue(draftBundle());
    sendSignatureRequest.mockResolvedValue({ deliveries: [{ status: "failed" }] });
    renderPanel("ready_to_sign");

    fireEvent.click(await screen.findByText("إرسال طلب التوقيع"));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("تعذّر إرسال دعوة التوقيع"));
    expect(toastSuccess).not.toHaveBeenCalled();
  });

  it("never claims success when delivery is still pending/sending/cancelled/absent", async () => {
    fetchSignatureBundle.mockResolvedValue(draftBundle());
    sendSignatureRequest.mockResolvedValue({ deliveries: [{ status: "pending" }] });
    renderPanel("ready_to_sign");

    fireEvent.click(await screen.findByText("إرسال طلب التوقيع"));

    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith("دعوة التوقيع قيد الإرسال"));
    expect(toastSuccess).not.toHaveBeenCalled();
    expect(toastError).not.toHaveBeenCalled();
  });
});

function allSignerStatusesBundle() {
  const statuses = ["waiting", "invited", "opened", "signed", "declined", "expired"];
  return {
    request: {
      id: REQUEST_ID,
      contract_id: CONTRACT_ID,
      provider: "simulated",
      status: "partially_signed",
      subject: "Please sign",
      message: null,
      signing_order_enabled: false,
      expires_at: "2026-12-01T00:00:00+00:00",
      sent_at: "2026-08-01T09:00:00+00:00",
      completed_at: null,
      signed_file_url: null,
      certificate_file_url: null,
      signers: statuses.map((status, index) => ({
        id: `signer-${index + 1}`,
        signer_order: index + 1,
        name: `Signer ${index + 1}`,
        email: `signer${index + 1}@example.invalid`,
        role: "other",
        status,
        eligible: false,
        signer_link: null,
        delivery: null,
      })),
      progress: { completed: 1, total: statuses.length },
      is_stale: false,
    },
    events: [],
    can_create: false,
  };
}

describe("SignaturePanel signer status labels", () => {
  it("shows a visible bilingual label for every signer status (waiting/invited/opened/signed/declined/expired), never a blank status", async () => {
    fetchSignatureBundle.mockResolvedValue(allSignerStatusesBundle());
    renderPanel("ready_to_sign");

    const expectedLabels = [
      "بانتظار الدور",
      "تمت الدعوة",
      "تم الفتح",
      "تم التوقيع",
      "مرفوض",
      "منتهي",
    ];
    for (let i = 0; i < expectedLabels.length; i++) {
      const row = await screen.findByText(new RegExp(`Signer ${i + 1}`));
      expect(row.textContent).toContain(expectedLabels[i]);
    }
  });
});

const SIGNER_ONE = "signer-1";
const SIGNER_TWO = "signer-2";

function orderedBundle() {
  return {
    request: {
      id: REQUEST_ID,
      contract_id: CONTRACT_ID,
      provider: "simulated",
      status: "sent",
      subject: "Please sign",
      message: null,
      signing_order_enabled: true,
      expires_at: "2026-12-01T00:00:00+00:00",
      sent_at: "2026-08-01T09:00:00+00:00",
      completed_at: null,
      signed_file_url: null,
      certificate_file_url: null,
      signers: [
        {
          id: SIGNER_ONE,
          signer_order: 1,
          name: "Signer One",
          email: "one@example.invalid",
          role: "company_signatory",
          status: "invited",
          eligible: true,
          signer_link: "https://demo.local/sign/first-signer-token",
          delivery: {
            id: "d1",
            message_type: "signature_invitation",
            recipient: "one@example.invalid",
            subject: "Please sign",
            contract_id: CONTRACT_ID,
            review_request_id: null,
            signature_request_id: REQUEST_ID,
            signer_id: SIGNER_ONE,
            status: "sent",
            attempt_count: 1,
            provider_message_id: "message-1",
            safe_error_code: null,
            created_at: "2026-08-01T09:00:00+00:00",
            sent_at: "2026-08-01T09:00:01+00:00",
            failed_at: null,
          },
        },
        {
          id: SIGNER_TWO,
          signer_order: 2,
          name: "Signer Two",
          email: "two@example.invalid",
          role: "client_signatory",
          status: "waiting",
          eligible: false,
          signer_link: null,
          delivery: null,
        },
      ],
      progress: { completed: 0, total: 2 },
      is_stale: false,
    },
    events: [],
    can_create: false,
  };
}

describe("SignaturePanel signer delivery and eligibility", () => {
  it("shows persisted delivery status, attempts, and timestamp for the eligible signer only", async () => {
    fetchSignatureBundle.mockResolvedValue(orderedBundle());
    renderPanel("ready_to_sign");

    expect(await screen.findByText("تم الإرسال")).toBeTruthy();
    expect(screen.getByText(/عدد المحاولات: 1/)).toBeTruthy();
    expect(screen.getByText(/وقت الإرسال/)).toBeTruthy();
  });

  it("offers Retry and Copy Link only for the eligible signer, never for a future waiting signer", async () => {
    fetchSignatureBundle.mockResolvedValue(orderedBundle());
    renderPanel("ready_to_sign");

    await screen.findByText("تم الإرسال");
    const resendButtons = screen.getAllByText("إعادة إرسال");
    expect(resendButtons).toHaveLength(1);
    const copyButtons = screen.getAllByText("نسخ رابط الموقّع");
    expect(copyButtons).toHaveLength(1);
  });

  it("resends the eligible signer and reports a real notified success", async () => {
    fetchSignatureBundle.mockResolvedValue(orderedBundle());
    resendSignatureSigner.mockResolvedValue({
      signer_link: "https://demo.local/sign/first-signer-token",
      token: "first-signer-token",
      email: {},
      delivery: { status: "sent" },
    });
    renderPanel("ready_to_sign");

    fireEvent.click(await screen.findByText("إعادة إرسال"));

    await waitFor(() => expect(resendSignatureSigner).toHaveBeenCalledWith(REQUEST_ID, SIGNER_ONE));
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith("تم إرسال دعوة التوقيع"));
  });

  it("never reports a notified success when the resend delivery failed", async () => {
    fetchSignatureBundle.mockResolvedValue(orderedBundle());
    resendSignatureSigner.mockResolvedValue({
      signer_link: "https://demo.local/sign/first-signer-token",
      token: "first-signer-token",
      email: {},
      delivery: { status: "failed", safe_error_code: "smtp_connection_failed" },
    });
    renderPanel("ready_to_sign");

    fireEvent.click(await screen.findByText("إعادة إرسال"));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("تعذّر إرسال دعوة التوقيع"));
    expect(toastSuccess).not.toHaveBeenCalled();
  });

  it("copies the persisted signing link for the eligible signer", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    fetchSignatureBundle.mockResolvedValue(orderedBundle());
    renderPanel("ready_to_sign");

    fireEvent.click(await screen.findByText("نسخ رابط الموقّع"));

    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith("https://demo.local/sign/first-signer-token")
    );
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith("تم النسخ"));
  });

  it("never reports a notified success when the resend delivery is still pending/sending/cancelled", async () => {
    fetchSignatureBundle.mockResolvedValue(orderedBundle());
    resendSignatureSigner.mockResolvedValue({
      signer_link: "https://demo.local/sign/first-signer-token",
      token: "first-signer-token",
      email: {},
      delivery: { status: "cancelled" },
    });
    renderPanel("ready_to_sign");

    fireEvent.click(await screen.findByText("إعادة إرسال"));

    await waitFor(() => expect(toastInfo).toHaveBeenCalledWith("دعوة التوقيع قيد الإرسال"));
    expect(toastSuccess).not.toHaveBeenCalled();
    expect(toastError).not.toHaveBeenCalled();
  });

  it("surfaces a deterministic error when copying the signing link fails instead of failing silently", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    Object.assign(navigator, { clipboard: { writeText } });
    fetchSignatureBundle.mockResolvedValue(orderedBundle());
    renderPanel("ready_to_sign");

    fireEvent.click(await screen.findByText("نسخ رابط الموقّع"));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("تعذّر نسخ الرابط"));
    expect(toastSuccess).not.toHaveBeenCalled();
  });

  it("shows the signer's recipient email and the delivery's recorded recipient", async () => {
    fetchSignatureBundle.mockResolvedValue(orderedBundle());
    renderPanel("ready_to_sign");

    const signerOneRow = await screen.findByText(/Signer One/);
    expect(signerOneRow.textContent).toContain("one@example.invalid");
    expect(screen.getByText(/المستلم: one@example.invalid/)).toBeTruthy();
  });

  it("keeps exactly one scoped Copy action after a resend — no redundant ephemeral top-level copy button", async () => {
    fetchSignatureBundle.mockResolvedValue(orderedBundle());
    resendSignatureSigner.mockResolvedValue({
      signer_link: "https://demo.local/sign/first-signer-token",
      token: "first-signer-token",
      email: {},
      delivery: { status: "sent" },
    });
    renderPanel("ready_to_sign");

    fireEvent.click(await screen.findByText("إعادة إرسال"));
    await waitFor(() => expect(resendSignatureSigner).toHaveBeenCalled());

    await waitFor(() =>
      expect(screen.getAllByText("نسخ رابط الموقّع")).toHaveLength(1)
    );
  });
});
