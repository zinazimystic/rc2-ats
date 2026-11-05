export class ApiError extends Error {
  status: number;
  code: string;
  errors?: { loc?: (string | number)[]; msg: string }[];
  body: unknown;
  constructor(status: number, detail: string, code: string, body?: unknown) {
    super(detail);
    this.status = status;
    this.code = code;
    this.body = body;
    const b = body as { errors?: ApiError["errors"] } | undefined;
    this.errors = b?.errors;
  }
}

interface Opts {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  form?: FormData;
  signal?: AbortSignal;
}

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export async function api<T>(path: string, opts: Opts = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method: opts.method ?? (body ? "POST" : "GET"),
      headers,
      body,
      credentials: "same-origin",
      signal: opts.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    throw new ApiError(0, "Cannot reach the server. Check your connection and try again.", "network_error");
  }
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const d = data as { detail?: unknown; code?: string } | null;
    let detail = res.statusText || "Request failed";
    if (d && typeof d === "object" && typeof d.detail === "string") detail = d.detail;
    else if (res.status === 502 || res.status === 503 || res.status === 504)
      detail = "The server is unavailable right now. Please retry in a moment.";
    throw new ApiError(res.status, detail, (d && typeof d === "object" && d.code) || `http_${res.status}`, data);
  }
  return data as T;
}

export function errMsg(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === "validation_error" && e.errors?.length) {
      return e.errors.map((x) => `${(x.loc ?? []).filter((p) => p !== "body").join(".")}: ${x.msg}`).join("; ");
    }
    return e.message;
  }
  return e instanceof Error ? e.message : "Something went wrong";
}
