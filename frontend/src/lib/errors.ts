/* One place that turns any thrown value into a friendly, jargon-free sentence. */

const BY_CODE: Record<string, string> = {
  network_error: "We can’t reach the server. Check your connection and try again.",
  unauthorized: "Your session has expired. Please sign in again.",
  http_401: "Your session has expired. Please sign in again.",
  http_403: "You don’t have permission to do that.",
  forbidden: "You don’t have permission to do that.",
  http_404: "We couldn’t find what you were looking for. It may have been removed.",
  not_found: "We couldn’t find what you were looking for. It may have been removed.",
  http_413: "That file is too large.",
  http_429: "You’re doing that too quickly. Please wait a moment and try again.",
  rate_limited: "You’re doing that too quickly. Please wait a moment and try again.",
  http_500: "Something went wrong on our side. Please try again.",
  http_502: "The service is unavailable right now. Please try again in a moment.",
  http_503: "The service is unavailable right now. Please try again in a moment.",
  http_504: "The service is taking too long to respond. Please try again.",
  validation_error: "Some details look incorrect. Please check them and try again.",
  resume_in_use: "This resume is attached to an application, so it can’t be deleted right now.",
  already_applied: "You’ve already applied to this role.",
  job_closed: "This position is no longer accepting applications.",
  schedule_conflict: "That time clashes with another interview.",
  llm_unavailable: "Suggestions aren’t available right now. Please try again later.",
  already_processing: "This is already being processed. Please wait a moment.",
  invalid_code: "That code isn’t right. Check it and try again.",
  code_expired: "That code has expired. Request a new one.",
};

// Business-rule codes whose server detail is already written for end users.
const FRIENDLY_DETAIL = new Set(["resume_in_use", "already_applied", "job_closed", "schedule_conflict", "invalid_code", "code_expired", "already_processing"]);

// Server strings that should never reach a user.
const JARGON = /\b(llm|embeddings?|json|traceback|exception|stack|sqlalchemy|psycopg|nonetype|keyerror|rule-based|openai|anthropic)\b/i;

interface ErrLike {
  message?: string;
  code?: string;
  status?: number;
  name?: string;
  errors?: { loc?: (string | number)[]; msg: string }[];
}

export function friendlyError(e: unknown, fallback = "Something went wrong. Please try again."): string {
  if (typeof e === "string") return JARGON.test(e) ? fallback : e;
  if (!e || typeof e !== "object") return fallback;
  const err = e as ErrLike;
  const code = err.code;
  const msg = err.message;
  if (code && BY_CODE[code]) {
    if (msg && FRIENDLY_DETAIL.has(code) && !JARGON.test(msg)) return msg;
    return BY_CODE[code];
  }
  if (err.name === "AbortError") return "Cancelled.";
  if (err.status !== undefined && err.status >= 400 && err.status < 500 && msg && !JARGON.test(msg)) return msg;
  if (err.status !== undefined && BY_CODE[`http_${err.status}`]) return BY_CODE[`http_${err.status}`];
  if (err.status === undefined && msg && !JARGON.test(msg)) return msg;
  return fallback;
}

/** Readable list of field problems for a 422, or null when the error isn't one. */
export function fieldErrors(e: unknown): string | null {
  const err = e as ErrLike | null;
  if (err && err.code === "validation_error" && err.errors?.length) {
    return err.errors
      .map((x) => {
        const loc = (x.loc ?? []).filter((p) => p !== "body").join(" › ");
        return loc ? `${loc}: ${x.msg}` : x.msg;
      })
      .join("; ");
  }
  return null;
}
