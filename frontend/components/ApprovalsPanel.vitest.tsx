/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ApprovalsPanel from "@/components/ApprovalsPanel";
import { I18nProvider } from "@/lib/i18n";

const fetchApprovals = vi.fn();
const fetchActivity = vi.fn();
const fetchContractApprovalRoute = vi.fn();
const startApproval = vi.fn();
const patchApprovalStep = vi.fn();
const cancelApproval = vi.fn();

vi.mock("@/lib/api", () => ({
  apiErrorCode: (_error: unknown, fallback: string) => fallback,
  DEMO_ROLE_EVENT: "demo-role-changed",
  fetchApprovals: (...args: unknown[]) => fetchApprovals(...args),
  fetchActivity: (...args: unknown[]) => fetchActivity(...args),
  fetchContractApprovalRoute: (...args: unknown[]) => fetchContractApprovalRoute(...args),
  startApproval: (...args: unknown[]) => startApproval(...args),
  patchApprovalStep: (...args: unknown[]) => patchApprovalStep(...args),
  cancelApproval: (...args: unknown[]) => cancelApproval(...args),
}));

// The route builder has its own dedicated test file — here it's a stub so
// these tests stay focused on ApprovalsPanel's own gating logic.
vi.mock("@/components/ApprovalRouteBuilder", () => ({
  default: () => <div data-testid="route-builder">route builder</div>,
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
  fetchContractApprovalRoute.mockResolvedValue({ route: null });
});

describe("ApprovalsPanel — canonical start gating (no hardcoded stage fallback)", () => {
  it("never offers the route builder when contractStage is unknown/undefined, even with no unresolved negotiations", async () => {
    fetchApprovals.mockResolvedValue({ workflow: null, unresolved_negotiations: [] });
    renderPanel({ contractStage: undefined });

    await screen.findByText("لا يوجد مسار موافقة بعد");
    expect(screen.queryByTestId("route-builder")).toBeNull();
  });

  it("offers the route configuration builder only when contractStage is internal_review — never a generic hardcoded Start button", async () => {
    fetchApprovals.mockResolvedValue({ workflow: null, unresolved_negotiations: [] });
    renderPanel({ contractStage: "internal_review" });

    expect(await screen.findByTestId("route-builder")).toBeTruthy();
    expect(screen.queryByText("بدء مسار الموافقات الداخلية")).toBeNull();
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

function step(order: number, role: string, status: string) {
  return {
    id: `step-${order}`,
    step_order: order,
    role,
    approver_name: null,
    status,
    required: true,
    comment: null,
    acted_at: null,
  };
}

describe("ApprovalsPanel — step count is always the real configured route, never assumed to be four", () => {
  it("renders exactly one step card for a one-step Executive-only route", async () => {
    fetchApprovals.mockResolvedValue({
      workflow: {
        id: "wf-1", contract_id: CONTRACT_ID, status: "in_progress", current_step_order: 1,
        started_by: "legal", started_at: "2026-08-01T00:00:00+00:00", completed_at: null,
        steps: [step(1, "executive", "pending")],
        current_step: step(1, "executive", "pending"),
        allowed_actions: ["approved", "rejected", "changes_requested"],
        approved_count: 0, remaining_count: 1, completed_step_count: 0, total_step_count: 1,
        current_required_role: "executive", contract_stage: "internal_review", actionable: true,
        stale: false, is_stale: false, override_used: false, version_id: "v1",
        route_name: "Fast Executive Approval", contract_route_id: "cr1", workflow_type: "sequential",
      },
      unresolved_negotiations: [],
    });
    renderPanel({ contractStage: "internal_review" });

    await screen.findByText("Fast Executive Approval");
    expect(screen.getAllByText("الإدارة التنفيذية").length).toBeGreaterThan(0);
    // Only one step card total — must not pad out to four.
    expect(screen.getByText("1")).toBeTruthy();
    expect(screen.queryByText("2")).toBeNull();
  });

  it("renders exactly six step cards for a six-step route", async () => {
    const roles = ["business_owner", "legal", "finance", "sales", "manager", "executive"];
    fetchApprovals.mockResolvedValue({
      workflow: {
        id: "wf-2", contract_id: CONTRACT_ID, status: "in_progress", current_step_order: 1,
        started_by: "legal", started_at: "2026-08-01T00:00:00+00:00", completed_at: null,
        steps: roles.map((r, i) => step(i + 1, r, i === 0 ? "pending" : "locked")),
        current_step: step(1, roles[0], "pending"),
        allowed_actions: ["approved", "rejected", "changes_requested"],
        approved_count: 0, remaining_count: 6, completed_step_count: 0, total_step_count: 6,
        current_required_role: roles[0], contract_stage: "internal_review", actionable: true,
        stale: false, is_stale: false, override_used: false, version_id: "v1",
        route_name: "High-Value Contract Route", contract_route_id: "cr2", workflow_type: "sequential",
      },
      unresolved_negotiations: [],
    });
    renderPanel({ contractStage: "internal_review" });

    await screen.findByText("High-Value Contract Route");
    for (let i = 1; i <= 6; i++) {
      expect(screen.getByText(String(i))).toBeTruthy();
    }
    expect(screen.queryByText("7")).toBeNull();
  });
});
