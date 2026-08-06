/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ReviewPortalPage from "@/app/review/[token]/page";
import { I18nProvider } from "@/lib/i18n";
import type { ReviewPortalPayload } from "@/lib/types";

class FakeApiError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

const fetchReviewPortal = vi.fn();
const reviewApprove = vi.fn();
const reviewReject = vi.fn();
const reviewRequestChanges = vi.fn();
const reviewAddComment = vi.fn();
const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ token: "demo-token" }),
}));

vi.mock("@/lib/api", () => ({
  apiErrorCode: (error: unknown, fallback: string) =>
    error instanceof FakeApiError ? error.code : fallback,
  fetchReviewPortal: (...args: unknown[]) => fetchReviewPortal(...args),
  reviewApprove: (...args: unknown[]) => reviewApprove(...args),
  reviewReject: (...args: unknown[]) => reviewReject(...args),
  reviewRequestChanges: (...args: unknown[]) => reviewRequestChanges(...args),
  reviewAddComment: (...args: unknown[]) => reviewAddComment(...args),
}));

vi.mock("@/components/feedback/ToastProvider", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError, warning: vi.fn(), info: vi.fn(), toast: vi.fn() }),
}));

vi.mock("@/components/DualDate", () => ({
  default: ({ date }: { date: string | null }) => <span>{date}</span>,
}));

vi.mock("@/components/feedback/ConfirmDialog", () => ({
  useConfirm: () => ({
    confirm: async ({ onConfirm }: { onConfirm: () => void | Promise<void> }) => {
      await onConfirm();
      return true;
    },
  }),
}));

function basePayload(overrides: Partial<ReviewPortalPayload> = {}): ReviewPortalPayload {
  return {
    contract: {
      id: "c1",
      title: "Synthetic Portal Contract",
      party_a: "Acme",
      party_b: "Beta",
      value_sar: 50000,
      start_date: null,
      end_date: null,
      governing_law: "KSA",
      status: "ready",
      contract_category: "MSA",
    },
    ai_summary: "Contract summary text",
    notices: [],
    obligations: [],
    timeline: { deadlines: [], summary: { total: 0, critical: 0, within_14_days: 0, missed_or_time_barred: 0, needs_review: 0 } },
    payments: { milestones: [], summary: { total: 0, claimable_sar: 0, blocked_sar: 0, overdue_sar: 0, paid_sar: 0, needs_review_count: 0 } },
    comparison: null,
    comparison_unavailable_reason: "not_linked",
    risks: { score: 0, level: "low", calculation_version: "risk-v2", items: [], count: 0 },
    recipient_name: "Client Reviewer",
    status: "opened",
    expires_at: "2026-12-01T00:00:00+00:00",
    opened_at: "2026-08-06T00:00:00+00:00",
    responded_at: null,
    comments: [],
    decision: null,
    overall_comment: null,
    read_only: false,
    contract_stage: "client_review",
    actionable: true,
    is_stale: false,
    terminal_decision: null,
    next_allowed_actions: ["comment", "approve", "reject", "request_changes"],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <I18nProvider>
      <ReviewPortalPage />
    </I18nProvider>
  );
}

async function clickTab(label: string) {
  fireEvent.click(await screen.findByText(label));
}

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ReviewPortalPage — loading and error states", () => {
  it("shows a loading state before data arrives", () => {
    fetchReviewPortal.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByText("جارٍ التحميل…")).toBeTruthy();
  });

  it("shows a distinct, translated failed-to-load state (not a raw error code) with retry", async () => {
    fetchReviewPortal.mockRejectedValue(new FakeApiError(404, "review_not_found"));
    renderPage();

    expect(await screen.findByText("تعذّر تحميل بيانات المراجعة")).toBeTruthy();
    expect(screen.getByText("review_not_found")).toBeTruthy();
    expect(screen.getByText("إعادة المحاولة")).toBeTruthy();
  });
});

