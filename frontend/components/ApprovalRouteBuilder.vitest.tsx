/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ApprovalRouteBuilder from "@/components/ApprovalRouteBuilder";
import { I18nProvider } from "@/lib/i18n";
import type { SavedApprovalRoute } from "@/lib/types";

const fetchSavedRoutes = vi.fn();
const fetchSavedRoute = vi.fn();
const configureApprovalRoute = vi.fn();

class FakeApiError extends Error {
  code: string;
  constructor(code: string) {
    super(code);
    this.code = code;
  }
}

vi.mock("@/lib/api", () => ({
  apiErrorCode: (error: unknown, fallback: string) => (error instanceof FakeApiError ? error.code : fallback),
  DEMO_ROLE_STORAGE: "demoRole",
  DEMO_ROLE_EVENT: "demo-role-changed",
  fetchSavedRoutes: (...args: unknown[]) => fetchSavedRoutes(...args),
  fetchSavedRoute: (...args: unknown[]) => fetchSavedRoute(...args),
  configureApprovalRoute: (...args: unknown[]) => configureApprovalRoute(...args),
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();

vi.mock("@/components/feedback/ToastProvider", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError, warning: vi.fn(), info: vi.fn(), toast: vi.fn() }),
}));

const CONTRACT_ID = "00000000-0000-0000-0000-000000000060";

function savedRoute(overrides: Partial<SavedApprovalRoute> = {}): SavedApprovalRoute {
  return {
    id: "route-1",
    name: "Standard Commercial",
    scope: "default",
    active: true,
    created_by: "legal",
    created_at: "2026-08-01T00:00:00+00:00",
    updated_at: "2026-08-01T00:00:00+00:00",
    steps: [
      { id: "s1", step_order: 1, role: "legal", approver_name: null, required: true },
      { id: "s2", step_order: 2, role: "sales", approver_name: null, required: true },
      { id: "s3", step_order: 3, role: "executive", approver_name: null, required: true },
    ],
    step_count: 3,
    ...overrides,
  };
}

function renderBuilder(props: Partial<React.ComponentProps<typeof ApprovalRouteBuilder>> = {}) {
  return render(
    <I18nProvider>
      <ApprovalRouteBuilder contractId={CONTRACT_ID} onConfigured={vi.fn()} {...props} />
    </I18nProvider>
  );
}

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  fetchSavedRoutes.mockResolvedValue({ routes: [], available_roles: ["business_owner", "legal", "finance", "executive", "sales", "manager"] });
});

