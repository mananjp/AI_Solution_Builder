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
  MVPDeployPayload,
  MVPDeployResult,
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

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
  }
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

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Network request failed' }));
    throw new Error(errorData.detail || `Request failed with status ${response.status}`);
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

export async function sendChatMessageStream(
  payload: { solution_id: string; message: string; uploaded_context?: string },
  handlers: StreamHandlers
) {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}/chat/send`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

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

export async function confirmRecommendationsStream(
  payload: { solution_id: string; accepted_modules: string[] },
  handlers: StreamHandlers
) {
  const token = getAuthToken();
  const response = await fetch(`${API_BASE_URL}/chat/confirm-recommendations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Recommendation confirmation failed with status ${response.status}`);
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
