/** @vitest-environment jsdom */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import AiSummaryPanel from "@/components/contract/AiSummaryPanel";
import { I18nProvider } from "@/lib/i18n";

vi.mock("@/lib/api", () => ({
  fetchContractSummary: vi.fn().mockResolvedValue({
    status: "ready",
    summary_ar: {
      purpose: {
        status: "stated",
        overview: "ملخص",
        items: [{ text: "بند", citations: [] }],
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
});