describe("ApprovalRouteBuilder", () => {
  it("starts with one default approver row, addable/removable, and shows the ordered preview", async () => {
    renderBuilder();
    await screen.findByText("تحديد مسار الموافقات");

    fireEvent.click(screen.getByText("+ إضافة موافِق"));
    fireEvent.click(screen.getByText("+ إضافة موافِق"));

    const removeButtons = screen.getAllByText("إزالة");
    expect(removeButtons).toHaveLength(3);
    fireEvent.click(removeButtons[2]);
    expect(screen.getAllByText("إزالة")).toHaveLength(2);
  });

  it("reorders approvers with move up/down and reflects the new order in the preview", async () => {
    renderBuilder();
    await screen.findByText("تحديد مسار الموافقات");
    fireEvent.click(screen.getByText("+ إضافة موافِق"));

    const selects = screen.getAllByLabelText("الدور") as HTMLSelectElement[];
    fireEvent.change(selects[0], { target: { value: "legal" } });
    fireEvent.change(selects[1], { target: { value: "executive" } });

    const [, moveUpSecond] = screen.getAllByLabelText("تحريك لأعلى");
    fireEvent.click(moveUpSecond);

    const preview = screen.getByText("معاينة المسار").closest("div")!;
    expect(preview.textContent).toMatch(/1\.[\s\S]*تنفيذي[\s\S]*2\.[\s\S]*الشؤون القانونية/);
  });

  it("requires at least one approver — the save action is disabled with zero approvers", async () => {
    renderBuilder();
    await screen.findByText("تحديد مسار الموافقات");
    fireEvent.click(screen.getByText("إزالة"));

    const saveButton = screen.getByText("حفظ مسار الموافقات").closest("button") as HTMLButtonElement;
    expect(saveButton.disabled).toBe(true);
    fireEvent.click(saveButton);

    expect(configureApprovalRoute).not.toHaveBeenCalled();
  });

  it("rejects duplicate role without a distinct approver name", async () => {
    renderBuilder();
    await screen.findByText("تحديد مسار الموافقات");
    fireEvent.click(screen.getByText("+ إضافة موافِق"));
    const selects = screen.getAllByLabelText("الدور") as HTMLSelectElement[];
    fireEvent.change(selects[0], { target: { value: "legal" } });
    fireEvent.change(selects[1], { target: { value: "legal" } });

    fireEvent.click(screen.getByText("حفظ مسار الموافقات"));

    expect(toastError).toHaveBeenCalledWith("لا يمكن تكرار نفس الدور دون اسم موقّع مختلف");
    expect(configureApprovalRoute).not.toHaveBeenCalled();
  });

  it("submits the configured route (roles, order, required, name, save-as-reusable) to the backend", async () => {
    configureApprovalRoute.mockResolvedValue({ id: "cr1", status: "draft", steps: [] });
    const onConfigured = vi.fn();
    renderBuilder({ onConfigured });
    await screen.findByText("تحديد مسار الموافقات");

    fireEvent.change(screen.getByPlaceholderText("مثال: تجاري قياسي"), { target: { value: "Standard Commercial" } });
    fireEvent.click(screen.getByLabelText("الدور"), {}); // sanity: single row exists
    const roleSelect = screen.getAllByLabelText("الدور")[0];
    fireEvent.change(roleSelect, { target: { value: "executive" } });
    fireEvent.click(screen.getByText("حفظ هذا المسار لإعادة الاستخدام"));
    fireEvent.change(screen.getByPlaceholderText("اسم المسار المحفوظ"), { target: { value: "Fast Executive Approval" } });

    fireEvent.click(screen.getByText("حفظ مسار الموافقات"));

    await waitFor(() =>
      expect(configureApprovalRoute).toHaveBeenCalledWith(
        CONTRACT_ID,
        expect.objectContaining({
          name: "Standard Commercial",
          steps: [{ role: "executive", approver_name: null, required: true }],
          save_as_route: true,
          save_as_route_name: "Fast Executive Approval",
        })
      )
    );
    await waitFor(() => expect(onConfigured).toHaveBeenCalled());
  });

  it("loads a saved route into the builder for customization before starting", async () => {
    fetchSavedRoutes.mockResolvedValue({ routes: [savedRoute()], available_roles: [] });
    fetchSavedRoute.mockResolvedValue(savedRoute());
    renderBuilder();

    const select = await screen.findByText("اختر مسارًا محفوظًا");
    fireEvent.change(select.closest("select")!, { target: { value: "route-1" } });

    await waitFor(() => expect(screen.getAllByLabelText("الدور")).toHaveLength(3));
    const preview = screen.getByText("معاينة المسار").closest("div")!;
    expect(preview.textContent).toMatch(/الشؤون القانونية/);
    expect(preview.textContent).toMatch(/المبيعات/);
    expect(preview.textContent).toMatch(/تنفيذي/);
  });

  it("shows the sequential-only disclosure honestly, without implying parallel support", async () => {
    renderBuilder();
    expect(await screen.findByText(/الموافقات المتوازية غير مدعومة بعد/)).toBeTruthy();
  });
});

