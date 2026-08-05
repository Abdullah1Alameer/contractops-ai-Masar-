import type { TKey } from "@/lib/i18n";
import type { WorkflowSummary } from "@/lib/types";

export type PipelineKey =
  | "draft"
  | "ai_review"
  | "sent_to_client"
  | "client_reviewing"
  | "negotiating"
  | "internal_review"
  | "awaiting_signature"
  | "signed"
  | "active"
  | "completed";

export type HomeContractRow = {
  id: string;
  status: string;
  stage?: string | null;
  value_sar?: number | null;
  end_date?: string | null;
  workflow_summary?: WorkflowSummary | null;
};

export type PipelineBucketSummary = {
  key: PipelineKey;
  count: number;
  valueSar: number;
  highRiskCount: number;
  serverStage: string;
  labelKey: TKey;
};

export const PIPELINE_ORDER: PipelineKey[] = [
  "draft",
  "ai_review",
  "sent_to_client",
  "client_reviewing",
  "negotiating",
  "internal_review",
  "awaiting_signature",
  "signed",
  "active",
  "completed",
];

const LABEL_KEYS: Record<PipelineKey, TKey> = {
  draft: "home.pipeline.draft",
  ai_review: "home.pipeline.aiReview",
  sent_to_client: "home.pipeline.sentToClient",
  client_reviewing: "home.pipeline.clientReviewing",
  negotiating: "home.pipeline.negotiating",
  internal_review: "home.pipeline.internalReview",
  awaiting_signature: "home.pipeline.awaitingSignature",
  signed: "home.pipeline.signed",
  active: "home.pipeline.active",
  completed: "home.pipeline.completed",
};

const SERVER_STAGE: Record<PipelineKey, string> = {
  draft: "negotiation",
  ai_review: "negotiation",
  sent_to_client: "negotiation",
  client_reviewing: "negotiation",
  negotiating: "negotiation",
  internal_review: "internal_review",
  awaiting_signature: "awaiting_signature",
  signed: "signed",
  active: "active",
  completed: "active",
};

const KNOWN_STAGES = new Set([
  "",
  "draft",
  "negotiation",
  "internal_review",
  "approved",
  "ready_to_sign",
  "awaiting_signature",
  "partially_signed",
  "signed",
  "active",
  "completed",
]);
const KNOWN_CONTRACT_STATUSES = new Set(["processing", "ready", "needs_review", "failed", "unsupported", "completed"]);
const KNOWN_REVIEW_STATUSES = new Set(["sent", "opened", "approved", "rejected", "changes_requested", "expired"]);
const KNOWN_NEGOTIATION_STATUSES = new Set([
  "pending_analysis",
  "ready",
  "edited_by_legal",
  "sent_to_client",
  "client_responded",
  "accepted",
  "closed",
]);
const KNOWN_APPROVAL_STATUSES = new Set(["in_progress", "approved", "rejected", "changes_requested", "cancelled"]);
const KNOWN_SIGNATURE_STATUSES = new Set([
  "draft",
  "created",
  "sent",
  "viewed",
  "partially_signed",
  "completed",
  "declined",
  "expired",
  "cancelled",
  "error",
]);

