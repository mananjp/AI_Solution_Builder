export interface User {
  id: string;
  email: string;
  full_name?: string;
  role: string;
  org_id: string;
  settings?: Record<string, unknown>;
  created_at: string;
}

export interface Workspace {
  id: string;
  org_id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at?: string;
}

export type ArtifactType = 
  | 'hld'
  | 'lld'
  | 'wireframe'
  | 'er_diagram'
  | 'database_schema'
  | 'api_spec'
  | 'roadmap'
  | 'bpmn'
  | 'workable';

export interface Artifact {
  id: string;
  solution_id: string;
  artifact_type: ArtifactType;
  title: string;
  content: Record<string, unknown>;
  content_text?: string;
  version: number;
  created_at: string;
}

export interface Solution {
  id: string;
  workspace_id: string;
  title: string;
  description?: string;
  status: 'discovery' | 'analyzing' | 'recommending' | 'generating' | 'complete' | 'failed';
  ai_state?: Record<string, unknown>;
  conversation_history?: Array<{
    role: 'user' | 'assistant' | 'system';
    content: string;
  }>;
  artifacts?: Artifact[];
  created_at: string;
  updated_at?: string;
}

export interface RecommendedModule {
  id?: string;
  name: string;
  category?: string;
  description: string;
  features: string[];
  complexity?: 'Low' | 'Medium' | 'High';
  priority?: 'Must Have' | 'Should Have' | 'Nice to Have';
}

export interface AgentEventMessage {
  agent: string;
  type: string;
  message?: string;
  data?: unknown;
}

// ── BPMN Process Types ────────────────────────────
export interface BpmnNode {
  id: string;
  type: 'start' | 'task' | 'gateway' | 'end' | 'service';
  label: string;
  actor: string;
  description?: string;
  isBottleneck?: boolean;
}

export interface BpmnConnection {
  from: string;
  to: string;
  label?: string;
}

export interface BpmnProcess {
  processName: string;
  swimlanes: string[];
  nodes: BpmnNode[];
  connections: BpmnConnection[];
  bottlenecks?: string[];
}

// ── Workable System Runtime Types ────────────────
export interface WorkableField {
  name: string;
  type: string;
  required?: boolean;
  unique?: boolean;
  default?: unknown;
}

export type WorkableRecord = Record<string, unknown> & { id: string };

export interface WorkableEntity {
  name: string;
  label: string;
  table_name: string;
  fields: WorkableField[];
  records?: WorkableRecord[];
}

export interface WorkableModule {
  id: string;
  name: string;
  label: string;
  entities: WorkableEntity[];
}

// ── Billing & Metering Types ─────────────────────
export interface PlanTier {
  id: string;
  name: string;
  price_usd: number;
  monthly_credits: number;
  max_workable_systems: number;
  features: string[];
}

export interface BillingUsage {
  org_id: string;
  plan_name: string;
  monthly_limit: number;
  current_balance: number;
  credits_used: number;
}

export interface CreditTransaction {
  id: string;
  amount: number;
  action: string;
  description: string;
  created_at: string;
}

// ── Admin & Governance Types ─────────────────────
export interface AdminStats {
  total_users: number;
  total_organizations: number;
  total_solutions: number;
  total_workspaces: number;
  active_llm_model: string;
  system_status: string;
  total_ai_credits_consumed: number;
  average_generation_time_sec: number;
}

export interface AdminUser {
  id: string;
  email: string;
  full_name?: string;
  role: string;
  org_id?: string;
  org_name?: string;
  created_at: string;
}

export interface AuditLogEntry {
  id: string;
  org_id: string;
  action: string;
  description: string;
  amount: number;
  timestamp: string;
  status: string;
}

// ── OpenCode MVP Builder & Deploy Types ─────────
export interface MVPTemplate {
  slug: string;
  title: string;
  description: string;
  app_name: string;
  industry: string;
}

export interface MVPFileEntry {
  path: string;
  size: number;
  is_dir: boolean;
}

export type MVPBuildStatus =
  | 'pending'
  | 'building'
  | 'complete'
  | 'failed'
  | 'cancelled';

export interface MVPBuild {
  build_id: string;
  solution_id: string;
  build_number: number;
  status: MVPBuildStatus;
  workspace_path: string;
  file_count: number;
  error_message?: string | null;
  repo_url?: string | null;
  files?: MVPFileEntry[];
}

export interface MVPBuildPayload {
  app_name?: string;
  template?: string;
  config?: Record<string, unknown>;
  force?: boolean;
}

export interface MVPDeployPayload {
  repo_name: string;
  description?: string;
  private?: boolean;
  force?: boolean;
}

export interface MVPDeployResult {
  repo_url: string;
  clone_url: string;
  branch: string;
  file_count: number;
  render_blueprint: string;
}
