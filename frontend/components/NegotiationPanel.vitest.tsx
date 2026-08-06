/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import NegotiationPanel from "@/components/NegotiationPanel";
import { I18nProvider } from "@/lib/i18n";
import type { NegotiationCandidate, NegotiationRow } from "@/lib/types";

const fetchNegotiations = vi.fn();
const analyzeNegotiation = vi.fn();
const patchNegotiation = vi.fn();
const sendNegotiationUpdated = vi.fn();
const abandonNegotiation = vi.fn();
const recordNegotiationAgreement = vi.fn();

const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("@/lib/api", () => ({
  apiErrorCode: (_error: unknown, fallback: string) => fallback,
  DEMO_ROLE_STORAGE: "demoRole",
  DEMO_ROLE_EVENT: "demo-role-changed",
  fetchNegotiations: (...args: unknown[]) => fetchNegotiations(...args),
  analyzeNegotiation: (...args: unknown[]) => analyzeNegotiation(...args),
  patchNegotiation: (...args: unknown[]) => patchNegotiation(...args),
  sendNegotiationUpdated: (...args: unknown[]) => sendNegotiationUpdated(...args),
  abandonNegotiation: (...args: unknown[]) => abandonNegotiation(...args),
  recordNegotiationAgreement: (...args: unknown[]) => recordNegotiationAgreement(...args),
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
    confirm: async ({ onConfirm }: { onConfirm: () => void | Promise<void> }) => {
      await onConfirm();
      return true;
    },
  }),
}));

const CONTRACT_ID = "00000000-0000-0000-0000-000000000040";
const REVIEW_ID = "44444444-4444-4444-4444-444444444444";
const NEGOTIATION_ID = "55555555-5555-5555-5555-555555555555";

function negotiation(overrides: Partial<NegotiationRow> = {}): NegotiationRow {
  return {
    id: NEGOTIATION_ID,
    contract_id: CONTRACT_ID,
    review_request_id: REVIEW_ID,
    review_comment_id: null,
    clause_ref: null,
    original_clause: "Original clause text",
    reviewer_comment: "Please shorten the notice period",
    reviewer_decision: "changes_requested",
    ai_summary: "AI summary of the negotiation",
    business_impact: null,
    legal_impact: null,
    risk_level: "low",
    recommendation: "accept",
    reasoning: null,
    counter_clause: "Proposed counter wording",
    counter_clause_ar: null,
    pros: [],
    cons: [],
    status: "sent",
    editing_status: "sent",
    edited_by_lawyer: false,
    sent_review_request_id: "66666666-6666-6666-6666-666666666666",
    workflow_status: "sent_to_client",
    closure_outcome: null,
    lawyer_final_clause: null,
    lawyer_final_clause_ar: null,
    sent_at: "2026-08-06T10:00:00+00:00",
    final_summary: { review_link: "https://demo.local/review/followup-token", sent_at: "2026-08-06T10:00:00+00:00" },
    confidence: 0.8,
    created_at: "2026-08-06T09:00:00+00:00",
    updated_at: "2026-08-06T10:00:00+00:00",
    is_stale: false,
    actionable: true,
    ...overrides,
  };
}

function candidate(overrides: Partial<NegotiationCandidate> = {}): NegotiationCandidate {
  return {
    review_id: REVIEW_ID,
    comment_id: null,
    clause_ref: null,
    reviewer_comment: "Please shorten the notice period",
    review_status: "changes_requested",
    original_clause: "Original clause text",
    negotiation: negotiation(),
    ...overrides,
  };
}

function renderPanel(props: Partial<React.ComponentProps<typeof NegotiationPanel>> = {}) {
  return render(
    <I18nProvider>
      <NegotiationPanel contractId={CONTRACT_ID} {...props} />
    </I18nProvider>
  );
}

function setRole(role: string) {
  localStorage.setItem("demoRole", role);
}

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe("NegotiationPanel — sent_to_client is not a dead end", () => {
  it("offers the client link and Abandon while waiting for the counterparty, instead of no action at all", async () => {
    fetchNegotiations.mockResolvedValue({ candidates: [candidate()] });
    renderPanel();

    expect(await screen.findByText("بانتظار رد العميل")).toBeTruthy();
    expect(screen.getByText("نسخ رابط العميل")).toBeTruthy();
    expect(screen.getByText("إلغاء التفاوض")).toBeTruthy();
    // The approve/send buttons (for items not yet sent) must not also show.
    expect(screen.queryByText("إرسال النسخة المحدّثة للعميل")).toBeNull();
  });

  it("copies the client's review link", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    fetchNegotiations.mockResolvedValue({ candidates: [candidate()] });
    renderPanel();

    fireEvent.click(await screen.findByText("نسخ رابط العميل"));

    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith("https://demo.local/review/followup-token")
    );
  });

  it("still allows abandoning a negotiation stuck waiting on the client", async () => {
    fetchNegotiations.mockResolvedValue({ candidates: [candidate()] });
    abandonNegotiation.mockResolvedValue({});
    vi.spyOn(window, "prompt").mockReturnValue("No longer proceeding");
    renderPanel();

    fireEvent.click(await screen.findByText("إلغاء التفاوض"));

    await waitFor(() =>
      expect(abandonNegotiation).toHaveBeenCalledWith(NEGOTIATION_ID, "No longer proceeding")
    );
  });

  it("offers Analyze as the next action for a fresh, unanalyzed negotiation", async () => {
    fetchNegotiations.mockResolvedValue({
      candidates: [candidate({ negotiation: negotiation({ ai_summary: null, workflow_status: "pending_analysis" }) })],
    });
    renderPanel();

    expect(await screen.findByText("تحليل بالذكاء الاصطناعي")).toBeTruthy();
  });
});