export function bucketContract(c: HomeContractRow): PipelineKey {
  const status = c.status.toLowerCase();
  const stage = (c.stage ?? "").toLowerCase();
  const rawReview = c.workflow_summary?.review_status?.toLowerCase() ?? null;
  const rawNegotiation = c.workflow_summary?.negotiation_status?.toLowerCase() ?? null;
  const rawApproval = c.workflow_summary?.approval_status?.toLowerCase() ?? null;
  const rawSignature = c.workflow_summary?.signature_status?.toLowerCase() ?? null;
  const review = rawReview && KNOWN_REVIEW_STATUSES.has(rawReview) ? rawReview : null;
  const negotiation =
    rawNegotiation && KNOWN_NEGOTIATION_STATUSES.has(rawNegotiation) ? rawNegotiation : null;
  const approval = rawApproval && KNOWN_APPROVAL_STATUSES.has(rawApproval) ? rawApproval : null;
  const signature = rawSignature && KNOWN_SIGNATURE_STATUSES.has(rawSignature) ? rawSignature : null;

  if (
    process.env.NODE_ENV !== "production" &&
    (!KNOWN_STAGES.has(stage) ||
      !KNOWN_CONTRACT_STATUSES.has(status) ||
      (rawReview !== null && review === null) ||
      (rawNegotiation !== null && negotiation === null) ||
      (rawApproval !== null && approval === null) ||
      (rawSignature !== null && signature === null))
  ) {
    console.warn("Unknown contract workflow state", {
      stage,
      status,
      review: rawReview,
      negotiation: rawNegotiation,
      approval: rawApproval,
      signature: rawSignature,
    });
  }

  const ended =
    stage === "active" &&
    !!c.end_date &&
    !Number.isNaN(new Date(c.end_date).getTime()) &&
    new Date(c.end_date) < new Date();

  if (stage === "completed" || status === "completed" || ended) return "completed";
  if (stage === "active") return "active";

  if (stage === "signed" || signature === "completed") return "signed";
  if (
    stage === "ready_to_sign" ||
    stage === "awaiting_signature" ||
    stage === "partially_signed" ||
    ["created", "sent", "viewed", "partially_signed"].includes(signature ?? "")
  ) {
    return "awaiting_signature";
  }

  if (
    stage === "internal_review" ||
    stage === "approved" ||
    approval === "in_progress" ||
    approval === "changes_requested"
  ) {
    return "internal_review";
  }

  const activeNegotiation = !!negotiation && !["accepted", "closed"].includes(negotiation);
  if (stage === "negotiation" && (activeNegotiation || review === "changes_requested")) {
    return "negotiating";
  }
  if (review === "opened") return "client_reviewing";
  if (review === "sent") return "sent_to_client";

  if (status === "needs_review") return "ai_review";
  if (status === "processing" || stage === "draft") return "draft";

  return "draft";
}

export function pipelineHref(key: PipelineKey): string {
  return `/contracts?bucket=${key}`;
}

export function filterContractsByPipelineBucket<T extends HomeContractRow>(
  contracts: T[],
  bucket: string | null
): T[] {
  if (!bucket) return contracts;
  if (!PIPELINE_ORDER.includes(bucket as PipelineKey)) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("Unknown pipeline bucket", { bucket });
    }
    return contracts;
  }
  return contracts.filter((contract) => bucketContract(contract) === bucket);
}

export function summarizePipeline(
  contracts: HomeContractRow[],
  highRiskIds: Set<string>
): PipelineBucketSummary[] {
  const acc: Record<PipelineKey, { count: number; valueSar: number; highRisk: number }> = {} as Record<
    PipelineKey,
    { count: number; valueSar: number; highRisk: number }
  >;

  for (const key of PIPELINE_ORDER) {
    acc[key] = { count: 0, valueSar: 0, highRisk: 0 };
  }

  for (const c of contracts) {
    const key = bucketContract(c);
    acc[key].count += 1;
    acc[key].valueSar += Number(c.value_sar) || 0;
    if (highRiskIds.has(c.id)) acc[key].highRisk += 1;
  }

  return PIPELINE_ORDER.map((key) => ({
    key,
    count: acc[key].count,
    valueSar: acc[key].valueSar,
    highRiskCount: acc[key].highRisk,
    serverStage: SERVER_STAGE[key],
    labelKey: LABEL_KEYS[key],
  }));
}

export function formatPortfolioSar(value: number, locale: string): string {
  if (value <= 0) return "—";
  return new Intl.NumberFormat(locale === "ar" ? "ar-SA" : "en-SA", {
    style: "currency",
    currency: "SAR",
    maximumFractionDigits: 0,
  }).format(value);
}
