/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ContractHeader from "@/components/contract/ContractHeader";
import { I18nProvider } from "@/lib/i18n";
import type { ContractDetail } from "@/lib/types";

const markContractReadyForClient = vi.fn();
const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  apiErrorCode: (_error: unknown, fallback: string) => fallback,
  sendContractForReview: vi.fn(),
  markContractReadyForClient: (...args: unknown[]) => markContractReadyForClient(...args),
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

function detail(overrides: Partial<ContractDetail> = {}): ContractDetail {
  return {
    id: "00000000-0000-0000-0000-000000000030",
    title: "Synthetic contract",
    type: "main",
    parent_main_contract_id: null,
    party_a: null,
    party_b: "Beta LLC",
    value_sar: null,
    start_date: null,
    end_date: null,
    governing_law: null,
    retention_pct: null,
    bond_expiry: null,
    warranty_end: null,
    language: null,
    calendar: null,
    status: "ready",
    stage: "ready_for_client",
    contract_category: null,
    supported: true,
    classification_confidence: null,
    classification_message: null,
    extractions: [],
    ...overrides,
  };
}

function renderHeader(overrides: Partial<ContractDetail> = {}, props: Partial<React.ComponentProps<typeof ContractHeader>> = {}) {
  return render(
    <I18nProvider>
      <ContractHeader
        detail={detail(overrides)}
        contractId="00000000-0000-0000-0000-000000000030"
        {...props}
      />
    </I18nProvider>
  );
}

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ContractHeader — Create Review Link gating", () => {
  it("offers Create Review Link when the contract is ready_for_client", () => {
    renderHeader({ stage: "ready_for_client", status: "ready" });
    expect(screen.getByText("إرسال للمراجعة")).toBeTruthy();
  });

  it("never offers Create Review Link while the contract is in negotiation (would 409 invalid_stage_transition)", () => {
    renderHeader({ stage: "negotiation", status: "ready" });
    expect(screen.queryByText("إرسال للمراجعة")).toBeNull();
  });

  it("never offers Create Review Link for any other non-ready_for_client stage", () => {
    renderHeader({ stage: "internal_review", status: "ready" });
    expect(screen.queryByText("إرسال للمراجعة")).toBeNull();
  });
});

describe("ContractHeader — Mark Ready for Client Review (draft entry action)", () => {
  it("offers the action for a draft contract with extraction complete", () => {
    renderHeader({ stage: "draft", status: "ready" });
    expect(screen.getByText("تجهيز العقد لمراجعة العميل")).toBeTruthy();
  });

  it("never offers the action while extraction/classification is still processing", () => {
    renderHeader({ stage: "draft", status: "processing" });
    expect(screen.queryByText("تجهيز العقد لمراجعة العميل")).toBeNull();
  });

  it("never offers the action, nor Create Review Link, for any other stage", () => {
    renderHeader({ stage: "ready_for_client", status: "ready" });
    expect(screen.queryByText("تجهيز العقد لمراجعة العميل")).toBeNull();
  });

  it("never offers negotiation/approval/signature actions while in draft", () => {
    renderHeader(
      { stage: "draft", status: "ready" },
      { onStartApproval: vi.fn(), onCreateSignature: vi.fn() }
    );
    expect(screen.queryByText("بدء مسار الموافقات الداخلية")).toBeNull();
    expect(screen.queryByText("إنشاء طلب توقيع")).toBeNull();
  });

  it("calls the endpoint and refreshes contract data on success", async () => {
    markContractReadyForClient.mockResolvedValue({ id: "x", stage: "ready_for_client" });
    const onLifecycleChange = vi.fn().mockResolvedValue(undefined);
    renderHeader({ stage: "draft", status: "ready" }, { onLifecycleChange });

    fireEvent.click(screen.getByText("تجهيز العقد لمراجعة العميل"));

    await waitFor(() =>
      expect(markContractReadyForClient).toHaveBeenCalledWith("00000000-0000-0000-0000-000000000030")
    );
    await waitFor(() => expect(onLifecycleChange).toHaveBeenCalled());
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
  });

  it("surfaces a deterministic backend error instead of failing silently", async () => {
    class FakeApiError extends Error {
      code = "contract_not_ready";
    }
    markContractReadyForClient.mockRejectedValue(new FakeApiError());
    renderHeader({ stage: "draft", status: "ready" });

    fireEvent.click(screen.getByText("تجهيز العقد لمراجعة العميل"));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
  });
});
