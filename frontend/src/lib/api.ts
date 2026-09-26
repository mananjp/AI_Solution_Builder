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
  OpenCodeChatPayload,
  SystemResources,
  SocialProvidersResponse,
  AnonymousAuthResponse,
  UpgradeAnonymousPayload,
  MVPChatEditResponse,
} from '@/types';
import { getActiveLanguageCode } from '@/lib/i18n/client';

function normalizeApiUrl(url?: string | null): string {
  if (!url) return '';
  const trimmed = url
    .replace('ai-solution-builder-app.onrender.com', 'ai-solution-builder.onrender.com')
    .replace(/\/+$/, '');
  return trimmed.endsWith('/api/v1') ? trimmed : `${trimmed}/api/v1`;
}


export function getApiBaseUrl(): string {
  if (typeof window === 'undefined') {
    return normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1');
  }

  // 1. Check local storage override (allows mobile users / devs to point to custom backend)
  const customUrl = localStorage.getItem('custom_backend_url') || localStorage.getItem('api_base_url');
  if (customUrl) return normalizeApiUrl(customUrl);

  // 2. Check build-time env variable (if it's not a localhost address)
  if (process.env.NEXT_PUBLIC_API_URL && !process.env.NEXT_PUBLIC_API_URL.startsWith('http://localhost')) {
    return normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL);
  }

  // 3. Detect Capacitor native mobile environment (e.g. running on Android WebView)
  const isCapacitorNative =
    (window as any).Capacitor !== undefined ||
    (window.location.protocol === 'https:' && window.location.hostname === 'localhost' && window.location.port === '');
  if (isCapacitorNative) {
    return 'https://ai-solution-builder.onrender.com/api/v1';
  }

  return '/api/v1';
}

const rawApiUrl =
  typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_URL && !process.env.NEXT_PUBLIC_API_URL.startsWith('http://localhost')
      ? normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL)
      : (typeof window !== 'undefined' && ((window as any).Capacitor !== undefined || (window.location.protocol === 'https:' && window.location.hostname === 'localhost' && window.location.port === '')))
      ? 'https://ai-solution-builder.onrender.com/api/v1'
      : '/api/v1')
    : normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1');

const API_BASE_URL = rawApiUrl;

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

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token') || localStorage.getItem('token');
}

export function setAuthToken(token: string) {
  if (typeof window !== 'undefined') {
    localStorage.setItem('access_token', token);
  }
}

export function removeAuthToken() {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('access_token');
    localStorage.removeItem('demo_session');
  }
}

/**
 * Write a client-side-only demo session so the app can be explored
 * fully offline without a running backend.
 */
export function setDemoSession() {
  if (typeof window !== 'undefined') {
    localStorage.setItem('demo_session', 'true');
    // Use a synthetic token so API calls include an Authorization header
    // (they'll still fail at the network level, but the app has
    // extensive mock-data fallbacks for every route).
    localStorage.setItem('access_token', 'DEMO_SESSION');
  }
}

