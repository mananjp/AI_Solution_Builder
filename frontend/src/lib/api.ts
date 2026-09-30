import {
  PlanTier,
  BillingUsage,
  CreditTransaction,
  CheckoutSession,
  AdminStats,
  AdminUser,
  AuditLogEntry,
  Artifact,
  RecommendedModule,
  User,
  Workspace,
  Solution,
  WorkableField,
  WorkableRecord,
  MVPTemplate,
  MVPBuild,
  MVPBuildPayload,
  MVPQuickBuildPayload,
  MVPDeployPayload,
  MVPDeployResult,
  MVPDeployStatus,
    MVPEnvPlan,
    MVPEnvUpdateResult,
  OpenCodeChatPayload,
  SystemResources,
  MVPChatEditResponse,
  ArtifactExplainability,
} from '@/types';
import { getActiveLanguageCode } from '@/lib/i18n/client';
import { ApiError, codeForStatus, toApiError } from '@/lib/errors';
import { logger, logError } from '@/lib/logger';
import { isAuthBypassed } from '@/lib/auth-bypass';

function normalizeApiUrl(url?: string | null): string {
  if (!url) return '';
  const trimmed = url
    .replace('ai-solution-builder-app.onrender.com', 'ai-solution-builder.onrender.com')
    .replace(/\/+$/, '');
  return trimmed.endsWith('/api/v1') ? trimmed : `${trimmed}/api/v1`;
}

/**
 * Origins a bearer token may be sent to.
 *
 * `getApiBaseUrl()` honours a `custom_backend_url` from localStorage, which the
 * Settings screen writes. The override only trimmed the string and appended
 * `/api/v1`, so any origin could be named — and `request()` then attaches
 * `Authorization: Bearer <access token>` to whatever host came out. That meant a
 * single XSS payload, or one user pasting an attacker's URL, could exfiltrate
 * the session token and defeat the in-memory token storage this app otherwise
 * gets right.
 *
 * So an absolute override must now resolve to an allowed origin. A rejected
 * override falls back to the build-time default rather than failing the request,
 * and the reason is logged.
 */
function allowedApiOrigins(): ReadonlySet<string> {
  const origins = new Set<string>();

  // Same-origin proxy (`/api/v1`) and the page's own origin are always fine.
  if (typeof window !== 'undefined') origins.add(window.location.origin);

  // The build-time URL is operator-controlled, so trust it.
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (configured) {
    try {
      origins.add(new URL(configured).origin);
    } catch {
      // Unparseable build-time value; the default below still applies.
    }
  }

  // Explicit allowlist for anything else, so production hosts do not have to be
  // hard-coded here.
  for (const entry of (process.env.NEXT_PUBLIC_ALLOWED_API_ORIGINS ?? '').split(',')) {
    const value = entry.trim();
    if (value) origins.add(value.replace(/\/+$/, ''));
  }

  // Loopback in any form, for local development and the Capacitor WebView.
  if (process.env.NODE_ENV !== 'production') {
    for (const host of ['localhost', '127.0.0.1', '[::1]']) {
      origins.add(`http://${host}`);
      origins.add(`https://${host}`);
    }
  }

  return origins;
}

/** True when `url` is safe to attach credentials to. */
function isAllowedApiUrl(url: string): boolean {
  // Relative paths stay same-origin and are always allowed.
  if (url.startsWith('/')) return true;

  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }

  // `javascript:` and `data:` URLs parse but must never receive a token.
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false;

  return allowedApiOrigins().has(parsed.origin);
}

export function getApiBaseUrl(): string {
  if (typeof window === 'undefined') {
    return normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1');
  }

  // 1. Check local storage override (allows mobile users / devs to point to custom backend)
  const customUrl = localStorage.getItem('custom_backend_url') || localStorage.getItem('apiBaseUrl()');
  if (customUrl) {
    const normalized = normalizeApiUrl(customUrl);
    if (isAllowedApiUrl(customUrl)) return normalized;
    // Previously any origin was accepted here and the bearer token went with it.
    logger.warn('Ignoring a backend URL that is not on the allow list', {
      requested: customUrl,
    });
  }

  // 2. Check build-time env variable (if it's not a localhost address)
  if (process.env.NEXT_PUBLIC_API_URL && !process.env.NEXT_PUBLIC_API_URL.startsWith('http://localhost')) {
    return normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL);
  }

  // 3. Detect Capacitor native mobile environment (e.g. running on Android WebView)
  const isCapacitorNative =
    'Capacitor' in window ||
    (window.location.protocol === 'https:' && window.location.hostname === 'localhost' && window.location.port === '');
  if (isCapacitorNative) {
    return 'https://ai-solution-builder.onrender.com/api/v1';
  }

  return '/api/v1';
}

/**
 * Resolved per call, never cached at module load.
 *
 * This used to be a module-level `const` built from a duplicated copy of the
 * base-url logic that skipped the localStorage override, while `request()`
 * called the function above. The two could disagree, so a custom backend set
 * in Settings worked for most calls and silently failed for the ~9 raw
 * `fetch()` call sites. Everything now goes through `getApiBaseUrl()`.
 */

export interface RawWorkableEntity {
  name?: string;
  entity_name?: string;
  label?: string;
  table_name?: string;
  fields?: WorkableField[];
  records?: WorkableRecord[];
}

