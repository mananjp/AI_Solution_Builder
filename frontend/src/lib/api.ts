import {
  PlanTier,
  BillingUsage,
  CreditTransaction,
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
  OpenCodeChatPayload,
  SocialProvidersResponse,
  AnonymousAuthResponse,
  UpgradeAnonymousPayload,
} from '@/types';

function normalizeApiUrl(url?: string | null): string {
  if (!url) return '';
  return url
    .replace('ai-solution-builder-app.onrender.com', 'ai-solution-builder.onrender.com')
    .replace(/\/+$/, '');
}

const rawApiUrl =
  typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_URL && !process.env.NEXT_PUBLIC_API_URL.startsWith('http://localhost')
      ? normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL)
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
  return localStorage.getItem('access_token');
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

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let response: Response | undefined;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });
  } catch (err) {
    if (
      typeof window !== 'undefined' &&
      API_BASE_URL !== '/api/v1' &&
      !API_BASE_URL.startsWith('/')
    ) {
      try {
        response = await fetch(`/api/v1${endpoint}`, {
          ...options,
          headers,
        });
      } catch {
        // Fallback proxy failed as well
      }
    }

    if (!response) {
      const isNetworkError =
        err instanceof TypeError &&
        (err.message.toLowerCase().includes('fetch') || err.message.toLowerCase().includes('network'));
      if (isNetworkError) {
        throw new Error(
          `Unable to reach backend (${API_BASE_URL}). The backend service may be waking up from idle sleep or BACKEND_URL / NEXT_PUBLIC_API_URL is unconfigured.`
        );
      }
      throw err;
    }
  }

  if (!response.ok) {
    if (response.status === 401) {
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
  getExportUrl(solutionId: string, format: 'json' | 'markdown' | 'zip'): string {
    const token = getAuthToken();
    return `${API_BASE_URL}/export/${solutionId}/${format}${token ? `?token=${token}` : ''}`;
  },

  async downloadExport(solutionId: string, format: 'json' | 'markdown' | 'zip', filename?: string) {
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

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

  async downloadBuild(buildId: string, filename?: string) {
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

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

  async destroy(buildId: string) {
    return request<void>(`/mvp/builds/${buildId}`, {
      method: 'DELETE',
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
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  let response: Response | undefined;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
    });
  } catch (err) {
    if (
      typeof window !== 'undefined' &&
      API_BASE_URL !== '/api/v1' &&
      !API_BASE_URL.startsWith('/')
    ) {
      try {
        response = await fetch(`/api/v1${endpoint}`, {
          method: 'POST',
          headers,
          body: JSON.stringify(payload),
        });
      } catch {
        // Fallback failed
      }
    }
    if (!response) {
      throw err;
    }
  }

  if (!response.ok) {
    throw new Error(`Chat stream failed with status ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No reader available on response');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    let currentEvent = 'message';
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      if (trimmed.startsWith('event:')) {
        currentEvent = trimmed.replace('event:', '').trim();
      } else if (trimmed.startsWith('data:')) {
        const rawData = trimmed.replace('data:', '').trim();
        try {
          const parsed = JSON.parse(rawData);
          if (currentEvent === 'complete') {
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
export const opencodeApi = {
  async health(): Promise<{ healthy: boolean }> {
    return request<{ healthy: boolean }>('/opencode/health');
  },
};

export async function sendOpenCodeChatStream(
  payload: OpenCodeChatPayload,
  handlers: StreamHandlers
) {
  await streamSSE('/opencode/chat', payload, handlers);
}
