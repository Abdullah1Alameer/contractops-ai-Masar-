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

async function parseError(res: Response): Promise<never> {
  let code = "unknown";
  try {
    const body = await res.json();
    code = body?.detail?.error ?? body?.error ?? "unknown";
  } catch {}
  throw new ApiError(res.status, code);
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${TOKEN}`, ...(init?.headers ?? {}) },
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
  contract_category?: string;
  confidence?: number;
  message?: string;
  supported_categories?: string[];
  status?: string;
  counts?: Record<string, number>;
}

export async function fetchDeadlines(contractId: string) {
  return api<import("./types").DeadlinesResponse>(`/api/contracts/${contractId}/deadlines`);
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
