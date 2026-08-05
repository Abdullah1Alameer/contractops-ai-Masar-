/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ApprovalsPanel from "@/components/ApprovalsPanel";
import { I18nProvider } from "@/lib/i18n";

const fetchApprovals = vi.fn();
const fetchActivity = vi.fn();
const startApproval = vi.fn();
const patchApprovalStep = vi.fn();
const cancelApproval = vi.fn();

vi.mock("@/lib/api", () => ({
  apiErrorCode: (_error: unknown, fallback: string) => fallback,
  DEMO_ROLE_EVENT: "demo-role-changed",
  fetchApprovals: (...args: unknown[]) => fetchApprovals(...args),
  fetchActivity: (...args: unknown[]) => fetchActivity(...args),
  startApproval: (...args: unknown[]) => startApproval(...args),
  patchApprovalStep: (...args: unknown[]) => patchApprovalStep(...args),
  cancelApproval: (...args: unknown[]) => cancelApproval(...args),
}));

vi.mock("@/components/feedback/ToastProvider", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn(), toast: vi.fn() }),
}));

vi.mock("@/components/feedback/ConfirmDialog", () => ({
  useConfirm: () => ({ confirm: ({ onConfirm }: { onConfirm: () => void }) => onConfirm() }),
}));

const CONTRACT_ID = "00000000-0000-0000-0000-000000000050";

function renderPanel(props: Partial<React.ComponentProps<typeof ApprovalsPanel>> = {}) {
  return render(
    <I18nProvider>
      <ApprovalsPanel contractId={CONTRACT_ID} {...props} />
    </I18nProvider>
  );
}

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  fetchActivity.mockResolvedValue({ events: [] });
});

describe("ApprovalsPanel — canonical start gating (no hardcoded stage fallback)", () => {
  it("never offers Start when contractStage is unknown/undefined, even with no unresolved negotiations", async () => {
    fetchApprovals.mockResolvedValue({ workflow: null, unresolved_negotiations: [] });
    renderPanel({ contractStage: undefined });

    await screen.findByText("لا يوجد مسار موافقة بعد");
    expect(screen.queryByText("بدء مسار الموافقات الداخلية")).toBeNull();
  });

  it("offers Start only when contractStage is internal_review", async () => {
    fetchApprovals.mockResolvedValue({ workflow: null, unresolved_negotiations: [] });
    renderPanel({ contractStage: "internal_review" });

    expect(await screen.findByText("بدء مسار الموافقات الداخلية")).toBeTruthy();
  });

  it("while blocked by unresolved negotiations in negotiation stage, offers a way to the Negotiation tab instead of a dead end", async () => {
    fetchApprovals.mockResolvedValue({
      workflow: null,
      unresolved_negotiations: [{ id: "n1" }],
    });
    const onGoToNegotiation = vi.fn();
    renderPanel({ contractStage: "negotiation", onGoToNegotiation });

    fireEvent.click(await screen.findByText("الانتقال إلى تبويب التفاوض"));
    expect(onGoToNegotiation).toHaveBeenCalled();
  });
});