describe("ReviewPortalPage — Risks tab", () => {
  it("shows the real risk score/level and explains it with backing findings, never 'no data' when a score exists", async () => {
    fetchReviewPortal.mockResolvedValue(
      basePayload({
        risks: {
          score: 2,
          level: "low",
          calculation_version: "risk-v2",
          items: [
            {
              type: "finding",
              category: "temporal",
              label: "Temporal",
              detail: "Date reference could not be fully resolved.",
              detail_ar: "تعذر حل مرجع التاريخ.",
              severity: "medium",
              link_tab: "deadlines",
              contributes_to_score: true,
            },
          ],
          count: 1,
        },
      })
    );
    renderPage();
    await clickTab("المخاطر");

    // Default UI language is Arabic, so the Arabic explanation renders.
    expect(await screen.findByText(/تعذر حل مرجع التاريخ/)).toBeTruthy();
    expect(screen.queryByText("لم يتم رصد أي عوامل مخاطرة أو غرامات في هذا العقد.")).toBeNull();
    // The explanation must be direction-isolated for mixed AR/EN content.
    const detail = screen.getByText(/تعذر حل مرجع التاريخ/);
    expect(detail.getAttribute("dir")).toBe("auto");
  });

  it("shows a specific empty state, distinct from the generic empty copy, when there truly are no risk items", async () => {
    fetchReviewPortal.mockResolvedValue(basePayload());
    renderPage();
    await clickTab("المخاطر");

    expect(await screen.findByText("لم يتم رصد أي عوامل مخاطرة أو غرامات في هذا العقد.")).toBeTruthy();
  });

  it("labels supplementary (non-scoring) items separately from score-backing findings", async () => {
    fetchReviewPortal.mockResolvedValue(
      basePayload({
        risks: {
          score: 2,
          level: "low",
          calculation_version: "risk-v2",
          items: [
            {
              type: "penalty",
              category: "financial",
              label: "late delivery penalty",
              detail: "0.5% per week",
              detail_ar: null,
              severity: "medium",
              link_tab: "risks",
              contributes_to_score: false,
              rate: "0.5% per week",
              cap: "10% of contract value",
              quote: "A late delivery penalty applies",
              clause_ref: "5",
              page: 7,
            },
          ],
          count: 1,
        },
      })
    );
    renderPage();
    await clickTab("المخاطر");

    expect(await screen.findByText("معلومات إضافية")).toBeTruthy();
    expect(screen.getByText(/10% of contract value/)).toBeTruthy();
  });
});

describe("ReviewPortalPage — Obligations tab", () => {
  it("renders complete available fields, not just description/party/due date", async () => {
    fetchReviewPortal.mockResolvedValue(
      basePayload({
        obligations: [
          {
            id: "o1",
            title: "Pay monthly wage",
            description: "Provider shall invoice Client monthly.",
            responsible_party: "Provider",
            beneficiary: "Client",
            trigger_type: "recurring",
            trigger_event: "monthly_payroll",
            completion_criteria: null,
            contract_required_evidence: [],
            suggested_evidence: ["payroll_record"],
            due_date: null,
            penalty_text: "0.5% per week",
            status: "pending",
            clause_ref: "2",
            page: 7,
          },
        ],
      })
    );
    renderPage();
    await clickTab("الالتزامات");

    expect(await screen.findByText("Pay monthly wage")).toBeTruthy();
    expect(screen.getByText(/monthly_payroll/)).toBeTruthy();
    expect(screen.getByText(/0.5% per week/)).toBeTruthy();
  });

  it("shows a specific empty state when no obligations were extracted", async () => {
    fetchReviewPortal.mockResolvedValue(basePayload());
    renderPage();
    await clickTab("الالتزامات");

    expect(await screen.findByText("لم يتم استخراج أي التزامات من هذا العقد.")).toBeTruthy();
  });
});

describe("ReviewPortalPage — Timeline tab", () => {
  it("shows status, notice days, and the calculation explanation when the date is genuinely unresolved", async () => {
    fetchReviewPortal.mockResolvedValue(
      basePayload({
        timeline: {
          deadlines: [
            {
              id: "d1",
              contract_id: "c1",
              type: "notice_deadline",
              title: "Termination notice",
              description: null,
              event_date: null,
              deadline_date: null,
              source_trigger_date: null,
              notice_period_days: 60,
              days_remaining: null,
              severity: "warning",
              status: "needs_review",
              time_barred: false,
              needs_review: true,
              review_reason: "missing_base_date",
              responsible_party: "either_party",
              clause_ref: "3",
              quote: null,
              page: 2,
              confidence: 1,
              verified: true,
              char_start: null,
              char_end: null,
              calculation_explanation: "Date reference could not be fully resolved.",
              calculation_explanation_ar: "تعذر حل مرجع التاريخ.",
            },
          ],
          summary: { total: 1, critical: 0, within_14_days: 0, missed_or_time_barred: 0, needs_review: 1 },
        },
      })
    );
    renderPage();
    await clickTab("الجدول الزمني");

    expect(await screen.findByText("Termination notice")).toBeTruthy();
    expect(screen.getByText("يحتاج مراجعة")).toBeTruthy(); // deadline.status.needs_review
    expect(screen.getByText(/60/)).toBeTruthy();
    // Default UI language is Arabic, so the Arabic explanation renders (with
    // an English fallback only when the Arabic field is absent).
    expect(screen.getByText(/تعذر حل مرجع التاريخ/)).toBeTruthy();
    expect(screen.getByText("لا يوجد تاريخ محدد بعد")).toBeTruthy();
  });

  it("shows a specific empty state when no deadlines were extracted", async () => {
    fetchReviewPortal.mockResolvedValue(basePayload());
    renderPage();
    await clickTab("الجدول الزمني");

    expect(await screen.findByText("لم يتم استخراج أي مواعيد أو إشعارات من هذا العقد.")).toBeTruthy();
  });
});