// Root cause: approval_route_role_required is a pure authorization gate
// (app/services/approval_routes.py::_require_route_admin — the acting
// X-Demo-Role must be "legal" or "executive") on the PUT
// /contracts/{id}/approval-route call itself; it has nothing to do with
// the request body's shape (no role/approver_name/email/required field
// was ever missing or malformed). The frontend previously had no
// awareness of the acting role at all, and rendered the raw backend
// error code verbatim via toast.error(apiErrorCode(...)) with no i18n
// mapping. See docs/approval-route-role-error-audit.md.
describe("ApprovalRouteBuilder — role gate for approval_route_role_required", () => {
  it("prevents submission and explains why when the acting demo role cannot configure routes", async () => {
    localStorage.setItem("demoRole", "finance");
    renderBuilder();

    expect(await screen.findByText("لا تملك صلاحية تحديد مسار الموافقات")).toBeTruthy();
    const saveButton = screen.getByText("حفظ مسار الموافقات").closest("button") as HTMLButtonElement;
    expect(saveButton.disabled).toBe(true);

    fireEvent.click(saveButton);
    expect(configureApprovalRoute).not.toHaveBeenCalled();
  });

  it("allows submission for the legal role", async () => {
    localStorage.setItem("demoRole", "legal");
    configureApprovalRoute.mockResolvedValue({ id: "cr1", status: "draft", steps: [] });
    renderBuilder();

    expect(screen.queryByText("لا تملك صلاحية تحديد مسار الموافقات")).toBeNull();
    fireEvent.click(screen.getByText("حفظ مسار الموافقات"));

    await waitFor(() => expect(configureApprovalRoute).toHaveBeenCalled());
  });

  it("allows submission for the executive role", async () => {
    localStorage.setItem("demoRole", "executive");
    configureApprovalRoute.mockResolvedValue({ id: "cr1", status: "draft", steps: [] });
    renderBuilder();

    expect(screen.queryByText("لا تملك صلاحية تحديد مسار الموافقات")).toBeNull();
    fireEvent.click(screen.getByText("حفظ مسار الموافقات"));

    await waitFor(() => expect(configureApprovalRoute).toHaveBeenCalled());
  });

  it("maps the raw approval_route_role_required backend code to a localized message instead of showing it verbatim", async () => {
    // Simulates the role switching to a non-admin one in another tab
    // right before the request lands — the backend still rejects it even
    // though the client-side gate normally prevents this.
    localStorage.setItem("demoRole", "legal");
    configureApprovalRoute.mockRejectedValue(new FakeApiError("approval_route_role_required"));
    renderBuilder();

    fireEvent.click(screen.getByText("حفظ مسار الموافقات"));

    await waitFor(() => expect(toastError).toHaveBeenCalledWith("لا تملك صلاحية تحديد مسار الموافقات"));
    expect(toastError).not.toHaveBeenCalledWith("approval_route_role_required");
  });

  it("maps other known backend error codes to localized messages too", async () => {
    localStorage.setItem("demoRole", "legal");
    configureApprovalRoute.mockRejectedValue(new FakeApiError("approval_route_locked"));
    renderBuilder();

    fireEvent.click(screen.getByText("حفظ مسار الموافقات"));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith("تم بدء مسار الموافقات بالفعل — يجب إلغاؤه أولًا قبل تعديل الإعداد")
    );
  });

  it("falls back to the generic error message for an unmapped/unexpected backend code", async () => {
    localStorage.setItem("demoRole", "legal");
    configureApprovalRoute.mockRejectedValue(new FakeApiError("not_found"));
    renderBuilder();

    fireEvent.click(screen.getByText("حفظ مسار الموافقات"));

    await waitFor(() => expect(toastError).toHaveBeenCalled());
    expect(toastError).not.toHaveBeenCalledWith("not_found");
  });

  it("updates the gate live when the demo role switcher changes role", async () => {
    localStorage.setItem("demoRole", "finance");
    renderBuilder();
    await screen.findByText("لا تملك صلاحية تحديد مسار الموافقات");

    localStorage.setItem("demoRole", "executive");
    fireEvent(window, new Event("demo-role-changed"));

    await waitFor(() => expect(screen.queryByText("لا تملك صلاحية تحديد مسار الموافقات")).toBeNull());
  });
});
