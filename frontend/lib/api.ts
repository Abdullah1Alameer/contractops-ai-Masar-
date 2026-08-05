import { invalidateContract } from "./cache";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN = process.env.NEXT_PUBLIC_DEMO_TOKEN ?? "demo-secret-token";

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string) {
    super(code);
    this.status = status;
    this.code = code;
  }
}

export function apiErrorCode(error: unknown, fallback = "unknown"): string {
  return error instanceof ApiError ? error.code : fallback;
}

async function parseError(res: Response): Promise<never> {
  let code = "unknown";
  try {
    const body = await res.json();
    code = body?.detail?.code ?? body?.detail?.error ?? body?.error ?? "unknown";
  } catch {}
  throw new ApiError(res.status, code);
}

export const DEMO_ROLE_STORAGE = "demoRole";
export const DEMO_ROLE_EVENT = "demo-role-changed";

function demoRoleHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const role = localStorage.getItem(DEMO_ROLE_STORAGE) || "legal";
  return { "X-Demo-Role": role };
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${TOKEN}`, ...demoRoleHeader(), ...(init?.headers ?? {}) },
  });
  if (!res.ok) await parseError(res);
  return res.json();
}

/** Like api() but also reports whether the endpoint is a teammate placeholder. */
export async function apiWithMeta<T>(path: string): Promise<{ data: T; placeholder: boolean }> {
  const res = await fetch(`${BASE}${path}`, { headers: { Authorization: `Bearer ${TOKEN}` } });
  if (!res.ok) await parseError(res);
  return { data: await res.json(), placeholder: res.headers.get("X-Placeholder") === "true" };
}

export async function apiJson<T>(path: string, method: string, body: unknown): Promise<T> {
  return api<T>(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function uploadContract(file: File) {
  const form = new FormData();
  form.append("file", file);
  return api<{ id: string; status: string }>("/api/contracts", { method: "POST", body: form });
}

export async function deleteContract(id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/contracts/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${TOKEN}` },
  });
  if (!res.ok) await parseError(res);
}

export interface ExtractResult {
  supported?: boolean;
  deleted?: boolean;
  contract_id?: string;
  contract_category?: string;
  confidence?: number;
  message?: string;
  needs_review?: boolean;
  supported_categories?: string[];
  status?: string;
  counts?: Record<string, number>;
}

export async function reclassifyContract(contractId: string, contractCategory: string, actor = "user") {
  return apiJson<{ reclassified: boolean; extraction: ExtractResult }>(
    `/api/contracts/${contractId}/reclassify`,
    "POST",
    { contract_category: contractCategory, actor }
  );
}

export async function fetchDeadlines(contractId: string) {
  return api<import("./types").DeadlinesResponse>(`/api/contracts/${contractId}/deadlines`);
}

export async function fetchContractRisk(contractId: string) {
  return api<import("./types").RiskSummary>(`/api/contracts/${contractId}/risk`);
}

export async function fetchNegotiationOpportunities(contractId: string) {
  return api<{ opportunities: import("./types").NegotiationOpportunityRow[] }>(
    `/api/contracts/${contractId}/negotiation-opportunities`
  );
}

export async function rebuildContractIntelligence(
  contractId: string,
  targets?: string[]
) {
  return apiJson<{ contract_id: string; targets: string[]; results: Record<string, unknown> }>(
    `/api/contracts/${contractId}/intelligence/rebuild`,
    "POST",
    { targets: targets ?? null }
  );
}

export async function fetchContractSummary(contractId: string) {
  return api<import("./types").ContractSummaryPayload>(`/api/contracts/${contractId}/summary`);
}

export async function generateContractSummary(contractId: string, force = false) {
  return apiJson<{ status: string; contract_id: string }>(
    `/api/contracts/${contractId}/summary/generate`,
    "POST",
    { force }
  );
}

export async function fetchContractFileBlob(contractId: string): Promise<Blob> {
  const res = await fetch(`${BASE}/api/contracts/${contractId}/file`, {
    headers: { Authorization: `Bearer ${TOKEN}`, ...demoRoleHeader() },
  });
  if (!res.ok) await parseError(res);
  return res.blob();
}

export async function reextractContractText(contractId: string) {
  return apiJson<{ reanchored: number; unverified: number; pages: number }>(
    `/api/contracts/${contractId}/reextract-text`,
    "POST",
    {}
  );
}

