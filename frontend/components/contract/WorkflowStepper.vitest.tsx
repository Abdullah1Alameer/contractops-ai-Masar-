/** @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import WorkflowStepper from "@/components/contract/WorkflowStepper";
import { I18nProvider } from "@/lib/i18n";

// I18nProvider defaults to Arabic (see other *.vitest.tsx files in this repo).
const STEP = {
  draft: "مسودة",
  review: "مراجعة",
  negotiation: "تفاوض",
  approval: "موافقة",
  signature: "توقيع",
  completed: "مكتمل",
};

function activeStepLabel(container: HTMLElement) {
  // The active step is the one styled with bg-brand-600 (see component).
  const active = container.querySelector("li div.bg-brand-600");
  return active?.textContent?.trim();
}

function renderStepper(stage: string | null | undefined) {
  const { container } = render(
    <I18nProvider>
      <WorkflowStepper stage={stage} />
    </I18nProvider>
  );
  return container;
}

afterEach(cleanup);

describe("WorkflowStepper — canonical stage-to-step mapping", () => {
  it("highlights Negotiation, not Draft, for a contract in negotiation", () => {
    const container = renderStepper("negotiation");
    expect(activeStepLabel(container)).toContain(STEP.negotiation);
  });

  it("highlights Draft for draft and ready_for_client", () => {
    expect(activeStepLabel(renderStepper("draft"))).toContain(STEP.draft);
    expect(activeStepLabel(renderStepper("ready_for_client"))).toContain(STEP.draft);
  });

  it("highlights Review for client_review", () => {
    expect(activeStepLabel(renderStepper("client_review"))).toContain(STEP.review);
  });

  it("highlights Approval for internal_review", () => {
    expect(activeStepLabel(renderStepper("internal_review"))).toContain(STEP.approval);
  });

  it("highlights Signature for ready_to_sign and partially_signed", () => {
    expect(activeStepLabel(renderStepper("ready_to_sign"))).toContain(STEP.signature);
    expect(activeStepLabel(renderStepper("partially_signed"))).toContain(STEP.signature);
  });

  it("highlights Completed for signed, active, and completed", () => {
    expect(activeStepLabel(renderStepper("signed"))).toContain(STEP.completed);
    expect(activeStepLabel(renderStepper("active"))).toContain(STEP.completed);
    expect(activeStepLabel(renderStepper("completed"))).toContain(STEP.completed);
  });

  it("highlights nothing for an unset stage rather than guessing", () => {
    const container = renderStepper(null);
    expect(container.querySelector("li div.bg-brand-600")).toBeNull();
  });

  it("renders a terminal label instead of the linear stepper for rejected/cancelled/terminated", () => {
    renderStepper("rejected");
    expect(screen.getByText("مرفوض")).toBeTruthy();
    expect(screen.queryByText(STEP.draft)).toBeNull();
  });
});
