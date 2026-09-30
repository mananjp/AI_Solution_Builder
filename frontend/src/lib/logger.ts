import { ApiError } from "./errors";

/**
 * Minimal structured client logger.
 *
 * Production builds emit a single JSON object per event so errors are
 * greppable and aggregatable; development builds get a readable line. Nothing
 * is silently swallowed: `log.error` records the message, the endpoint and the
 * status, which is what turns an invisible failure into a diagnosable one.
 */

type Level = "debug" | "info" | "warn" | "error";

const isDev = process.env.NODE_ENV !== "production";

const LEVEL_ORDER: Record<Level, number> = { debug: 10, info: 20, warn: 30, error: 40 };

function emit(level: Level, message: string, context?: Record<string, unknown>): void {
  if (!isDev && LEVEL_ORDER[level] < LEVEL_ORDER.info) return;

  if (isDev) {
    const suffix = context && Object.keys(context).length ? ` ${JSON.stringify(context)}` : "";
    const fn = level === "error" ? console.error : level === "warn" ? console.warn : console.log;
    fn(`[sutra:${level}] ${message}${suffix}`);
    return;
  }

  // Single-line JSON so the platform's log drain can parse it.
  const sink =
    level === "error" ? console.error : level === "warn" ? console.warn : console.log;
  sink(JSON.stringify({ level, message, ts: new Date().toISOString(), ...context }));
}

export const logger = {
  debug: (message: string, context?: Record<string, unknown>) => emit("debug", message, context),
  info: (message: string, context?: Record<string, unknown>) => emit("info", message, context),
  warn: (message: string, context?: Record<string, unknown>) => emit("warn", message, context),
  error: (message: string, context?: Record<string, unknown>) => emit("error", message, context),
};

/** Log a thrown value with its ApiError metadata, if it has any. */
export function logError(what: string, err: unknown, context?: Record<string, unknown>): void {
  if (err instanceof ApiError) {
    logger.error(what, { endpoint: err.endpoint, status: err.status, code: err.code, ...context });
    return;
  }
  logger.error(what, {
    message: err instanceof Error ? err.message : String(err),
    ...context,
  });
}