export async function rebuildDeadlines(contractId: string) {
  return api<import("./types").DeadlinesResponse>(`/api/contracts/${contractId}/deadlines/rebuild`, {
    method: "POST",
  });
}

export async function getDemoToday() {
  return api<{ today: string }>("/api/demo/today");
}

export async function setDemoToday(today: string) {
  return apiJson<{ today: string }>("/api/demo/today", "POST", { today });
}

export async function logContractEvent(
  contractId: string,
  body: { type: string; description?: string; event_date: string }
) {
  return api<import("./types").DeadlinesResponse & { event: Record<string, string> }>(
    `/api/contracts/${contractId}/events`,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
  );
}

export async function fetchMilestones(contractId: string) {
  return api<import("./types").MilestonesResponse>(`/api/contracts/${contractId}/milestones`);
}

export async function rebuildMilestones(contractId: string) {
  return api<import("./types").MilestonesResponse>(`/api/contracts/${contractId}/milestones/rebuild`, {
    method: "POST",
  });
}

export async function patchMilestone(
  milestoneId: string,
  body: { paid?: boolean; precondition_id?: string; completed?: boolean; preconditions?: unknown[] }
) {
  return apiJson<import("./types").PaymentMilestoneRow>(`/api/milestones/${milestoneId}`, "PATCH", body);
}

export async function listFlowdownContracts() {
  return api<import("./types").FlowdownContractsList>("/api/flowdown/contracts");
}

export async function runFlowdown(mainId: string, subId: string) {
  return apiJson<import("./types").FlowdownResponse>("/api/flowdown", "POST", {
    main_contract_id: mainId,
    subcontract_id: subId,
  });
}

export async function getFlowdown(mainId: string, subId: string) {
  return api<import("./types").FlowdownResponse>(
    `/api/flowdown?main_id=${encodeURIComponent(mainId)}&sub_id=${encodeURIComponent(subId)}`
  );
}