export interface RawWorkableModule {
  id?: string;
  name?: string;
  module_name?: string;
  label?: string;
  path?: string;
  entities?: RawWorkableEntity[];
}

export interface WorkableSystemResponse {
  solution_id: string;
  schema_name: string;
  status: string;
  modules: RawWorkableModule[];
}

// ── Access token ────────────────────────────────────
// The token is never mirrored into localStorage. It used to be, which meant an
// XSS payload could simply read it out, and it went stale the moment Auth0
// renewed the session, leaving the app issuing 401s for a valid user.
//
// Instead the Auth0 SDK owns the token and the API layer asks for a fresh one
// per request. `getAccessTokenSilently` returns from the SDK's in-memory cache
// when the token is still valid, so this costs nothing on the common path and
// only hits the network when a silent renewal is actually due.
// `undefined` is the SDK's "no token" value (`getAccessTokenSilently` resolves
// without a token when there is no session), so it is what this contract uses.
// `getAuthToken` normalises it to `null` for the `if (token)` guards below.
type AccessTokenProvider = () => Promise<string | undefined>;

let tokenProvider: AccessTokenProvider | null = null;

/** Registered by <AuthProvider>; cleared on unmount or logout. */
export function setTokenProvider(provider: AccessTokenProvider | null): void {
  tokenProvider = provider;
}

export async function getAuthToken(): Promise<string | null> {
  if (!tokenProvider) return null;
  try {
    return (await tokenProvider()) ?? null;
  } catch (err) {
    // A renewal failure is not fatal to the call site: the request will 401
    // with a proper ApiError, and the 401 handler drives the re-login. Swallow
    // here so a token problem does not surface as an unrelated network error.
    logError('failed to obtain an access token', err);
    return null;
  }
}

/**
 * Headers for the call sites that must bypass `request()` because they need a
 * blob, a stream or a browser-native navigation rather than parsed JSON.
 */
export async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAuthToken();
  const currentLang = getCurrentLanguage() || getActiveLanguageCode();
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    'X-Content-Language': currentLang,
    'Accept-Language': currentLang,
  };
}

export function getCurrentLanguage(): string {
  if (typeof window === 'undefined') return 'en';
  return localStorage.getItem('sutra.lang') || localStorage.getItem('sutra_lang') || getActiveLanguageCode() || 'en';
}

export function setCurrentLanguage(lang: string) {
  if (typeof window !== 'undefined') {
    localStorage.setItem('sutra.lang', lang);
    localStorage.setItem('sutra_lang', lang);
    try {
      document.documentElement.lang = lang;
    } catch {
      // ignore
    }
  }
}

/** Per-request timeout. Generous, because builds and exports are slow. */
const DEFAULT_TIMEOUT_MS = 60_000;
const RETRYABLE_METHODS = new Set(['GET', 'HEAD']);

/**
 * Core transport.
 *
 * Guarantees, all of which the previous version lacked:
 *  - the request always settles: `AbortSignal.timeout` bounds it instead of
 *    leaving the UI spinning forever on a stalled socket;
 *  - HTTP failures throw `ApiError`, so callers can branch on `status` or
 *    `code` instead of matching on English text;
 *  - a user-supplied `signal` (SSE teardown, unmount) still aborts promptly,
 *    and the two signals are combined rather than overwriting each other;
 *  - idempotent reads retry once on a transport failure, which matters because
 *    the Render free tier sleeps and the first request after a wake always 502s.
 */