describe("ReviewPortalPage — Payments tab", () => {
  it("renders status and due date alongside the amount", async () => {
    fetchReviewPortal.mockResolvedValue(
      basePayload({
        payments: {
          milestones: [
            {
              id: "m1",
              contract_id: "c1",
              sequence: 1,
              type: "milestone",
              label: "First milestone",
              description: null,
              amount_sar: 50000,
              amount_percentage: null,
              due_date: "2026-09-01",
              status: "due",
              readiness_percentage: 100,
              claimable: true,
              paid: false,
              preconditions: [],
              missing_preconditions: [],
              clause_ref: "3",
              quote: null,
              page: 2,
              confidence: 1,
              verified: true,
              char_start: null,
              char_end: null,
              created_at: null,
              updated_at: null,
            },
          ],
          summary: { total: 1, claimable_sar: 50000, blocked_sar: 0, overdue_sar: 0, paid_sar: 0, needs_review_count: 0 },
        },
      })
    );
    renderPage();
    await clickTab("الدفعات");

    expect(await screen.findByText("First milestone")).toBeTruthy();
    expect(screen.getByText("مستحق")).toBeTruthy(); // payment.status.due
  });

  it("shows a specific empty state when no payment milestones were extracted", async () => {
    fetchReviewPortal.mockResolvedValue(basePayload());
    renderPage();
    await clickTab("الدفعات");

    expect(await screen.findByText("لم يتم استخراج أي دفعات مالية من هذا العقد.")).toBeTruthy();
  });
});

describe("ReviewPortalPage — Comparison tab", () => {
  it("explains that comparison requires a linked contract, not that another version is needed", async () => {
    fetchReviewPortal.mockResolvedValue(basePayload({ comparison: null, comparison_unavailable_reason: "not_linked" }));
    renderPage();
    await clickTab("المقارنة");

    expect(
      screen.getByText("لا تتوفر مقارنة — تتطلب هذه الميزة ربط العقد بعقد رئيسي أو عقد من الباطن. هذا غير متعلق بعدد إصدارات العقد.")
    ).toBeTruthy();
  });

  it("distinguishes 'linked but not yet compared' from 'not linked at all'", async () => {
    fetchReviewPortal.mockResolvedValue(basePayload({ comparison: null, comparison_unavailable_reason: "not_yet_compared" }));
    renderPage();
    await clickTab("المقارنة");

    expect(await screen.findByText("هذا العقد مرتبط بعقد آخر، لكن لم يتم إنشاء تحليل مقارنة بعد.")).toBeTruthy();
  });
});

describe("ReviewPortalPage — stale-version honesty", () => {
  it("tells the reviewer the dossier reflects the latest version when the review is stale", async () => {
    fetchReviewPortal.mockResolvedValue(basePayload({ is_stale: true, read_only: true, actionable: false }));
    renderPage();

    expect(
      await screen.findByText(
        "تشير هذه البيانات (الالتزامات، الجدول الزمني، الدفعات، المخاطر) إلى أحدث إصدار من العقد — وقد لا تطابق تمامًا ما كان عليه العقد عند إرسال هذه المراجعة."
      )
    ).toBeTruthy();
  });

  it("shows no stale notice for a fresh, non-stale review", async () => {
    fetchReviewPortal.mockResolvedValue(basePayload({ is_stale: false }));
    renderPage();

    await screen.findByText("Synthetic Portal Contract");
    expect(
      screen.queryByText(
        "تشير هذه البيانات (الالتزامات، الجدول الزمني، الدفعات، المخاطر) إلى أحدث إصدار من العقد — وقد لا تطابق تمامًا ما كان عليه العقد عند إرسال هذه المراجعة."
      )
    ).toBeNull();
  });
});