const BASE_PUBLIC = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function publicApi<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_PUBLIC}${path}`, init);
  if (!res.ok) await parseError(res);
  return res.json();
}

export async function publicApiJson<T>(path: string, method: string, body: unknown): Promise<T> {
  return publicApi<T>(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function sendContractForReview(
  contractId: string,
  body: {
    recipient_name: string;
    recipient_email: string;
    message?: string;
    sender_name?: string;
    sender_email?: string;
    expires_in_days?: number;
  }
) {
  const res = await apiJson<import("./types").SendReviewResponse>(`/api/contracts/${contractId}/review/send`, "POST", body);
  invalidateContract(contractId);
  return res;
}

export async function fetchContractReviews(contractId: string) {
  return api<import("./types").ReviewRequestRow[]>(`/api/contracts/${contractId}/reviews`);
}

export async function fetchReviewsSummary() {
  return api<{ items: import("./types").ReviewRequestRow[] }>("/api/reviews/summary");
}

export async function fetchReviewPortal(token: string) {
  return publicApi<import("./types").ReviewPortalPayload>(`/api/review/${encodeURIComponent(token)}`);
}

export async function reviewApprove(token: string) {
  return publicApiJson<{ status: string }>(`/api/review/${encodeURIComponent(token)}/approve`, "POST", {});
}

export async function reviewReject(token: string, reason: string) {
  return publicApiJson<{ status: string }>(
    `/api/review/${encodeURIComponent(token)}/reject`,
    "POST",
    { reason }
  );
}

export async function reviewRequestChanges(token: string, general_comment: string) {
  return publicApiJson<{ status: string }>(
    `/api/review/${encodeURIComponent(token)}/request-changes`,
    "POST",
    { general_comment }
  );
}

export async function reviewAddComment(
  token: string,
  body: { comment: string; clause_ref?: string; page?: number }
) {
  return publicApiJson<import("./types").ReviewCommentRow>(
    `/api/review/${encodeURIComponent(token)}/comment`,
    "POST",
    body
  );
}

export async function fetchNegotiations(contractId: string) {
  return api<import("./types").NegotiationsResponse>(`/api/contracts/${contractId}/negotiations`);
}

export async function analyzeNegotiation(reviewId: string, commentId?: string | null) {
  return apiJson<import("./types").NegotiationRow>("/api/negotiation/analyze", "POST", {
    review_id: reviewId,
    comment_id: commentId ?? null,
  });
}

export async function patchNegotiation(
  id: string,
  body: Partial<{
    ai_summary: string;
    business_impact: string;
    legal_impact: string;
    risk_level: string;
    recommendation: string;
    reasoning: string;
    counter_clause: string;
    counter_clause_ar: string;
    lawyer_final_clause: string | null;
    lawyer_final_clause_ar: string | null;
    status: string;
  }>
) {
  return apiJson<import("./types").NegotiationRow>(`/api/negotiations/${id}`, "PATCH", body);
}

export async function sendNegotiationUpdated(id: string) {
  return apiJson<import("./types").SendNegotiationResponse>(`/api/negotiations/${id}/send`, "POST", {});
}

export async function abandonNegotiation(id: string, reason: string) {
  return apiJson<import("./types").NegotiationRow>(
    `/api/negotiations/${id}/abandon`,
    "POST",
    { reason }
  );
}

export async function fetchApprovals(contractId: string) {
  return api<import("./types").ApprovalsResponse>(`/api/contracts/${contractId}/approvals`);
}

export async function startApproval(
  contractId: string,
  body: {
    approver_names?: Record<string, string>;
    override?: { reason: string; negotiation_ids: string[]; rules?: string[] };
  } = {}
) {
  const res = await apiJson<import("./types").ApprovalWorkflowView>(
    `/api/contracts/${contractId}/approvals/start`,
    "POST",
    body
  );
  invalidateContract(contractId);
  return res;
}

export async function patchApprovalStep(stepId: string, body: { status: string; comment?: string }) {
  const res = await apiJson<import("./types").ApprovalWorkflowView>(`/api/approvals/${stepId}`, "PATCH", body);
  if (res.contract_id) invalidateContract(res.contract_id);
  return res;
}

export async function cancelApproval(contractId: string, reason: string) {
  const res = await apiJson<import("./types").ApprovalWorkflowView>(
    `/api/contracts/${contractId}/approvals/cancel`,
    "POST",
    { reason }
  );
  invalidateContract(contractId);
  return res;
}

export async function fetchActivity(contractId: string) {
  return api<{ events: import("./types").ActivityEventRow[] }>(`/api/contracts/${contractId}/activity`);
}

export async function fetchApprovalSummary() {
  return api<import("./types").ApprovalSummaryKpis>("/api/approvals/summary");
}

export async function fetchSignatureBundle(contractId: string) {
  return api<import("./types").SignatureBundleResponse>(`/api/contracts/${contractId}/signature-request`);
}

export async function createSignatureRequest(
  contractId: string,
  body: {
    subject: string;
    message?: string;
    expires_at: string;
    signing_order_enabled: boolean;
    signers: { name: string; email: string; role: string; order: number }[];
  }
) {
  return apiJson<import("./types").SignatureBundleResponse & { signer_links?: { signer_link: string; token: string }[] }>(
    `/api/contracts/${contractId}/signature-request`,
    "POST",
    body
  );
}

export async function sendSignatureRequest(requestId: string) {
  return apiJson<import("./types").SignatureBundleResponse>(`/api/signature-requests/${requestId}/send`, "POST", {});
}

export async function cancelSignatureRequest(requestId: string) {
  return apiJson<import("./types").SignatureBundleResponse>(`/api/signature-requests/${requestId}/cancel`, "POST", {});
}

export async function resendSignatureSigner(requestId: string, signerId: string) {
  return apiJson<{ signer_link: string; token: string; email: Record<string, string> }>(
    `/api/signature-requests/${requestId}/resend/${signerId}`,
    "POST",
    {}
  );
}

export async function fetchSignatureSummary() {
  return api<import("./types").SignatureSummaryKpis>("/api/signature/summary");
}

async function downloadAuthBlob(path: string): Promise<Blob> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${TOKEN}`, ...demoRoleHeader() },
  });
  if (!res.ok) await parseError(res);
  return res.blob();
}

export function downloadSignedPdf(requestId: string) {
  return downloadAuthBlob(`/api/signature-requests/${requestId}/signed-document`);
}

export function downloadSignatureCertificate(requestId: string) {
  return downloadAuthBlob(`/api/signature-requests/${requestId}/certificate`);
}

export function publicSignDocumentUrl(token: string) {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return `${base}/api/public/sign/${encodeURIComponent(token)}/document`;
}

export async function fetchSignerPortal(token: string) {
  return publicApi<import("./types").SignerPublicPayload>(`/api/public/sign/${encodeURIComponent(token)}`);
}

export async function openSignerPortal(token: string) {
  return publicApiJson<import("./types").SignerPublicPayload>(
    `/api/public/sign/${encodeURIComponent(token)}/open`,
    "POST",
    {}
  );
}