describe("NegotiationPanel — Record Agreement Reached (authorized internal override)", () => {
  it("never offers the override when contractStage is not passed/negotiation", async () => {
    fetchNegotiations.mockResolvedValue({ candidates: [candidate()] });
    setRole("legal");
    renderPanel({ contractStage: "internal_review" });

    await screen.findByText("بانتظار رد العميل");
    expect(screen.queryByText("تسجيل التوصل إلى اتفاق")).toBeNull();
  });

  it("never offers the override for a role other than legal/executive", async () => {
    fetchNegotiations.mockResolvedValue({ candidates: [candidate()] });
    setRole("business_owner");
    renderPanel({ contractStage: "negotiation" });

    await screen.findByText("بانتظار رد العميل");
    expect(screen.queryByText("تسجيل التوصل إلى اتفاق")).toBeNull();
  });

  it("never offers the override for a stale or already-resolved negotiation", async () => {
    fetchNegotiations.mockResolvedValue({
      candidates: [candidate({ negotiation: negotiation({ is_stale: true }) })],
    });
    setRole("legal");
    renderPanel({ contractStage: "negotiation" });

    await screen.findByText("بانتظار رد العميل");
    expect(screen.queryByText("تسجيل التوصل إلى اتفاق")).toBeNull();
  });

  it("offers the override to legal/executive on an active negotiation in negotiation stage", async () => {
    fetchNegotiations.mockResolvedValue({ candidates: [candidate()] });
    setRole("executive");
    renderPanel({ contractStage: "negotiation" });

    expect(await screen.findByText("تسجيل التوصل إلى اتفاق")).toBeTruthy();
  });

  it("requires a non-empty reason before calling the endpoint", async () => {
    fetchNegotiations.mockResolvedValue({ candidates: [candidate()] });
    setRole("legal");
    vi.spyOn(window, "prompt").mockReturnValue("   ");
    renderPanel({ contractStage: "negotiation" });

    fireEvent.click(await screen.findByText("تسجيل التوصل إلى اتفاق"));

    expect(recordNegotiationAgreement).not.toHaveBeenCalled();
  });

  it("calls the record-agreement endpoint with the given reason, refreshes both negotiation and contract data, and offers a CTA to Internal Approval once the contract resolves", async () => {
    fetchNegotiations.mockResolvedValue({ candidates: [candidate()] });
    recordNegotiationAgreement.mockResolvedValue({ contract_stage: "internal_review" });
    vi.spyOn(window, "prompt").mockReturnValue("Client confirmed by phone on 2026-08-06");
    const onLifecycleChanged = vi.fn().mockResolvedValue(undefined);
    const onGoToApproval = vi.fn();
    setRole("legal");
    renderPanel({ contractStage: "negotiation", onLifecycleChanged, onGoToApproval });

    fireEvent.click(await screen.findByText("تسجيل التوصل إلى اتفاق"));

    await waitFor(() =>
      expect(recordNegotiationAgreement).toHaveBeenCalledWith(
        NEGOTIATION_ID,
        "Client confirmed by phone on 2026-08-06"
      )
    );
    await waitFor(() => expect(fetchNegotiations).toHaveBeenCalledTimes(2)); // initial load + onUpdated refresh
    await waitFor(() => expect(onLifecycleChanged).toHaveBeenCalled());
    expect(await screen.findByText("تم حسم جميع بنود التفاوض — انتقل العقد إلى مرحلة الموافقة الداخلية.")).toBeTruthy();

    fireEvent.click(screen.getByText("الانتقال إلى تبويب الموافقة الداخلية"));
    expect(onGoToApproval).toHaveBeenCalled();
  });

  it("does not show the Internal Approval CTA when other negotiation items remain unresolved", async () => {
    fetchNegotiations.mockResolvedValue({ candidates: [candidate()] });
    recordNegotiationAgreement.mockResolvedValue({ contract_stage: "negotiation" });
    vi.spyOn(window, "prompt").mockReturnValue("Client confirmed by phone");
    setRole("legal");
    renderPanel({ contractStage: "negotiation" });

    fireEvent.click(await screen.findByText("تسجيل التوصل إلى اتفاق"));

    await waitFor(() => expect(recordNegotiationAgreement).toHaveBeenCalled());
    expect(screen.queryByText("الانتقال إلى تبويب الموافقة الداخلية")).toBeNull();
  });

  it("surfaces a deterministic backend error instead of a silent failure", async () => {
    class FakeApiError extends Error {
      code = "negotiation_override_role_required";
    }
    fetchNegotiations.mockResolvedValue({ candidates: [candidate()] });
    recordNegotiationAgreement.mockRejectedValue(new FakeApiError());
    vi.spyOn(window, "prompt").mockReturnValue("Client confirmed by phone");
    setRole("legal");
    renderPanel({ contractStage: "negotiation" });

    fireEvent.click(await screen.findByText("تسجيل التوصل إلى اتفاق"));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
  });
});
