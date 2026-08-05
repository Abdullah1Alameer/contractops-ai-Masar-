import type { TKey } from "@/lib/i18n";

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
  workflow_summary?: {
    review?: string | null;
    negotiation?: string | null;
    approval?: string | null;
    signature?: string | null;
  } | null;
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

export function bucketContract(c: HomeContractRow): PipelineKey {
  const status = c.status;
  const stage = c.stage ?? "negotiation";
  const review = c.workflow_summary?.review?.toLowerCase();

  if (status === "processing") return "draft";
  if (status === "needs_review") return "ai_review";

  if (review === "sent") return "sent_to_client";
  if (review === "opened") return "client_reviewing";

  if (stage === "internal_review") return "internal_review";
  if (stage === "negotiation") return "negotiating";
  if (stage === "approved" || stage === "awaiting_signature" || stage === "partially_signed") {
    return "awaiting_signature";
  }
  if (stage === "signed") return "signed";
  if (stage === "active") {
    if (c.end_date) {
      const end = new Date(c.end_date);
      if (!Number.isNaN(end.getTime()) && end < new Date()) return "completed";
    }
    return "active";
  }
  return "negotiating";
}

export function pipelineHref(key: PipelineKey): string {
  const stage = SERVER_STAGE[key];
  if (key === "ai_review") return "/contracts?status=needs_review";
  if (key === "draft") return "/contracts?status=processing";
  if (key === "sent_to_client" || key === "client_reviewing") return "/reviews";
  if (key === "completed") return `/contracts?stage=${stage}&bucket=completed`;
  return `/contracts?stage=${stage}&bucket=${key}`;
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
