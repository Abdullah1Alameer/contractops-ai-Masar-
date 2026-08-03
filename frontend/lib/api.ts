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

export async function uploadContract(file: File, type: "main" | "subcontract", parentId?: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("type", type);
  if (parentId) form.append("parent_main_contract_id", parentId);
  return api<{ id: string; status: string }>("/api/contracts", { method: "POST", body: form });
}