async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  // Awaited per call so a renewed token is picked up without a reload. When no
  // provider is registered (SSR, or a build with Auth0 unconfigured) the request
  // still goes out unauthenticated and the backend answers 401, which is a far
  // clearer signal than a client-side throw.
  const token = await getAuthToken();
  const currentLang = getCurrentLanguage() || getActiveLanguageCode();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Content-Language': currentLang,
    'Accept-Language': currentLang,
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Honour a caller-supplied per-request timeout; otherwise use the default.
  // Destructured once so `timeoutMs` is stripped from the `fetch` init (it is
  // not a fetch option) and the same value is not read twice.
  const {
    timeoutMs = DEFAULT_TIMEOUT_MS,
    signal: callerSignal,
    ...init
  } = options as RequestInit & { timeoutMs?: number };

  // `AbortSignal.any` is unavailable on older Safari; fall back to the caller's
  // signal alone, which still aborts, just without the timeout backstop.
  const timeoutSignal =
    typeof AbortSignal.timeout === 'function' ? AbortSignal.timeout(timeoutMs) : undefined;
  const signal =
    callerSignal && timeoutSignal
      ? AbortSignal.any([callerSignal, timeoutSignal])
      : (callerSignal ?? timeoutSignal);

  const baseUrl = getApiBaseUrl();
  const primaryUrl = `${baseUrl}${endpoint}`;
  const urlsToTry: string[] = [primaryUrl];

  if (!primaryUrl.includes('/api/v1')) {
    urlsToTry.push(`${baseUrl}/api/v1${endpoint}`);
  }
  if (typeof window !== 'undefined' && baseUrl !== '/api/v1' && !baseUrl.startsWith('http://localhost') && !baseUrl.startsWith('https://localhost')) {
    urlsToTry.push(`/api/v1${endpoint}`);
  }

  const uniqueUrls = Array.from(new Set(urlsToTry));
  const method = (init.method ?? 'GET').toUpperCase();
  const canRetry = RETRYABLE_METHODS.has(method) && !callerSignal?.aborted;
  const maxAttempts = canRetry ? 2 : 1;

  let lastError: unknown;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    let response: Response | undefined;

    for (let i = 0; i < uniqueUrls.length; i++) {
      const url = uniqueUrls[i];
      try {
        const res = await fetch(url, { ...init, headers, signal });

        if (res.status === 404 && i < uniqueUrls.length - 1) {
          // If the 404 came with an API JSON body (e.g. from FastAPI with detail
          // or error), the backend was reached and explicitly returned an
          // application response. Do not fall back to a frontend route that
          // would mask the true error message.
          const contentType = res.headers.get('content-type') || '';
          if (contentType.includes('application/json')) {
            response = res;
            break;
          }
          continue;
        }
        response = res;
        break;
      } catch (err) {
        // A caller-initiated abort is a decision, not a failure: let it through
        // untouched so the originating code can recognise its own cancellation.
        if (err instanceof DOMException && err.name === 'AbortError' && callerSignal?.aborted) {
          throw new ApiError('Request cancelled', { code: 'CANCELLED', endpoint, cause: err });
        }
        lastError = err;
      }
    }

    if (!response) {
      const isTimeout =
        lastError instanceof DOMException && lastError.name === 'TimeoutError';
      const networkish =
        lastError instanceof TypeError &&
        (lastError.message.toLowerCase().includes('fetch') ||
          lastError.message.toLowerCase().includes('network'));

      if (attempt < maxAttempts) {
        logger.warn('request retrying', { endpoint, attempt, reason: isTimeout ? 'timeout' : 'network' });
        continue;
      }
      if (isTimeout) {
        throw new ApiError(
          `The backend did not respond within ${Math.round(timeoutMs / 1000)}s.`,
          { code: 'TIMEOUT', endpoint, cause: lastError },
        );
      }
      if (networkish) {
        throw new ApiError(
          `Unable to reach backend (${getApiBaseUrl()}). The backend service may be waking up from idle sleep or BACKEND_URL / NEXT_PUBLIC_API_URL is unconfigured.`,
          { code: 'NETWORK', endpoint, cause: lastError },
        );
      }
      throw lastError
        ? toApiError(lastError, endpoint)
        : new ApiError(`Failed to request ${endpoint}`, { code: 'NETWORK', endpoint });
    }

    if (!response.ok) {
      // A 401 means the access token is gone, expired past silent renewal, or
      // was revoked. Clearing the provider forces the next call to go back to
      // Auth0, and a hard navigation is the only way to reliably unwind the
      // signed-in React tree without a full router-aware re-render.
      //
      // Skipped while the auth bypass is on. That build has no real token by
      // design, so every request 401s — and without this the hard navigation
      // threw the user straight back to /login, making the bypass useless even
      // though the route guard was correctly bypassed.
      if (response.status === 401 && !isAuthBypassed) {
        if (token) {
          setTokenProvider(null);
        }
        if (
          typeof window !== 'undefined' &&
          !window.location.pathname.startsWith('/login') &&
          !window.location.pathname.startsWith('/callback')
        ) {
          const returnTo = `${window.location.pathname}${window.location.search}`;
          // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- api layer has no router access
          window.location.href = `/login?returnTo=${encodeURIComponent(returnTo)}`;
        }
      }
      const errorData = await response.json().catch(() => null);
      const message =
        errorData?.error?.message ||
        errorData?.detail ||
        (typeof errorData?.error === 'string' ? errorData.error : null) ||
        `Request failed with status ${response.status}`;

      const error = new ApiError(message, {
        status: response.status,
        code: codeForStatus(response.status),
        details: errorData?.error?.details ?? errorData?.detail,
        endpoint,
      });
      logError('request failed', error);
      throw error;
    }

    if (response.status === 204) {
      return {} as T;
    }

    // A 200 with an unparseable body is a real failure mode (proxy error page,
    // truncated response). Surface it as an ApiError rather than leaking a
    // SyntaxError out of the API layer.
    try {
      return (await response.json()) as T;
    } catch (err) {
      throw new ApiError('The backend returned a malformed response.', {
        status: response.status,
        code: 'SERVER',
        endpoint,
        cause: err,
      });
    }
  }

  throw toApiError(lastError, endpoint);
}

