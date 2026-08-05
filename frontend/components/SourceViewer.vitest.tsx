/** @vitest-environment jsdom */
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

const pdfMock = vi.hoisted(() => ({
  getDocument: vi.fn(),
}));

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: pdfMock.getDocument,
}));

import SourceViewer from "@/components/SourceViewer";
import { I18nProvider } from "@/lib/i18n";

const apiMock = vi.fn();
const fileMock = vi.fn();

vi.mock("@/lib/api", async (importOriginal) => {
  const orig = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...orig,
    api: (...args: unknown[]) => apiMock(...args),
    fetchContractFileBlob: (...args: unknown[]) => fileMock(...args),
  };
});

describe("SourceViewer", () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
    apiMock.mockReset();
    fileMock.mockReset();
    pdfMock.getDocument.mockReset();
    apiMock.mockResolvedValue({
      page: 2,
      text: "page two",
      char_start: 10,
      total_pages: 5,
      blocks: [],
    });
    fileMock.mockRejectedValue(new Error("no pdf in test"));
  });

  it("loads the page from citation target", async () => {
    render(
      <I18nProvider>
        <SourceViewer
          contractId="00000000-0000-0000-0000-000000000001"
          target={{ page: 2, char_start: 12, char_end: 20, quote: "sample" }}
        />
      </I18nProvider>
    );
    await waitFor(() => {
      expect(apiMock).toHaveBeenCalledWith("/api/contracts/00000000-0000-0000-0000-000000000001/raw?page=2");
    });
  });

  it("shows a loading state while the browser PDF module is not ready", async () => {
    fileMock.mockReturnValue(new Promise(() => undefined));

    render(
      <I18nProvider>
        <SourceViewer contractId="00000000-0000-0000-0000-000000000001" target={null} />
      </I18nProvider>
    );

    expect(await screen.findByText(/جارٍ التحميل|Loading/)).toBeTruthy();
  });

  it("shows a safe visible error when PDF loading fails", async () => {
    fileMock.mockResolvedValue(new Blob(["not a pdf"], { type: "application/pdf" }));
    pdfMock.getDocument.mockImplementation(() => {
      throw new Error("PDF module failed");
    });

    render(
      <I18nProvider>
        <SourceViewer contractId="00000000-0000-0000-0000-000000000001" target={null} />
      </I18nProvider>
    );

    expect(await screen.findByRole("alert")).toBeTruthy();
  });

  it("keeps the citation fallback visible when PDF rendering is unavailable", async () => {
    render(
      <I18nProvider>
        <SourceViewer
          contractId="00000000-0000-0000-0000-000000000001"
          target={{ page: 2, char_start: 12, char_end: 18, quote: "sample clause" }}
        />
      </I18nProvider>
    );

    expect(await screen.findByText("sample clause")).toBeTruthy();
  });
});
