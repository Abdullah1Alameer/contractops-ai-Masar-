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

const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  apiErrorCode: (error: unknown, fallback: string) =>
    error instanceof FakeApiError ? error.code : fallback,
  activateSignatureRequest: (...args: unknown[]) => activateSignatureRequest(...args),
  cancelSignatureRequest: (...args: unknown[]) => cancelSignatureRequest(...args),
  createSignatureRequest: vi.fn(),
  downloadSignatureCertificate: (...args: unknown[]) => downloadSignatureCertificate(...args),
  downloadSignedPdf: (...args: unknown[]) => downloadSignedPdf(...args),
  fetchSignatureBundle: (...args: unknown[]) => fetchSignatureBundle(...args),
  resendSignatureSigner: vi.fn(),
  sendSignatureRequest: vi.fn(),
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
