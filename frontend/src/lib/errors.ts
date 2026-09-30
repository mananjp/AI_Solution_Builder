/**
 * Typed error model for the API layer.
 *
 * The previous fetch wrapper threw bare `Error` objects and dropped the HTTP
 * status, so callers had to regex the human-readable message to make a control
 * decision (see chat/page.tsx: `if (/404|not found/i.test(msg))`). Every
 * failure is now an `ApiError` that carries the status, the backend's stable
 * error code, and whether a retry could plausibly succeed.
 */

/** Stable machine-readable codes, mirroring backend/app/core/errors.py. */
export type ApiErrorCode =
  | "NETWORK"
  | "TIMEOUT"
  | "CANCELLED"
  | "UNAUTHENTICATED"
  | "FORBIDDEN"
  | "NOT_FOUND"
  | "CONFLICT"
  | "VALIDATION"
  | "RATE_LIMITED"
  | "PAYMENT_REQUIRED"
  | "SERVER"
  | "UNKNOWN";

export interface ApiErrorOptions {
  status?: number;
  code?: ApiErrorCode;
  /** Field-level or contextual detail from the backend `error.details`. */
  details?: unknown;
  /** The request that failed, for logging. Never includes the auth token. */
  endpoint?: string;
  cause?: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode;
  readonly details?: unknown;
  readonly endpoint?: string;

  constructor(message: string, options: ApiErrorOptions = {}) {
    super(message, { cause: options.cause });
    this.name = "ApiError";
    this.status = options.status ?? 0;
    this.code = options.code ?? "UNKNOWN";
    this.details = options.details;
    this.endpoint = options.endpoint;
  }

  /** A session that cannot be recovered by retrying the same request. */
  get isAuthError(): boolean {
    return this.status === 401 || this.status === 403;
  }

  /** Server-side faults and transport blips worth retrying. */
  get isRetryable(): boolean {
    if (this.code === "TIMEOUT" || this.code === "NETWORK") return true;
    if (this.status === 429) return true;
    return this.status >= 500;
  }

  /** True when the backend said the request itself was malformed. */
  get isClientError(): boolean {
    return this.status >= 400 && this.status < 500;
  }
}

/** Narrow an unknown thrown value to an ApiError, wrapping if necessary. */
export function toApiError(err: unknown, endpoint?: string): ApiError {
  if (err instanceof ApiError) return err;
  if (err instanceof DOMException && err.name === "AbortError") {
    return new ApiError("Request cancelled", { code: "CANCELLED", endpoint, cause: err });
  }
  const message = err instanceof Error ? err.message : String(err);
  return new ApiError(message, { code: "NETWORK", endpoint, cause: err });
}

/** Map an HTTP status onto a stable code. */
export function codeForStatus(status: number): ApiErrorCode {
  switch (status) {
    case 401:
      return "UNAUTHENTICATED";
    case 402:
      return "PAYMENT_REQUIRED";
    case 403:
      return "FORBIDDEN";
    case 404:
      return "NOT_FOUND";
    case 409:
      return "CONFLICT";
    case 422:
    case 400:
      return "VALIDATION";
    case 429:
      return "RATE_LIMITED";
    default:
      return status >= 500 ? "SERVER" : "UNKNOWN";
  }
}

/** A message safe to show a user, for any thrown value. */
export function errorMessage(err: unknown, fallback = "Something went wrong."): string {
  if (err instanceof ApiError) return err.message || fallback;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
