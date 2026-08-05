/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ContractHeader from "@/components/contract/ContractHeader";
import { I18nProvider } from "@/lib/i18n";
import type { ContractDetail } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  sendContractForReview: vi.fn(),
}));

vi.mock("@/components/feedback/ToastProvider", () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
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

function renderHeader(overrides: Partial<ContractDetail> = {}) {
  return render(
    <I18nProvider>
      <ContractHeader detail={detail(overrides)} contractId="00000000-0000-0000-0000-000000000030" />
    </I18nProvider>
  );
}

afterEach(cleanup);

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
