/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchTemplates = vi.fn();

vi.mock("@/lib/api", () => ({
  fetchTemplates: (...args: unknown[]) => fetchTemplates(...args),
}));

import TemplatesPage from "@/app/templates/page";
import { I18nProvider } from "@/lib/i18n";

function renderPage() {
  return render(
    <I18nProvider>
      <TemplatesPage />
    </I18nProvider>
  );
}

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Templates list (Bug 2)", () => {
  it("links each template card to its own real detail page, not a shared /upload redirect", async () => {
    fetchTemplates.mockResolvedValue({
      templates: [
        { id: "tpl-msa", key: "msa", title_en: "Master Service Agreement", title_ar: "اتفاقية خدمات رئيسية", category: "Commercial", language: "both", industry: "Technology", usage_count: 42, updated_at: "2026-07-01T00:00:00+00:00" },
        { id: "tpl-nda", key: "nda", title_en: "Mutual NDA", title_ar: "اتفاقية عدم إفصاح متبادلة", category: "Legal", language: "both", industry: "All sectors", usage_count: 88, updated_at: "2026-06-15T00:00:00+00:00" },
      ],
    });
    renderPage();

    const links = await screen.findAllByText("استخدام القالب");
    expect(links).toHaveLength(2);
    expect(links[0].closest("a")?.getAttribute("href")).toBe("/templates/tpl-msa");
    expect(links[1].closest("a")?.getAttribute("href")).toBe("/templates/tpl-nda");
  });
});