// ── Auth ──────────────────────────────────────────
// No register, login, logout or provider-listing calls here. Those are Auth0's:
// the browser is redirected to Universal Login and comes back holding a token,
// and the session is destroyed by the SDK's logout. The only thing left for the
// API to answer is "who is this, and what may they do".
export const authApi = {
  async me() {
    return request<User>('/auth/me');
  },

  async updateSettings(data: { github_token?: string; render_api_key?: string; vercel_token?: string }) {
    return request<{ updated: boolean }>('/auth/me/settings', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },
};

// ── Workspaces ───────────────────────────────────
export const workspaceApi = {
  async list() {
    return request<Workspace[]>('/workspaces/');
  },

  async create(data: { name: string; description?: string }) {
    return request<Workspace>('/workspaces/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async get(id: string) {
    return request<Workspace>(`/workspaces/${id}`);
  },
};

// ── Solutions ────────────────────────────────────
export const solutionApi = {
  async list(workspaceId: string) {
    return request<Solution[]>(`/solutions/workspace/${workspaceId}`);
  },

  async create(data: { workspace_id: string; title: string; description?: string }) {
    return request<Solution>('/solutions/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async get(id: string) {
    return request<Solution>(`/solutions/${id}`);
  },

  async getDecisions(id: string) {
    return request<{
      solution_id: string;
      title: string;
      total_decisions: number;
      decisions: Record<string, unknown>[];
      assumptions_log: Record<string, unknown>[];
      requirements: Record<string, unknown>[];
    }>(`/solutions/${id}/decisions`);
  },

  async approve(id: string) {
    return request<{
      status: string;
      approval_status: string;
      solution_id: string;
      approved_by: string;
      approved_at: string;
      artifacts_snapshotted: number;
    }>(`/solutions/${id}/approve`, {
      method: 'POST',
    });
  },

  async requestChanges(id: string, comments: string) {
    return request<{
      status: string;
      approval_status: string;
      solution_id: string;
      comments: string;
    }>(`/solutions/${id}/request-changes`, {
      method: 'POST',
      body: JSON.stringify({ comments }),
    });
  },

  async regenerateCascade(
    id: string,
    targets: string[],
    feedback: string = '',
    cascade: boolean = true,
    dryRun: boolean = false
  ) {
    return request<{
      status: string;
      solution_id: string;
      primary_targets: string[];
      affected_artifacts: string[];
      estimated_credits: number;
      cascade: boolean;
    }>(`/solutions/${id}/regenerate`, {
      method: 'POST',
      body: JSON.stringify({ targets, feedback, cascade, dry_run: dryRun }),
    });
  },

  async updateTheme(id: string, theme: Record<string, unknown>) {
    return request<{
      status: string;
      solution_id: string;
      ui_theme: Record<string, unknown>;
    }>(`/solutions/${id}/theme`, {
      method: 'PATCH',
      body: JSON.stringify(theme),
    });
  },

  async delete(id: string) {
    return request<void>(`/solutions/${id}`, {
      method: 'DELETE',
    });
  },
};

// ── Artifacts & Regeneration ─────────────────────
export const artifactApi = {
  async getHistory(solutionId: string, artifactType: string): Promise<Artifact[]> {
    return request<Artifact[]>(`/artifacts/${solutionId}/history/${artifactType}`);
  },

  async regenerate(solutionId: string, artifactType: string, feedback: string) {
    return request<{ status: string; message: string; artifact: Artifact }>('/artifacts/regenerate', {
      method: 'POST',
      body: JSON.stringify({
        solution_id: solutionId,
        artifact_type: artifactType,
        user_feedback: feedback,
      }),
    });
  },

  /**
   * Fetch a generated visual as an object URL.
   *
   * A plain `<img src>` cannot carry the Authorization header these endpoints
   * require, so the bytes are fetched with auth and wrapped in a blob URL. The
   * caller owns the returned URL and must `URL.revokeObjectURL` it.
   */
  async getImageObjectUrl(artifactId: string): Promise<string> {
    const token = await getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${getApiBaseUrl()}/artifacts/${artifactId}/image`, { headers });
    if (!res.ok) throw new Error(`Failed to load image with status ${res.status}`);
    return URL.createObjectURL(await res.blob());
  },

  async explain(
    artifactId: string,
    signal?: AbortSignal
  ): Promise<ArtifactExplainability> {
    return request<ArtifactExplainability>(
      `/artifacts/${artifactId}/explain`,
      { signal }
    );
  },
};

// ── Workable System Runtime ──────────────────────
export const workableApi = {
  async provision(solutionId: string) {
    return request<WorkableSystemResponse>(
      `/workable/${solutionId}/provision`,
      {
        method: 'POST',
        body: JSON.stringify({ solution_id: solutionId }),
      }
    );
  },

  async getModules(solutionId: string) {
    return request<WorkableSystemResponse>(`/workable/${solutionId}/modules`);
  },

  async seedData(solutionId: string, rows: number = 5) {
    return request<{ seeded: number; per_table: number }>(`/workable/${solutionId}/seed?rows=${rows}`, {
      method: 'POST',
    });
  },

  async listRows(solutionId: string, moduleName: string, entityName: string) {
    return request<WorkableRecord[]>(`/workable/${solutionId}/${moduleName}/${entityName}`);
  },

  async createRow(solutionId: string, moduleName: string, entityName: string, data: Record<string, unknown>) {
    return request<WorkableRecord>(`/workable/${solutionId}/${moduleName}/${entityName}`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async deleteRow(solutionId: string, moduleName: string, entityName: string, rowId: string) {
    return request<void>(`/workable/${solutionId}/${moduleName}/${entityName}/${rowId}`, {
      method: 'DELETE',
    });
  },
};

// ── Export Engine ────────────────────────────────
export const exportApi = {
  // Returns a URL without any auth material — the JWT must travel in the
  // Authorization header (downloadExport below) so it never leaks into logs,
  // referrers, or browser history via a ?token= query param.
  getExportUrl(solutionId: string, format: 'json' | 'markdown' | 'zip'): string {
    return `${getApiBaseUrl()}/export/${solutionId}/${format}`;
  },

  async downloadExport(solutionId: string, format: 'json' | 'markdown' | 'zip', filename?: string) {
    const token = await getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    headers['X-Content-Language'] = getActiveLanguageCode();

    const res = await fetch(`${getApiBaseUrl()}/export/${solutionId}/${format}`, { headers });
    if (!res.ok) throw new Error(`Export failed with status ${res.status}`);

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || `solution_export.${format === 'zip' ? 'zip' : format === 'json' ? 'json' : 'md'}`;
    a.click();
    URL.revokeObjectURL(url);
  },
};

// ── OpenCode MVP Builder & Deploy ────────────────
export const mvpApi = {
  async listTemplates(): Promise<MVPTemplate[]> {
    return request<MVPTemplate[]>('/mvp/templates');
  },

  async quickBuild(payload: MVPQuickBuildPayload): Promise<MVPBuild> {
    return request<MVPBuild>('/mvp/quick-build', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async triggerBuild(solutionId: string, payload: MVPBuildPayload = {}): Promise<MVPBuild> {
    return request<MVPBuild>(`/mvp/${solutionId}/build`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async listBuilds(solutionId: string): Promise<MVPBuild[]> {
    return request<MVPBuild[]>(`/mvp/${solutionId}/builds`);
  },

async getStatus(buildId: string): Promise<MVPBuild> {
      return request<MVPBuild>(`/mvp/builds/${buildId}/status`);
    },

    /**
     * Address of the backend-served preview for a build, used when the app has
     * not been deployed yet. Returns a URL rather than fetching, because the
     * sandbox renders it in an iframe and needs the address, not the HTML.
     */
    getPreviewUrl(buildId: string): string {
      return `${getApiBaseUrl()}/mvp/builds/${encodeURIComponent(buildId)}/preview`;
    },

  async getFileContent(
    buildId: string,
    filePath: string,
    signal?: AbortSignal
  ): Promise<string> {
    const token = await getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    
    // Ensure the path does not start with a leading slash to construct the URL correctly
    const cleanPath = filePath.startsWith('/') ? filePath.substring(1) : filePath;
    const res = await fetch(`${getApiBaseUrl()}/mvp/builds/${buildId}/files/${cleanPath}`, {
      headers,
      signal,
    });
    if (!res.ok) throw new Error(`Failed to get file with status ${res.status}`);
    return res.text();
  },

  async downloadBuild(buildId: string, filename?: string) {
    const token = await getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    headers['X-Content-Language'] = getActiveLanguageCode();

    const res = await fetch(`${getApiBaseUrl()}/mvp/builds/${buildId}/download`, { headers });
    if (!res.ok) throw new Error(`Download failed with status ${res.status}`);

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || `mvp_build_${buildId}.zip`;
    a.click();
    URL.revokeObjectURL(url);
  },

  async configure(
    buildId: string,
    data: { app_name?: string; env?: Record<string, unknown> }
  ): Promise<{ applied: Record<string, unknown>; build_id: string }> {
    return request<{ applied: Record<string, unknown>; build_id: string }>(
      `/mvp/builds/${buildId}/configure`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  },

  async deploy(buildId: string, payload: MVPDeployPayload): Promise<MVPDeployResult> {
    return request<MVPDeployResult>(`/mvp/builds/${buildId}/deploy`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

    /** Required/optional env vars the finished build needs (UI-driven deploy prep). */
    async envPlan(buildId: string): Promise<MVPEnvPlan> {
      return request<MVPEnvPlan>(`/mvp/builds/${buildId}/env-plan`);
    },

    /**
     * Edit env vars on an ALREADY-deployed build. Patches the live Render
     * service(s) in place and restarts them, so a rotated secret or a changed
     * DATABASE_URL no longer requires a full redeploy.
     */
    async updateEnv(
      buildId: string,
      data: { env: Record<string, string>; unset?: string[]; restart?: boolean }
    ): Promise<MVPEnvUpdateResult> {
      return request<MVPEnvUpdateResult>(`/mvp/builds/${buildId}/env`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },


  /** Poll actual Render deploy state (never a fake "deployed"). */
  async deployStatus(buildId: string): Promise<MVPDeployStatus> {
    return request<MVPDeployStatus>(`/mvp/builds/${buildId}/deploy/status`);
  },

  async destroy(buildId: string) {
    return request<void>(`/mvp/builds/${buildId}`, {
      method: 'DELETE',
    });
  },

  async chatEdit(buildId: string, message: string, activeFile?: string): Promise<MVPChatEditResponse> {
    return request<MVPChatEditResponse>(`/mvp/builds/${buildId}/edit`, {
      method: 'POST',
      body: JSON.stringify({ message, active_file: activeFile }),
    });
  },

  async destroyPreview(buildId: string): Promise<{ destroyed: boolean; build_id: string }> {
    return request<{ destroyed: boolean; build_id: string }>(
      `/mvp/builds/${buildId}/preview/destroy`,
      {
        method: 'POST',
      }
    );
  },

  async getSpec(
    solutionId: string
  ): Promise<{ app_spec: Record<string, unknown>; cached?: boolean }> {
    return request<{ app_spec: Record<string, unknown>; cached?: boolean }>(
      `/mvp/${solutionId}/spec`
    );
  },

  async generateSpec(
    solutionId: string,
    prompt?: string
  ): Promise<{ app_spec: Record<string, unknown>; cached?: boolean }> {
    return request<{ app_spec: Record<string, unknown>; cached?: boolean }>(
      `/mvp/${solutionId}/spec`,
      {
        method: 'POST',
        body: JSON.stringify({ prompt }),
      }
    );
  },

  async updateSpec(
    solutionId: string,
    spec: Record<string, unknown>
  ): Promise<{ status: string; app_spec: Record<string, unknown> }> {
    return request<{ status: string; app_spec: Record<string, unknown> }>(
      `/mvp/${solutionId}/spec`,
      {
        method: 'PUT',
        body: JSON.stringify({ app_spec: spec }),
      }
    );
  },
};

// ── Billing & Credits ────────────────────────────
export const billingApi = {
  async getPlans(): Promise<PlanTier[]> {
    return request<PlanTier[]>('/billing/plans');
  },

  async getUsage(): Promise<BillingUsage> {
    return request<BillingUsage>('/billing/usage');
  },

  async getTransactions(): Promise<CreditTransaction[]> {
    return request<CreditTransaction[]>('/billing/transactions');
  },

  async topup(amount: number) {
    return request<{ status: string; added: number; message: string }>('/billing/topup', {
      method: 'POST',
      body: JSON.stringify({ amount }),
    });
  },

  async checkout(payload: {
    plan_id?: string;
    pack_credits?: number;
    gateway?: string;
    currency?: string;
  }): Promise<CheckoutSession> {
    return request<CheckoutSession>('/billing/checkout', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};

// ── Admin & Governance ───────────────────────────
export const adminApi = {
  async getStats(): Promise<AdminStats> {
    return request<AdminStats>('/admin/stats');
  },

  async getUsers(): Promise<AdminUser[]> {
    return request<AdminUser[]>('/admin/users');
  },

  async getAuditLogs(): Promise<AuditLogEntry[]> {
    return request<AuditLogEntry[]>('/admin/audit-logs');
  },
};

// ── Upload ───────────────────────────────────────
export const uploadApi = {
  async uploadFile(file: File): Promise<{ filename: string; text: string; size: number }> {
    const token = await getAuthToken();
    const formData = new FormData();
    formData.append('file', file);

    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    headers['X-Content-Language'] = getActiveLanguageCode();

    const response = await fetch(`${getApiBaseUrl()}/upload/document`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Upload failed' }));
      const message =
        err.error?.message ?? err.detail ?? (typeof err === 'string' ? err : 'Upload failed');
      throw new Error(message);
    }

    const data = await response.json();
    return {
      filename: data.filename ?? file.name,
      text: data.extracted_text ?? '',
      size: data.size_bytes ?? file.size,
    };
  },

  async parseUrl(url: string): Promise<{ url: string; extractedText: string; characterCount: number }> {
    const token = await getAuthToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    headers['X-Content-Language'] = getActiveLanguageCode();

    const response = await fetch(`${getApiBaseUrl()}/upload/url`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ url }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Failed to parse URL' }));
      const message =
        err.error?.message ?? err.detail ?? 'Failed to parse URL';
      throw new Error(message);
    }

    const data = await response.json();
    return {
      url: data.url,
      extractedText: data.extracted_text,
      characterCount: data.character_count,
    };
  },

  async uploadAudio(
    audioBlob: Blob,
    filename: string = 'voice_recording.webm',
    language?: string
  ): Promise<{
    filename: string;
    transcription: string;
    detected_language: string;
    character_count: number;
  }> {
    const token = await getAuthToken();
    const currentLang = language || getCurrentLanguage();
    const formData = new FormData();
    formData.append('file', audioBlob, filename);
    if (currentLang && currentLang !== 'auto') {
      formData.append('language', currentLang);
    }

    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (currentLang) {
      headers['X-Content-Language'] = currentLang;
      headers['Accept-Language'] = currentLang;
    }

    const response = await fetch(`${getApiBaseUrl()}/upload/audio`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Audio upload failed' }));
      const message =
        err.error?.message ?? err.detail ?? (typeof err === 'string' ? err : 'Audio upload failed');
      throw new Error(message);
    }

    return response.json();
  },
};

// ── Chat & Agent Streaming ───────────────────────
export interface ChatStreamEvent {
  agent?: string;
  type?: string;
  message?: string;
  status?: string;
  recommendations?: Array<RecommendedModule | string>;
  detail?: string;
  raw?: string;
  [key: string]: unknown;
}

export interface StreamHandlers {
  onEvent?: (event: string, data: ChatStreamEvent) => void;
  onError?: (err: unknown) => void;
  onComplete?: (data: ChatStreamEvent) => void;
}

async function streamSSE(
  endpoint: string,
  payload: object,
  handlers: StreamHandlers
) {
  const token = await getAuthToken();
  const currentLang = getCurrentLanguage() || getActiveLanguageCode();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Content-Language': currentLang,
    'Accept-Language': currentLang,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const baseUrl = getApiBaseUrl();
  const primaryUrl = `${baseUrl}${endpoint}`;
  const urlsToTry: string[] = [primaryUrl];

  if (!primaryUrl.includes('/api/v1')) {
    urlsToTry.push(`${baseUrl}/api/v1${endpoint}`);
  }
  if (typeof window !== 'undefined') {
    if (baseUrl !== '/api/v1' && !baseUrl.startsWith('http://localhost') && !baseUrl.startsWith('https://localhost')) {
      urlsToTry.push(`/api/v1${endpoint}`);
    }
    urlsToTry.push(endpoint);
  }

  const uniqueUrls = Array.from(new Set(urlsToTry));
  let response: Response | undefined;
  let lastError: Error | undefined;

  for (let i = 0; i < uniqueUrls.length; i++) {
    const url = uniqueUrls[i];
    try {
      const res = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      if (res.status === 404 && i < uniqueUrls.length - 1) {
        continue;
      }

      if (!res.ok) {
        const errorData = await res.json().catch(() => null);
        const msg =
          errorData?.error?.message ||
          errorData?.detail ||
          (typeof errorData?.error === 'string' ? errorData.error : null) ||
          `Chat stream failed with status ${res.status}`;
        throw new Error(msg);
      }

      response = res;
      break;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (i === uniqueUrls.length - 1) {
        throw lastError;
      }
    }
  }

  if (!response) {
    throw lastError || new Error('Failed to connect to chat stream');
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No reader available on response');

  const decoder = new TextDecoder();
  let buffer = '';
  let completed = false;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    let currentEvent = 'message';
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith(':')) continue;

      if (trimmed.startsWith('event:')) {
        currentEvent = trimmed.replace('event:', '').trim();
      } else if (trimmed.startsWith('data:')) {
        const rawData = trimmed.replace('data:', '').trim();
        try {
          const parsed = JSON.parse(rawData);
          if (currentEvent === 'complete') {
            completed = true;
            handlers.onComplete?.(parsed);
          } else if (currentEvent === 'error') {
            handlers.onError?.(parsed);
          } else {
            handlers.onEvent?.(currentEvent, parsed);
          }
        } catch {
          handlers.onEvent?.(currentEvent, { raw: rawData });
        }
      }
    }
  }

  // EOF without an explicit `complete` event (truncated/keep-alive stream):
  // still signal completion with the last-known data so handlers can render.
  if (!completed) {
    handlers.onComplete?.({});
  }
}

export async function sendChatMessageStream(
  payload: { solution_id: string; message: string; uploaded_context?: string },
  handlers: StreamHandlers
) {
  await streamSSE('/chat/send', payload, handlers);
}

export async function confirmRecommendationsStream(
  payload: { solution_id: string; accepted_modules: string[] },
  handlers: StreamHandlers
) {
  await streamSSE('/chat/confirm-recommendations', payload, handlers);
}

// ── OpenCode API (Custom App Builder path) ───────
export interface EngineHealth {
  healthy: boolean;
  sidecar_healthy: boolean;
  mode: 'opencode-sidecar' | 'integrated-synthesizer';
  version?: string;
  model?: string;
  latency_ms?: number;
}

export interface DiagnoseCheck {
  status: 'ok' | 'warn' | 'fail';
  label: string;
  detail: string;
  fix: string | null;
}

export interface OpenCodeDiagnosis {
  ok: boolean;
  model?: string;
  version?: string;
  checks: DiagnoseCheck[];
}

export const opencodeApi = {
  async health(): Promise<EngineHealth> {
    return request<EngineHealth>('/opencode/health');
  },
  async diagnose(): Promise<OpenCodeDiagnosis> {
    return request<OpenCodeDiagnosis>('/opencode/diagnose');
  },
};

export async function sendOpenCodeChatStream(
  payload: OpenCodeChatPayload,
  handlers: StreamHandlers
) {
  await streamSSE('/opencode/chat', payload, handlers);
}

export interface SandboxChatMessage {
  role: string;
  content: string;
}

export async function sendSandboxChatStream(
  buildId: string,
  payload: { message: string; history?: SandboxChatMessage[] },
  handlers: StreamHandlers
) {
  await streamSSE(`/mvp/builds/${buildId}/sandbox/chat`, payload, handlers);
}

// ── System Resources (live CPU / memory / disk observability) ──────
export const systemApi = {
  async resources(): Promise<SystemResources> {
    return request<SystemResources>('/system/resources');
  },
};

// ── Legacy Repository Modernization API ───────────────────────────
export interface LegacyRepoAnalysis {
  root_path: string;
  project_name: string;
  structure: {
    total_files: number;
    total_directories: number;
    manifests: string[];
    configs: string[];
    docs: string[];
    tests: string[];
    sample_files: string[];
  };
  technology_stack: {
    languages: string[];
    frontend_framework: string | null;
    backend_framework: string | null;
    database: string | null;
    orm: string | null;
    auth: string | null;
    api_style: string;
    styling: string | null;
    state_management: string | null;
    build_tools: string[];
    package_manager: string | null;
    manifest_dependencies: Record<string, Record<string, string>>;
  };
  entry_points: {
    frontend_entry: string | null;
    backend_entry: string | null;
    routing_files: string[];
    database_schemas: string[];
    env_files: string[];
  };
  architecture: {
    topology: string;
    data_flow: string;
    frontend_present: boolean;
    backend_present: boolean;
    database_present: boolean;
    auth_present: boolean;
  };
  assets_inventory: {
    total_assets: number;
    logos: string[];
    icons: string[];
    images: string[];
    fonts: string[];
    media: string[];
    reusable_message: string;
  };
  technical_debt: {
    outdated_dependencies: Array<{ package: string; current_version: string; reason: string }>;
    legacy_patterns: Array<{ file: string; type: string; recommendation: string }>;
    security_findings: Array<{ file: string; type: string; recommendation: string }>;
    missing_infrastructure: string[];
  };
  reusable_elements: {
    reusable_assets_count: number;
    reusable_branding: string[];
    reusable_configs: string[];
    existing_tests: string[];
    reusable_models: string[];
    preservation_policy: string;
  };
  modernization_plan: Array<{
    phase: number;
    title: string;
    goal: string;
    actions: string[];
    safety_level: string;
  }>;
}

export interface CredentialValidationResult {
  key_name: string;
  format_valid: boolean;
  connection_tested: boolean;
  connection_success: boolean;
  message: string;
  masked_key: string;
}

export interface ModernizeReport {
  status: string;
  build_id: string;
  target_repository: string;
  detected_stack: {
    languages: string[];
    frontend: string;
    backend: string;
    database: string;
    styling: string;
  };
  credentials_configured: Record<string, string>;
  modified_files: string[];
  modernized: string[];
  added_features: string[];
  preserved_features: string[];
  validation: {
    all_passed: boolean;
    existing_features_intact: boolean;
    new_features_verified: boolean;
    security_hygiene_passed: boolean;
    checks: Array<{ name: string; passed: boolean; details: string }>;
    repairs_executed: Array<{ turn: number; fix: string }>;
  };
  schedule_summary: {
    total_tasks: number;
    completed: number;
    failed: number;
    timeline_events: number;
  };
  sutra_os: string;
  git: {
    status: string;
    commit: string;
    push: string;
    deployment: string;
  };
  zip_size_bytes: number;
}

export const legacyRepoApi = {
  async analyze(payload: { local_path?: string; github_repo_url?: string; github_token?: string }): Promise<LegacyRepoAnalysis> {
    return request<LegacyRepoAnalysis>('/legacy-repo/analyze', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async analyzeUpload(file: File): Promise<LegacyRepoAnalysis> {
    const formData = new FormData();
    formData.append('file', file);
    const token = await getAuthToken();
    const res = await fetch(`${getApiBaseUrl()}/legacy-repo/analyze-upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
    if (!res.ok) {
      if (res.status === 401) {
        throw new Error('Your session has expired or you are not logged in. Please log in to inspect repositories.');
      }
      const err = await res.json().catch(() => ({ detail: 'Upload analysis failed' }));
      throw new Error(err.error?.message || err.detail || 'Upload analysis failed');
    }
    return res.json();
  },

  async validateCredential(key_name: string, key_value: string): Promise<CredentialValidationResult> {
    return request<CredentialValidationResult>('/legacy-repo/validate-credentials', {
      method: 'POST',
      body: JSON.stringify({ key_name, key_value }),
    });
  },

  async modernize(payload: {
    local_path?: string;
    github_repo_url?: string;
    github_token?: string;
    requested_features?: string[];
    credentials?: Record<string, string>;
  }): Promise<ModernizeReport> {
    return request<ModernizeReport>('/legacy-repo/modernize', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  getDownloadUrl(buildId: string): string {
    return `${getApiBaseUrl()}/legacy-repo/download/${buildId}`;
  },
};

export interface SecurityScanItem {
  id: string;
  sha256?: string;
  url?: string;
  target: string;
  source: string;
  verdict: 'clean' | 'suspicious' | 'malicious' | 'unknown' | 'error' | 'skipped';
  findings: Array<{
    source: string;
    verdict: string;
    reason: string;
    detail: Record<string, unknown>;
  }>;
  scanned_bytes: number;
  from_cache: boolean;
  user_id?: string;
  duration_ms: number;
  created_at?: string;
}

export interface SecurityStats {
  total_scans: number;
  cache_hits: number;
  cache_hit_rate: number;
  total_bytes_scanned: number;
  verdict_breakdown: Record<string, number>;
  source_breakdown: Record<string, number>;
}

export interface SecurityConfig {
  security_scan_enabled: boolean;
  block_threshold: string;
  fail_unavailable_mode: string;
  scan_sources: string;
  archive_limits: {
    max_entries: number;
    max_uncompressed_bytes: number;
    max_ratio: number;
    max_nested_depth: number;
  };
  layers: {
    layer_0_local_rules: { configured: boolean; live: boolean };
    layer_1_clamav: { configured: boolean; live: boolean; host?: string; port?: number };
    layer_2_virustotal: {
      configured: boolean;
      acknowledged_tos: boolean;
      live: boolean;
      api_key_configured: boolean;
      api_key_masked?: string;
      rpm_limit: number;
      daily_limit: number;
    };
  };
}

export const securityApi = {
  async getScans(params?: { verdict?: string; source?: string; limit?: number; offset?: number }) {
    const qs = new URLSearchParams();
    if (params?.verdict) qs.set('verdict', params.verdict);
    if (params?.source) qs.set('source', params.source);
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    const queryStr = qs.toString();
    return request<{ total: number; offset: number; limit: number; items: SecurityScanItem[] }>(
      `/security/scans${queryStr ? `?${queryStr}` : ''}`
    );
  },

  async getStats(): Promise<SecurityStats> {
    return request<SecurityStats>('/security/stats');
  },

  async getConfig(): Promise<SecurityConfig> {
    return request<SecurityConfig>('/security/config');
  },

  async scanFile(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const token = await getAuthToken();
    const res = await fetch(`${getApiBaseUrl()}/security/scan/file`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Scan failed' }));
      throw new Error(err.error?.message || err.detail || 'Scan failed');
    }
    return res.json();
  },
};

