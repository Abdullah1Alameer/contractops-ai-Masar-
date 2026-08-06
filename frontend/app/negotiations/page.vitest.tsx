/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import NegotiationsPage from "@/app/negotiations/page";
import { invalidateByPrefix } from "@/lib/cache";
import { I18nProvider } from "@/lib/i18n";
import type { NegotiationBoardResponse } from "@/lib/types";

const fetchNegotiationBoard = vi.fn();

vi.mock("@/lib/api", () => ({
  fetchNegotiationBoard: (...args: unknown[]) => fetchNegotiationBoard(...args),
}));

function board(overrides: Partial<NegotiationBoardResponse> = {}): NegotiationBoardResponse {
  return {
    items: [
      {
        negotiation_id: "n1",
        contract_id: "c1",
        contract_title: "Facilities Management Agreement",
        counterparty: "Acme Services Co.",
        clause_ref: "4.2",
        issue: "Client requested a reduced service fee",
        workflow_status: "sent_to_client",
        editing_status: "sent",
        contract_stage: "negotiation",
        risk_level: "high",
        recommendation: "negotiate",
        assigned_lawyer: "Sara Al-Fahad",
        waiting_party: "client",
        message_count: 3,
        sent_at: "2026-07-28T10:00:00+00:00",
        updated_at: "2026-08-01T10:00:00+00:00",
        days_waiting: 8,
        sla_status: "overdue",
        critical_deadlines: 1,
        missed_deadlines: 0,
        is_stale: false,
      },
      {
        negotiation_id: "n2",
        contract_id: "c2",
        contract_title: "Maintenance Contract",
        counterparty: "Beta Holdings",
        clause_ref: null,
        issue: "Internal review pending lawyer response",
        workflow_status: "ready",
        editing_status: "draft",
        contract_stage: "negotiation",
        risk_level: "low",
        recommendation: "accept",
        assigned_lawyer: null,
        waiting_party: "lawyer",
        message_count: 1,
        sent_at: null,
        updated_at: "2026-08-02T10:00:00+00:00",
        days_waiting: null,
        sla_status: null,
        critical_deadlines: 0,
        missed_deadlines: 0,
        is_stale: false,
      },
    ],
    summary: {
      total_active: 2,
      pending: 0,
      waiting_client: 1,
      waiting_lawyer: 1,
      high_risk: 1,
      overdue: 1,
    },
    ...overrides,
  };
}

function renderPage() {
  return render(
    <I18nProvider>
      <NegotiationsPage />
    </I18nProvider>
  );
}

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  invalidateByPrefix("negotiations:board");
});

describe("Unified Negotiations page (Bug 3)", () => {
  it("lists every active negotiation contract with its real, persisted fields", async () => {
    fetchNegotiationBoard.mockResolvedValue(board());
    renderPage();

    expect(await screen.findByText("Facilities Management Agreement")).toBeTruthy();
    expect(screen.getByText("Maintenance Contract")).toBeTruthy();
    expect(screen.getByText("Acme Services Co.")).toBeTruthy();
  });

  it("filters to waiting-for-client contracts only", async () => {
    fetchNegotiationBoard.mockResolvedValue(board());
    renderPage();
    await screen.findByText("Facilities Management Agreement");

    fireEvent.click(screen.getByRole("button", { name: "بانتظار العميل" }));

    expect(screen.getByText("Facilities Management Agreement")).toBeTruthy();
    expect(screen.queryByText("Maintenance Contract")).toBeNull();
  });

  it("filters to waiting-for-lawyer contracts only", async () => {
    fetchNegotiationBoard.mockResolvedValue(board());
    renderPage();
    await screen.findByText("Facilities Management Agreement");

    fireEvent.click(screen.getByRole("button", { name: "بانتظار القانوني" }));

    expect(screen.getByText("Maintenance Contract")).toBeTruthy();
    expect(screen.queryByText("Facilities Management Agreement")).toBeNull();
  });

  it("filters to high-risk contracts only", async () => {
    fetchNegotiationBoard.mockResolvedValue(board());
    renderPage();
    await screen.findByText("Facilities Management Agreement");

    fireEvent.click(screen.getByRole("button", { name: "مخاطر مرتفعة" }));

    expect(screen.getByText("Facilities Management Agreement")).toBeTruthy();
    expect(screen.queryByText("Maintenance Contract")).toBeNull();
  });

  it("filters to overdue contracts only", async () => {
    fetchNegotiationBoard.mockResolvedValue(board());
    renderPage();
    await screen.findByText("Facilities Management Agreement");

    fireEvent.click(screen.getByText("متأخر"));

    expect(screen.getByText("Facilities Management Agreement")).toBeTruthy();
    expect(screen.queryByText("Maintenance Contract")).toBeNull();
  });

  it("searches by contract name and counterparty", async () => {
    fetchNegotiationBoard.mockResolvedValue(board());
    renderPage();
    await screen.findByText("Facilities Management Agreement");

    fireEvent.change(screen.getByPlaceholderText("البحث باسم العقد أو الطرف الآخر"), {
      target: { value: "beta" },
    });

    expect(screen.getByText("Maintenance Contract")).toBeTruthy();
    expect(screen.queryByText("Facilities Management Agreement")).toBeNull();
  });

  it("shows the real summary metric counts, not invented numbers", async () => {
    fetchNegotiationBoard.mockResolvedValue(board());
    renderPage();

    await waitFor(() => expect(screen.getAllByText("2").length).toBeGreaterThan(0)); // total_active
  });

  it("shows the empty state only when there are genuinely zero active negotiations", async () => {
    fetchNegotiationBoard.mockResolvedValue(
      board({ items: [], summary: { total_active: 0, pending: 0, waiting_client: 0, waiting_lawyer: 0, high_risk: 0, overdue: 0 } })
    );
    renderPage();

    expect(await screen.findByText("لا توجد مفاوضات نشطة حالياً")).toBeTruthy();
  });

  it("flags a stale negotiation (referencing a superseded version) instead of hiding the mismatch", async () => {
    fetchNegotiationBoard.mockResolvedValue(
      board({ items: [{ ...board().items[0], is_stale: true }] })
    );
    renderPage();

    await screen.findByText("Facilities Management Agreement");
    expect(screen.getByText("مسار عمل مبني على إصدار سابق")).toBeTruthy();
  });
});
