/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const fetchTemplateDetail = vi.fn();
const previewTemplateContract = vi.fn();
const createContractFromTemplate = vi.fn();
const api = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "msa" }),
  useRouter: () => ({ push }),
}));

vi.mock("@/lib/api", () => ({
  apiErrorCode: (_error: unknown, fallback: string) => fallback,
  api: (...args: unknown[]) => api(...args),
  fetchTemplateDetail: (...args: unknown[]) => fetchTemplateDetail(...args),
  previewTemplateContract: (...args: unknown[]) => previewTemplateContract(...args),
  createContractFromTemplate: (...args: unknown[]) => createContractFromTemplate(...args),
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();
const toastWarning = vi.fn();

vi.mock("@/components/feedback/ToastProvider", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError, warning: toastWarning, info: vi.fn(), toast: vi.fn() }),
}));

import TemplateDetailPage from "@/app/templates/[id]/page";
import { I18nProvider } from "@/lib/i18n";
import type { TemplateDetail } from "@/lib/types";

function detail(): TemplateDetail {
  return {
    id: "tpl-1",
    key: "msa",
    title_en: "Master Service Agreement",
    title_ar: "اتفاقية خدمات رئيسية",
    category: "Commercial",
    language: "both",
    industry: "Technology",
    usage_count: 42,
    updated_at: "2026-07-01T00:00:00+00:00",
    description_en: "A master services agreement.",
    description_ar: "اتفاقية خدمات رئيسية.",
    variables: [
      { key: "party_a", label_en: "Service Provider", label_ar: "مقدم الخدمة", type: "text", required: true },
      { key: "party_b", label_en: "Client", label_ar: "العميل", type: "text", required: true },
    ],
    clauses: [{ title_en: "Scope of Services", title_ar: "نطاق الخدمات" }],
  };
}

function renderPage() {
  return render(
    <I18nProvider>
      <TemplateDetailPage />
    </I18nProvider>
  );
}

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Template detail / creation flow (Bug 2)", () => {
  it("shows real template details fetched from the backend, not a generic redirect", async () => {
    fetchTemplateDetail.mockResolvedValue(detail());
    renderPage();

    expect(await screen.findByText("اتفاقية خدمات رئيسية")).toBeTruthy();
    expect(screen.getByText("اتفاقية خدمات رئيسية.")).toBeTruthy();
    expect(screen.getByText("نطاق الخدمات")).toBeTruthy();
  });

  it("shows a deterministic not-found state for an unknown template", async () => {
    fetchTemplateDetail.mockRejectedValue(new Error("template_not_found"));
    renderPage();

    expect(await screen.findByText("لم يتم العثور على هذا القالب.")).toBeTruthy();
  });

  it("walks detail -> form -> preview -> create, sending the correct template ID throughout", async () => {
    fetchTemplateDetail.mockResolvedValue(detail());
    previewTemplateContract.mockResolvedValue({
      template: { id: "tpl-1", key: "msa", title_en: "MSA", title_ar: "msa", category: null, language: "both", industry: null, usage_count: 42, updated_at: null },
      missing_variables: [],
      sections_en: [{ title: "Scope of Services", body: "Acme LLC shall provide services to Beta Corp." }],
      sections_ar: [{ title: "نطاق الخدمات", body: "يقدم Acme LLC الخدمات إلى Beta Corp." }],
    });
    createContractFromTemplate.mockResolvedValue({ id: "contract-1", stage: "draft", status: "processing", template_id: "tpl-1", version_id: "v1", version_number: 1 });
    api.mockResolvedValue({ status: "ready", supported: true });
    renderPage();

    fireEvent.click(await screen.findByText("إنشاء عقد من هذا القالب"));

    const partyA = await screen.findByText("مقدم الخدمة");
    fireEvent.change(partyA.closest("label")!.querySelector("input")!, { target: { value: "Acme LLC" } });
    const partyB = screen.getByText("العميل");
    fireEvent.change(partyB.closest("label")!.querySelector("input")!, { target: { value: "Beta Corp" } });

    fireEvent.click(screen.getByText("معاينة المستند"));

    await waitFor(() => expect(previewTemplateContract).toHaveBeenCalledWith("tpl-1", expect.objectContaining({ party_a: "Acme LLC", party_b: "Beta Corp" })));
    expect(await screen.findByText("يقدم Acme LLC الخدمات إلى Beta Corp.")).toBeTruthy();

    fireEvent.click(screen.getByText("تأكيد إنشاء العقد"));

    await waitFor(() => expect(createContractFromTemplate).toHaveBeenCalledWith("tpl-1", expect.objectContaining({ party_a: "Acme LLC", party_b: "Beta Corp" })));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/api/contracts/contract-1/extract", { method: "POST" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/contracts/contract-1"));
  });

  it("blocks preview when required variables are missing, without creating anything", async () => {
    fetchTemplateDetail.mockResolvedValue(detail());
    previewTemplateContract.mockResolvedValue({
      template: { id: "tpl-1", key: "msa", title_en: "MSA", title_ar: "msa", category: null, language: "both", industry: null, usage_count: 42, updated_at: null },
      missing_variables: ["party_b"],
      sections_en: [],
      sections_ar: [],
    });
    renderPage();

    fireEvent.click(await screen.findByText("إنشاء عقد من هذا القالب"));
    fireEvent.click(screen.getByText("معاينة المستند"));

    await waitFor(() => expect(toastWarning).toHaveBeenCalledWith("يرجى تعبئة الحقول المطلوبة أولًا."));
    expect(createContractFromTemplate).not.toHaveBeenCalled();
  });
});