export async function submitSignerPortal(
  token: string,
  body: {
    signature_type: string;
    signature_value: string;
    consent_accepted: boolean;
    signer_name_confirmation: string;
  }
) {
  return publicApiJson<import("./types").SignerPublicPayload>(
    `/api/public/sign/${encodeURIComponent(token)}/submit`,
    "POST",
    body
  );
}

export async function declineSignerPortal(token: string, reason: string) {
  return publicApiJson<import("./types").SignerPublicPayload>(
    `/api/public/sign/${encodeURIComponent(token)}/decline`,
    "POST",
    { reason }
  );
}

export async function fetchVersions(contractId: string) {
  return api<import("./types").VersionHistoryResponse>(`/api/contracts/${contractId}/versions`);
}

export async function fetchVersionLineage(contractId: string) {
  return api<import("./types").VersionLineageResponse>(`/api/contracts/${contractId}/versions/lineage`);
}

export async function uploadNewVersion(
  contractId: string,
  file: File,
  source: string,
  changeSummary: string
) {
  const form = new FormData();
  form.append("file", file);
  form.append("source", source);
  form.append("change_summary", changeSummary);
  const res = await api<import("./types").ContractVersionRow>(`/api/contracts/${contractId}/versions`, {
    method: "POST",
    body: form,
  });
  invalidateContract(contractId);
  return res;
}

export async function setCurrentVersion(versionId: string, contractId?: string) {
  const res = await apiJson<import("./types").ContractVersionRow>(`/api/versions/${versionId}/set-current`, "POST", {});
  if (contractId) invalidateContract(contractId);
  return res;
}

export async function compareVersions(contractId: string, fromId: string, toId: string) {
  const q = new URLSearchParams({ from_id: fromId, to_id: toId });
  return api<import("./types").VersionCompareResult>(
    `/api/contracts/${contractId}/versions/compare?${q.toString()}`
  );
}

export function downloadVersionUrl(versionId: string) {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return `${base}/api/versions/${versionId}/download`;
}

export async function downloadVersionBlob(versionId: string): Promise<Blob> {
  const res = await fetch(downloadVersionUrl(versionId), {
    headers: { Authorization: `Bearer ${TOKEN}`, ...demoRoleHeader() },
  });
  if (!res.ok) await parseError(res);
  return res.blob();
}

export async function listNegotiationMonitorThreads(status?: string) {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return api<{ threads: import("./types").NegotiationMonitorThread[] }>(`/api/negotiation-monitor/threads${q}`);
}

export async function getNegotiationMonitorThread(threadId: string) {
  return api<import("./types").NegotiationMonitorThread & { emails: unknown[]; rounds: unknown[] }>(
    `/api/negotiation-monitor/threads/${threadId}`
  );
}

export async function importNegotiationEmail(threadId: string, body: Record<string, unknown>) {
  return apiJson(`/api/negotiation-monitor/threads/${threadId}/emails/import`, "POST", body);
}

export async function analyzeNegotiationThread(threadId: string, emailId?: string) {
  const q = emailId ? `?email_id=${emailId}` : "";
  return api<import("./types").NegotiationReviewPackageRow>(`/api/negotiation-monitor/threads/${threadId}/analyze${q}`, {
    method: "POST",
  });
}

export async function getNegotiationPackage(packageId: string) {
  return api<import("./types").NegotiationReviewPackageRow>(`/api/negotiation-monitor/packages/${packageId}`);
}

export async function approveNegotiationResponse(packageId: string, edited?: Record<string, unknown>) {
  return apiJson(`/api/negotiation-monitor/packages/${packageId}/approve-response`, "POST", { edited });
}

export async function sendNegotiationResponse(packageId: string, overrideReason?: string) {
  return apiJson(`/api/negotiation-monitor/packages/${packageId}/send-response`, "POST", {
    override_reason: overrideReason ?? null,
  });
}

export async function listSimulatedInbox() {
  return api<{ messages: { external_message_id: string; subject: string; preview: string }[] }>(
    "/api/negotiation-monitor/inbox/simulated"
  );
}

export async function listPlaybooks() {
  return api<{ playbooks: { id: string; name: string; contract_category: string | null }[] }>("/api/playbooks");
}

export async function getPlaybook(playbookId: string) {
  return api<{ id: string; name: string; rules: Record<string, unknown>[] }>(`/api/playbooks/${playbookId}`);
}
