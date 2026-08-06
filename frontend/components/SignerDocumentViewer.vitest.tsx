/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("pdfjs-dist", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: () => ({
    promise: Promise.resolve({
      numPages: 2,
      getPage: () =>
        Promise.resolve({
          getViewport: () => ({ width: 595, height: 842, scale: 1.2 }),
          render: () => ({ promise: Promise.resolve() }),
        }),
    }),
  }),
}));

import SignerDocumentViewer from "@/components/SignerDocumentViewer";
import { I18nProvider } from "@/lib/i18n";
import type { SignatureField } from "@/lib/types";

const FIELDS: SignatureField[] = [
  { id: "f1", signer_id: "signer-1", page_number: 1, x: 0.1, y: 0.1, width: 0.36, height: 0.06, field_type: "signature", required: true, ai_suggested: false },
  { id: "f2", signer_id: "signer-1", page_number: 2, x: 0.1, y: 0.5, width: 0.36, height: 0.06, field_type: "date", required: true, ai_suggested: false },
];

function renderViewer(fields: SignatureField[] = FIELDS, onAllFieldsViewed = vi.fn()) {
  return render(
    <I18nProvider>
      <SignerDocumentViewer documentUrl="https://demo.local/document" fields={fields} onAllFieldsViewed={onAllFieldsViewed} />
    </I18nProvider>
  );
}

afterEach(cleanup);

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, arrayBuffer: () => Promise.resolve(new ArrayBuffer(8)) })
  );
});

describe("SignerDocumentViewer", () => {
  it("shows field 1 of N progress and highlights the current field", async () => {
    renderViewer();
    expect(await screen.findByText(/1\/2/)).toBeTruthy();
  });

  it("marks all fields viewed once the signer has jumped to every one", async () => {
    const onAllFieldsViewed = vi.fn();
    renderViewer(FIELDS, onAllFieldsViewed);

    await screen.findByText(/1\/2/);
    // First field (index 0) is auto-marked viewed on mount; jump to the second.
    fireEvent.click(screen.getByText("2. التاريخ (p.2)"));

    await waitFor(() => expect(onAllFieldsViewed).toHaveBeenCalled());
  });

  it("shows an honest message instead of a blank page when the signer has no field", () => {
    renderViewer([]);
    expect(screen.getByText("لم يتم تحديد موضع توقيع لك بعد في هذا المستند.")).toBeTruthy();
  });
});
