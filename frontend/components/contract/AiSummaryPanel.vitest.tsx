/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AiSummaryPanel from "@/components/contract/AiSummaryPanel";
import { I18nProvider } from "@/lib/i18n";

vi.mock("@/lib/api", () => ({
  fetchContractSummary: vi.fn().mockResolvedValue({
    status: "ready",
    summary_ar: {
      purpose: {
        status: "stated",
        overview: "ملخص",
        items: [
          {
            text: "بند",
            citations: [{ clause_ref: "4.2", page: 3, quote: "يلتزم الطرف الأول بتقديم إشعار خلال سبعة أيام." }],
          },
        ],
      },
    },
    summary_en: {
      purpose: {
        status: "stated",
        overview: "Overview",
        items: [{ text: "Item", citations: [] }],
      },
    },
    error_code: null,
    error_detail: null,
    generated_at: null,
    model: "test",
    is_stale: false,
  }),
  generateContractSummary: vi.fn(),
}));

afterEach(cleanup);

describe("AiSummaryPanel", () => {
  it("renders bilingual summary sections when ready", async () => {
    render(
      <I18nProvider>
        <AiSummaryPanel contractId="00000000-0000-0000-0000-000000000001" onCitation={() => {}} />
      </I18nProvider>
    );
    expect(await screen.findByText("ملخص")).toBeTruthy();
    fireEvent.click(screen.getByText("English"));
    expect(await screen.findByText("Overview")).toBeTruthy();
    expect(screen.getByText("Item")).toBeTruthy();
  });

  it("shows the exact quoted clause text inline when a citation is toggled, without navigating away", async () => {
    render(
      <I18nProvider>
        <AiSummaryPanel contractId="00000000-0000-0000-0000-000000000001" onCitation={vi.fn()} />
      </I18nProvider>
    );
    await screen.findByText("ملخص");

    const citationButton = screen.getByText(/4\.2.*p\.3/);
    expect(screen.queryByText("يلتزم الطرف الأول بتقديم إشعار خلال سبعة أيام.")).toBeNull();

    fireEvent.click(citationButton);

    expect(await screen.findByText("يلتزم الطرف الأول بتقديم إشعار خلال سبعة أيام.")).toBeTruthy();

    fireEvent.click(citationButton);
    expect(screen.queryByText("يلتزم الطرف الأول بتقديم إشعار خلال سبعة أيام.")).toBeNull();
  });

  it("jumping to the clause still calls onCitation with the source (existing navigation unchanged)", async () => {
    const onCitation = vi.fn();
    render(
      <I18nProvider>
        <AiSummaryPanel contractId="00000000-0000-0000-0000-000000000001" onCitation={onCitation} />
      </I18nProvider>
    );
    await screen.findByText("ملخص");

    fireEvent.click(screen.getByText("الانتقال إلى البند داخل المستند"));

    expect(onCitation).toHaveBeenCalledWith(
      expect.objectContaining({ page: 3, quote: "يلتزم الطرف الأول بتقديم إشعار خلال سبعة أيام." })
    );
  });
});
