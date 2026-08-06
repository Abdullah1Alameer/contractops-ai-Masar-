import { describe, expect, it } from "vitest";

import {
  bucketContract,
  filterContractsByPipelineBucket,
  pipelineHref,
  summarizePipeline,
  type HomeContractRow,
} from "@/lib/pipeline";
import type { WorkflowSummary } from "@/lib/types";

const workflow = (overrides: Partial<WorkflowSummary>): WorkflowSummary => ({
  review_status: null,
  negotiation_status: null,
  approval_status: null,
  signature_status: null,
  ...overrides,
});

const row = (overrides: Partial<HomeContractRow> = {}): HomeContractRow => ({
  id: "contract-1",
  status: "ready",
  stage: "negotiation",
  workflow_summary: workflow({}),
  ...overrides,
});

describe("bucketContract", () => {
  it("maps a sent review to sent_to_client", () => {
    expect(
      bucketContract(row({ workflow_summary: workflow({ review_status: "sent" }) }))
    ).toBe("sent_to_client");
  });

  it("maps an opened review to client_reviewing", () => {
    expect(
      bucketContract(row({ workflow_summary: workflow({ review_status: "opened" }) }))
    ).toBe("client_reviewing");
  });

  it("maps requested review changes to negotiating", () => {
    expect(
      bucketContract(row({ workflow_summary: workflow({ review_status: "changes_requested" }) }))
    ).toBe("negotiating");
  });

  it("maps an active approval to internal_review", () => {
    expect(
      bucketContract(row({ workflow_summary: workflow({ approval_status: "in_progress" }) }))
    ).toBe("internal_review");
  });

  it("maps a fully approved contract to awaiting_signature", () => {
    expect(
      bucketContract(
        row({
          stage: "ready_to_sign",
          workflow_summary: workflow({ approval_status: "approved" }),
        })
      )
    ).toBe("awaiting_signature");
  });

  it("maps a sent signature request to awaiting_signature", () => {
    expect(
      bucketContract(row({ workflow_summary: workflow({ signature_status: "sent" }) }))
    ).toBe("awaiting_signature");
  });

  it("maps a completed signature to signed unless the contract is active", () => {
    expect(
      bucketContract(row({ workflow_summary: workflow({ signature_status: "completed" }) }))
    ).toBe("signed");
    expect(
      bucketContract(
        row({
          stage: "active",
          workflow_summary: workflow({ signature_status: "completed" }),
        })
      )
    ).toBe("active");
  });

  it("gives completed and active lifecycle stages highest priority", () => {
    expect(bucketContract(row({ stage: "completed" }))).toBe("completed");
    expect(bucketContract(row({ stage: "active" }))).toBe("active");
  });

  it("buckets a freshly uploaded contract (stage draft, still processing) as draft, never negotiating", () => {
    expect(bucketContract(row({ stage: "draft", status: "processing" }))).toBe("draft");
  });

  it("buckets draft with extraction complete as draft (no negotiation/review workflow exists yet)", () => {
    expect(bucketContract(row({ stage: "draft", status: "ready" }))).toBe("draft");
  });

  it("buckets ready_for_client as draft (the existing pre-client-review bucket)", () => {
    expect(bucketContract(row({ stage: "ready_for_client", status: "ready" }))).toBe("draft");
  });

  it("buckets client_review by review status, falling back to sent_to_client if workflow_summary lacks one", () => {
    expect(
      bucketContract(row({ stage: "client_review", workflow_summary: workflow({ review_status: "opened" }) }))
    ).toBe("client_reviewing");
    expect(bucketContract(row({ stage: "client_review", workflow_summary: workflow({}) }))).toBe(
      "sent_to_client"
    );
  });

  it("does not crash or classify unknown workflow values as negotiating", () => {
    expect(
      bucketContract(
        row({
          stage: "unknown_stage",
          workflow_summary: workflow({ review_status: "unexpected_status" as never }),
        })
      )
    ).toBe("draft");
    expect(
      bucketContract(
        row({
          workflow_summary: workflow({ negotiation_status: "unexpected_status" as never }),
        })
      )
    ).toBe("draft");
  });
});

describe("pipeline summaries and links", () => {
  it("counts contracts using canonical workflow fields", () => {
    const summary = summarizePipeline(
      [
        row({ id: "sent", workflow_summary: workflow({ review_status: "sent" }) }),
        row({ id: "opened", workflow_summary: workflow({ review_status: "opened" }) }),
        row({ id: "approval", workflow_summary: workflow({ approval_status: "in_progress" }) }),
      ],
      new Set(["sent"])
    );

    expect(summary.find((bucket) => bucket.key === "sent_to_client")?.count).toBe(1);
    expect(summary.find((bucket) => bucket.key === "sent_to_client")?.highRiskCount).toBe(1);
    expect(summary.find((bucket) => bucket.key === "client_reviewing")?.count).toBe(1);
    expect(summary.find((bucket) => bucket.key === "internal_review")?.count).toBe(1);
  });

  it("uses a contracts-page bucket deep link supported by the list filter", () => {
    expect(pipelineHref("sent_to_client")).toBe("/contracts?bucket=sent_to_client");
    expect(pipelineHref("awaiting_signature")).toBe("/contracts?bucket=awaiting_signature");

    const contracts = [
      row({ id: "sent", workflow_summary: workflow({ review_status: "sent" }) }),
      row({ id: "opened", workflow_summary: workflow({ review_status: "opened" }) }),
    ];
    expect(filterContractsByPipelineBucket(contracts, "sent_to_client").map((item) => item.id)).toEqual(["sent"]);
  });
});
