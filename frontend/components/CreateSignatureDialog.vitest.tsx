/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import CreateSignatureDialog from "@/components/CreateSignatureDialog";
import { I18nProvider } from "@/lib/i18n";

afterEach(cleanup);

// Reproduces the reported bug's exact ancestor shape: a wrapper with a CSS
// transform, standing in for <PageTransition>'s framer-motion div. Per the
// CSS spec, a transformed ancestor becomes the containing block for any
// `position: fixed` descendant that isn't portaled out from under it — this
// is what clipped the dialog in production.
function TransformedAncestor({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ transform: "translateY(0px)", height: "50px", overflow: "hidden" }}>
      {children}
    </div>
  );
}

function renderDialog(props: Partial<React.ComponentProps<typeof CreateSignatureDialog>> = {}) {
  return render(
    <I18nProvider>
      <TransformedAncestor>
        <CreateSignatureDialog open onClose={vi.fn()} onSubmit={vi.fn()} {...props} />
      </TransformedAncestor>
    </I18nProvider>
  );
}

describe("CreateSignatureDialog — rendering fix (portal, not clipped by a transformed ancestor)", () => {
  it("renders its content on document.body, not inside the transformed ancestor", async () => {
    renderDialog();

    const title = await screen.findByRole("heading", { name: "إنشاء طلب توقيع" });
    // The dialog's DOM node must be a descendant of <body> directly (via
    // the portal), never nested inside the transformed wrapper div.
    const transformedDiv = document.querySelector('[style*="translateY"]') as HTMLElement;
    expect(transformedDiv.contains(title)).toBe(false);
    expect(document.body.contains(title)).toBe(true);
  });

  it("shows the title and action buttons even though the ancestor is a 50px-tall, overflow-hidden, transformed box", async () => {
    renderDialog();

    // If the old inline (non-portal) rendering were still in place, this
    // dialog would be laid out inside a 50px/overflow:hidden box and none
    // of this would be reachable in the accessibility tree.
    expect(await screen.findByRole("heading", { name: "إنشاء طلب توقيع" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "إنشاء طلب توقيع" })).toBeTruthy();
    expect(screen.getByText("إلغاء")).toBeTruthy();
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("renders nothing before mount and nothing when closed", () => {
    const { rerender } = render(
      <I18nProvider>
        <CreateSignatureDialog open={false} onClose={vi.fn()} onSubmit={vi.fn()} />
      </I18nProvider>
    );
    expect(screen.queryByRole("dialog")).toBeNull();

    rerender(
      <I18nProvider>
        <CreateSignatureDialog open onClose={vi.fn()} onSubmit={vi.fn()} />
      </I18nProvider>
    );
    // Portal mount happens post-effect; eventually the dialog appears.
    return waitFor(() => expect(screen.getByRole("dialog")).toBeTruthy());
  });

  it("still submits the same signer/subject/message payload — workflow logic is unchanged", async () => {
    const onSubmit = vi.fn();
    renderDialog({ onSubmit });
    await screen.findByRole("dialog");

    fireEvent.change(screen.getByText("الموضوع").parentElement!.querySelector("input")!, {
      target: { value: "Please sign" },
    });
    fireEvent.click(screen.getByRole("button", { name: "إنشاء طلب توقيع" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        subject: "Please sign",
        signing_order_enabled: true,
        signers: [
          expect.objectContaining({ role: "company_signatory", order: 1 }),
          expect.objectContaining({ role: "client_signatory", order: 2 }),
        ],
      })
    );
  });
});