export function isDemoSession(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem('demo_session') === 'true';
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

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
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
  let response: Response | undefined;
  let lastError: unknown;

  for (let i = 0; i < uniqueUrls.length; i++) {
    const url = uniqueUrls[i];
    try {
      const res = await fetch(url, {
        ...options,
        headers,
      });

      if (res.status === 404 && i < uniqueUrls.length - 1) {
        // If the 404 came with an API JSON body (e.g. from FastAPI with detail or error),
        // the backend was reached and explicitly returned an application response.
        // Do not fallback to a frontend route that will mask the true error message.
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
      lastError = err;
    }
  }

  if (!response) {
    const isNetworkError =
      lastError instanceof TypeError &&
      (lastError.message.toLowerCase().includes('fetch') || lastError.message.toLowerCase().includes('network'));
    if (isNetworkError) {
      throw new Error(
        `Unable to reach backend (${API_BASE_URL}). The backend service may be waking up from idle sleep or BACKEND_URL / NEXT_PUBLIC_API_URL is unconfigured.`
      );
    }
    throw lastError || new Error(`Failed to request ${endpoint}`);
  }

  if (!response.ok) {
    // Treat a 401 as a session problem only for real sessions — a demo session
    // must not be torn down or hard-redirected mid-flow.
    if (response.status === 401 && !isDemoSession()) {
      removeAuthToken();
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- api layer has no router access
        window.location.href = '/login';
      }
    }
    const errorData = await response.json().catch(() => null);
    const message =
      errorData?.error?.message ||
      errorData?.detail ||
      (typeof errorData?.error === 'string' ? errorData.error : null) ||
      `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// ── Auth ──────────────────────────────────────────
export const authApi = {
  async register(data: { email: string; password: string; org_name: string; full_name?: string }) {
    const res = await request<{ access_token: string; token_type: string }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    setAuthToken(res.access_token);
    return res;
  },

  async login(data: { email: string; password: string }) {
    const res = await request<{ access_token: string; token_type: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    setAuthToken(res.access_token);
    return res;
  },

  async me() {
    return request<User>('/auth/me');
  },

  async getProviders() {
    return request<SocialProvidersResponse>('/auth/providers');
  },

  async anonymousLogin() {
    const res = await request<AnonymousAuthResponse>('/auth/anonymous', {
      method: 'POST',
    });
    setAuthToken(res.access_token);
    return res;
  },

  async upgradeAnonymous(data: UpgradeAnonymousPayload) {
    return request<User>('/auth/upgrade-anonymous', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getOAuthAuthorizeUrl(provider: 'github' | 'google') {
    return request<{ authorization_url: string }>(`/auth/oauth/${provider}/authorize`);
  },

  async updateSettings(data: { github_token?: string; render_api_key?: string }) {
    return request<{ updated: boolean }>('/auth/me/settings', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  logout() {
    removeAuthToken();
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
    return `${API_BASE_URL}/export/${solutionId}/${format}`;
  },

  async downloadExport(solutionId: string, format: 'json' | 'markdown' | 'zip', filename?: string) {
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    headers['X-Content-Language'] = getActiveLanguageCode();

    const res = await fetch(`${API_BASE_URL}/export/${solutionId}/${format}`, { headers });
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

  async getFileContent(buildId: string, filePath: string): Promise<string> {
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    
    // Ensure the path does not start with a leading slash to construct the URL correctly
    const cleanPath = filePath.startsWith('/') ? filePath.substring(1) : filePath;
    const res = await fetch(`${API_BASE_URL}/mvp/builds/${buildId}/files/${cleanPath}`, { headers });
    if (!res.ok) throw new Error(`Failed to get file with status ${res.status}`);
    return res.text();
  },

  async downloadBuild(buildId: string, filename?: string) {
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    headers['X-Content-Language'] = getActiveLanguageCode();

    const res = await fetch(`${API_BASE_URL}/mvp/builds/${buildId}/download`, { headers });
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

  getPreviewUrl(buildId: string): string {
    return `${API_BASE_URL}/mvp/builds/${buildId}/preview`;
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
    const token = getAuthToken();
    const formData = new FormData();
    formData.append('file', file);

    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    headers['X-Content-Language'] = getActiveLanguageCode();

    const response = await fetch(`${API_BASE_URL}/upload/document`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(err.detail || 'Upload failed');
    }

    const data = await response.json();
    return {
      filename: data.filename ?? file.name,
      text: data.extracted_text ?? '',
      size: data.size_bytes ?? file.size,
    };
  },

  async parseUrl(url: string): Promise<{ url: string; extractedText: string; characterCount: number }> {
    const token = getAuthToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    headers['X-Content-Language'] = getActiveLanguageCode();

    const response = await fetch(`${API_BASE_URL}/upload/url`, {
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
    const token = getAuthToken();
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

    const response = await fetch(`${API_BASE_URL}/upload/audio`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'Audio upload failed' }));
      throw new Error(err.detail || 'Audio upload failed');
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
  const token = getAuthToken();
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
    const token = getAuthToken();
    const res = await fetch(`${API_BASE_URL}/legacy-repo/analyze-upload`, {
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
    return `${API_BASE_URL}/legacy-repo/download/${buildId}`;
  },
};

