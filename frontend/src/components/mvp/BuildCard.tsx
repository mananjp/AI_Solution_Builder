'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Check,
  CheckCircle2,
  Code2,
  Download,
  ExternalLink,
  FolderTree,
  Globe,
  Info,
  KeyRound,
  Loader2,
  PowerOff,
  Rocket,
  Server,
  Settings2,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import { mvpApi } from '@/lib/api';

/** Relative time for a build card, falling back to an absolute date. */
function formatBuildTime(iso?: string | null): string {
  if (!iso) return 'Time unavailable';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Time unavailable';

  const secs = Math.floor((Date.now() - d.getTime()) / 1000);
  if (secs < 0) return d.toLocaleString();
  if (secs < 60) return 'Just now';
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString();
}

import {
  BuildStep,
  MVPBuild,
  MVPBuildStatus,
  MVPDeployResult,
  MVPDeployStatus,
  MVPEnvPlan,
  MVPEnvVarSpec,
} from '@/types';
import { ResourceGauges } from '@/components/mvp/ResourceGauges';
import { ProgressStepper } from '@/components/lab/progress-stepper';
import { TreeView, type TreeNode } from '@/components/lab/tree-view';

import { Badge, type BadgeProps } from '@/components/ui/badge';

import { Button } from '@/components/ui/button';

export const STATUS_STYLES: Record<MVPBuildStatus, BadgeProps['variant']> = {
  queued: 'warning',
  pending: 'warning',
  building: 'info',
  complete: 'success',
  failed: 'destructive',
  cancelled: 'neutral',
};

export function StatusBadge({ status }: { status: MVPBuildStatus }) {
  return (
    <Badge
      variant={STATUS_STYLES[status]}
      className={status === 'building' ? 'animate-pulse' : undefined}
    >
      {status}
    </Badge>
  );
}


// Fallback only. The backend owns the canonical milestone list
// (``_CHAT_BUILD_STEPS``) and ships it on every progress payload, so anything it
// provides is used verbatim — hard-coding a second list here silently dropped
// milestones it didn't know about.
export const PROGRESS_STEPS: BuildStep[] = [
  { key: 'analyzing', label: 'Synthesizing architecture & specs', status: 'pending' },
  { key: 'scaffolding', label: 'Scaffolding full-stack codebase', status: 'pending' },
  { key: 'coding', label: 'Generating models, APIs & UI', status: 'pending' },
  { key: 'verifying', label: 'Verifying & repairing code', status: 'pending' },
  { key: 'packaging', label: 'Packaging artifact', status: 'pending' },
];

function useBuildSteps(build: MVPBuild): BuildStep[] {
  return useMemo(() => {
    const incoming = build.progress?.steps;
    if (Array.isArray(incoming) && incoming.length > 0) {
      return incoming.map((s, i) => ({
        key: s.key || `step-${i}`,
        label: s.label || s.key || `Step ${i + 1}`,
        status: s.status || 'pending',
      }));
    }
    const pct = build.progress?.percentage;
    const activeIdx =
      pct == null ? -1 : pct >= 95 ? 4 : pct >= 60 ? 2 : pct >= 40 ? 1 : pct >= 10 ? 0 : -1;
    return PROGRESS_STEPS.map((step, i) => ({
      ...step,
      status: i < activeIdx ? 'completed' : i === activeIdx ? 'active' : 'pending',
    }));
  }, [build.progress?.steps, build.progress?.percentage]);
}

function BuildStepList({ build }: { build: MVPBuild }) {
  const steps = useBuildSteps(build);
  // The stepper takes an index into a list of labels, so completed steps become
  // the count of finished milestones and the active one is the next index.
  // A build with no active step (not started, or finished) parks on the first
  // and last index respectively, which is where the marker belongs.
  const activeIndex = steps.findIndex((step) => step.status === 'active');
  const completedCount = steps.filter((step) => step.status === 'completed').length;
  const current =
    build.status === 'complete'
      ? steps.length - 1
      : activeIndex === -1
        ? completedCount > 0
          ? completedCount
          : 0
        : activeIndex;

  return (
    <ProgressStepper
      steps={steps.map((step) => step.label)}
      current={current}
      label="Build progress"
    />
  );
}

function FileTree({ build }: { build: MVPBuild }) {
  const [open, setOpen] = useState(false);
  const files = build.files || [];

  return (
    <div className="pt-3 border-t border-[var(--border)] mt-3">
      <Button variant="ghost" size="default"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-[11px] uppercase tracking-widest font-bold text-[var(--text-3)] hover:text-[var(--sutra-ink)] transition-colors"
      >
        <FolderTree className="w-3.5 h-3.5 text-[var(--sutra-ink)]" />
        <span>Generated Files ({build.file_count})</span>
        <span className="text-[var(--sutra-strong)] font-mono">{open ? '▾' : '▸'}</span>
      </Button>
      {open && (
        <div className="mt-3 max-h-64 overflow-y-auto overflow-x-hidden rounded-sm bg-[var(--bg-2)] border border-[var(--border)] p-2 shadow-inner">
          {files.length === 0 ? (
            <p className="p-2 text-[11px] text-[var(--text-3)] font-mono">No file tree returned yet.</p>
          ) : (
            <TreeView nodes={toTreeNodes(files)} label="Generated files" />
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Folds the backend's flat `path` list into the tree the view expects.
 *
 * The backend reports every entry separately and marks directories, but it does
 * not guarantee parents arrive before their children, so this is a single
 * folding pass rather than an incremental walk: a file whose parent is absent
 * from the payload is attached at the root instead of being dropped.
 */
function toTreeNodes(files: { path: string; is_dir?: boolean }[]): TreeNode[] {
  const root: TreeNode[] = [];
  const index = new Map<string, TreeNode>();

  for (const file of files) {
    const parts = file.path.split('/').filter(Boolean);
    if (parts.length === 0) continue;

    let siblings = root;
    let walked = '';

    parts.forEach((part, i) => {
      walked = walked ? `${walked}/${part}` : part;
      const existing = index.get(walked);
      if (existing) {
        // A directory seen first, then its own entry, must not become a leaf.
        if (file.is_dir && !existing.children) existing.children = [];
        if (i < parts.length - 1 && !existing.children) existing.children = [];
        siblings = existing.children as TreeNode[];
        return;
      }
      const node: TreeNode = { name: part };
      if (i < parts.length - 1 || file.is_dir) node.children = [];
      index.set(walked, node);
      siblings.push(node);
      siblings = node.children as TreeNode[];
    });
  }

  return root;
}

const DEPLOY_STEP_LABELS: Record<string, string> = {
  web: 'Unified Web App (FastAPI + Next.js)',
  database: 'Managed PostgreSQL Database (Render)',
  backend: 'Backend API service',
  frontend: 'Frontend app (links to backend URL)',
};

function EnvChip({ spec, value, onChange }: { spec: MVPEnvVarSpec; value: string; onChange: (v: string) => void }) {
  const [showOverride, setShowOverride] = useState(Boolean(value));
  const isDatabase = spec.key === 'DATABASE_URL';

  return (
    <div className={`p-3 bg-[var(--bg-2)] border ${isDatabase ? 'border-[var(--sutra-strong)]/40 bg-[var(--sutra-strong)]/[0.03]' : 'border-[var(--border)]'} space-y-2`}>
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <code className="text-[11px] font-mono font-bold text-[var(--sutra-ink)]">
          {spec.key}
        </code>
        <div className="flex items-center gap-1.5">
          {isDatabase ? (
            <Badge variant="success" className="text-[9px]">Render Postgres (Auto-configured)</Badge>
          ) : (
            <>
              {spec.auto_injected && <Badge variant="success" className="text-[9px]">auto-injected</Badge>}
              {spec.required ? (
                <Badge variant="destructive" className="text-[9px]">required</Badge>
              ) : (
                <Badge variant="warning" className="text-[9px]">optional</Badge>
              )}
              {spec.kind === 'build' && <Badge variant="neutral" className="text-[9px]">build-time</Badge>}
            </>
          )}
        </div>
      </div>
      {spec.description && (
        <p className="text-[10px] leading-snug text-[var(--text-2)] font-light">{spec.description}</p>
      )}

      {isDatabase ? (
        <div className="space-y-2 pt-1">
          <div className="flex items-center justify-between gap-2 flex-wrap text-[10px]">
            <span className="text-[var(--sutra-strong)] font-mono flex items-center gap-1">
              ✓ Auto-provisioned on Render — no manual database required
            </span>
            <Button variant="ghost" size="icon-sm"
              type="button"
              onClick={() => setShowOverride(!showOverride)}
              className="text-[9px] uppercase tracking-wider font-bold text-[var(--text-3)] hover:text-[var(--sutra-ink)] underline cursor-pointer"
            >
              {showOverride ? 'Hide custom override' : 'Custom DB URL (optional)'}
            </Button>
          </div>
          {showOverride && (
            <input
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder="postgresql://user:password@host/db (Leave empty to use Render PostgreSQL)"
              className="w-full px-3 py-2 bg-[var(--bg)] border border-[var(--border)] text-[var(--sutra-ink)] text-[11px] font-mono focus:outline-none focus:border-[var(--sutra-strong)] transition-colors"
            />
          )}
        </div>
      ) : spec.auto_injected && spec.current ? (
        <p className="text-[10px] font-mono text-[var(--sutra-strong)] break-all">
          Set automatically: {spec.current}
        </p>
      ) : (
        <>
          <div className="flex items-center gap-2">
            <input
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder={spec.current || spec.default || `Value for ${spec.key}`}
              className="w-full px-3 py-2 bg-[var(--bg)] border border-[var(--border)] text-[var(--sutra-ink)] text-[11px] font-mono focus:outline-none focus:border-[var(--sutra-strong)] transition-colors"
            />
            {spec.recommendation_kind === 'value' &&
              spec.recommended &&
              value !== spec.recommended && (
                <Button variant="outline" size="default"
                  type="button"
                  onClick={() => onChange(spec.recommended as string)}
                  className="shrink-0 border border-[var(--sutra-strong)] text-[9px] uppercase tracking-widest font-bold text-[var(--sutra-strong)] hover:bg-[var(--sutra-strong)] hover:text-[var(--bg)] transition-colors"
                >
                  Use default
                </Button>
              )}
          </div>
          {spec.recommendation_kind === 'hint' && spec.recommended && (
            <p className="text-[10px] leading-snug text-[var(--text-3)] font-light break-words">
              <span className="font-bold uppercase tracking-wide">Expected:</span>{' '}
              {spec.recommended}
            </p>
          )}
        </>
      )}
    </div>
  );
}

export function DeployModal({
  build,
  onClose,
  onDeployed,
}: {
  build: MVPBuild;
  onClose: () => void;
  onDeployed: (result: MVPDeployResult | string) => void;
}) {
  const [repoName, setRepoName] = useState(`mvp-${build.build_id.slice(0, 8)}`);
  const [description, setDescription] = useState('');
  const [privateRepo, setPrivateRepo] = useState(false);
  const [force, setForce] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [envPlan, setEnvPlan] = useState<MVPEnvPlan | null>(null);
  const [envValues, setEnvValues] = useState<Record<string, string>>({});
  const [deployResult, setDeployResult] = useState<MVPDeployResult | null>(null);
  const [liveStatus, setLiveStatus] = useState<MVPDeployStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    mvpApi
      .envPlan(build.build_id)
      .then((plan) => {
        if (cancelled) return;
        setEnvPlan(plan);
        const initial: Record<string, string> = {};
        for (const spec of plan.env) {
          if (spec.auto_injected) continue;
          // Saved value wins; otherwise pre-fill the backend's suggested
          // non-secret default so the user isn't staring at a blank field.
          if (spec.current) initial[spec.key] = spec.current;
          else if (spec.recommendation_kind === 'value' && spec.recommended) {
            initial[spec.key] = spec.recommended;
          }
        }
        setEnvValues((prev) => ({ ...initial, ...prev }));
      })
      .catch(() => setEnvPlan(null));
    return () => {
      cancelled = true;
    };
  }, [build.build_id]);

  useEffect(() => {
    if (!deployResult || !deployResult.deploy_state) return;
    const current = deployResult.deploy_state;
    const timer = setTimeout(() => {
      setLiveStatus({
        // 'unknown' rather than 'building': a missing status must not claim a deploy is
  // in progress.
  overall: (current.status as MVPDeployStatus['overall']) ?? 'unknown',
        services: current.services,
        injected_env: current.injected_env,
        deploy_url: build.render_deploy_url || null,
        repo_url: build.repo_url || null,
        frontend_url: build.frontend_url || null,
        backend_url: build.backend_url || null,
      });
    }, 0);
    return () => clearTimeout(timer);
  }, [deployResult, build.render_deploy_url, build.repo_url, build.frontend_url, build.backend_url]);

  // Poll the real Render deploy objects until the app is live or failed.
  useEffect(() => {
    if (!deployResult) return;
    if (liveStatus?.overall === 'live' || liveStatus?.overall === 'failed') return;
    let cancelled = false;
    const poll = async () => {
      try {
        const st = await mvpApi.deployStatus(build.build_id);
        if (!cancelled) setLiveStatus(st);
      } catch {
        // transient — keep last known state
      }
    };
    poll();
    const timer = setInterval(poll, 4000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [deployResult, liveStatus?.overall, build.build_id]);

  const pendingRequired = useMemo(() => {
    if (!envPlan) return [];
    return envPlan.env.filter((spec) => spec.required && !spec.auto_injected && spec.key !== 'DATABASE_URL' && !envValues[spec.key]?.trim());
  }, [envPlan, envValues]);

  const pendingEnv = Array.isArray(envPlan?.injected) ? [] : Object.entries(envPlan?.injected || {});

  const handleDeploy = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await mvpApi.deploy(build.build_id, {
        repo_name: repoName.trim(),
        description,
        private: privateRepo,
        force,
        env: envValues,
      });
      setDeployResult(res);
      onDeployed(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Deploy failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--sutra-ink)]/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-2xl bg-[var(--bg)] border border-[var(--sutra-strong)] p-5 sm:p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-4 mb-6">
          <h3 className="text-[14px] font-serif text-[var(--sutra-ink)] flex items-center gap-2">
            <Rocket className="w-4 h-4 text-[var(--sutra-strong)]" />
            <span>Deploy Build #{build.build_number}</span>
          </h3>
          <Button variant="ghost" size="icon-sm" onClick={onClose} className="text-[var(--text-3)] hover:text-[var(--sutra-ink)] transition-colors">
            <X className="w-4 h-4" />
          </Button>
        </div>

        {error && (
          <p className="text-[11px] text-[var(--red)] bg-[var(--bg)] border border-[var(--red)] p-3 mb-6 shadow-sm">
            {error}
          </p>
        )}

        {!deployResult ? (
          <div className="space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-ink)]">Repository Name</label>
                <input
                  value={repoName}
                  onChange={(e) => setRepoName(e.target.value)}
                  className="w-full px-4 py-2.5 bg-[var(--bg-2)] border border-[var(--border)] text-[var(--sutra-ink)] text-[13px] font-mono focus:outline-none focus:border-[var(--sutra-strong)] transition-colors shadow-sm"
                />
              </div>
              <div className="space-y-2">
                <label className="text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-ink)]">Description (optional)</label>
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Auto-generated MVP by AI Solution Builder"
                  className="w-full px-4 py-2.5 bg-[var(--bg-2)] border border-[var(--border)] text-[var(--sutra-ink)] text-[13px] font-light focus:outline-none focus:border-[var(--sutra-strong)] transition-colors shadow-sm"
                />
              </div>
            </div>

            <div className="space-y-3 pt-1">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={privateRepo}
                  onChange={(e) => setPrivateRepo(e.target.checked)}
                  className="mt-1 w-4 h-4 accent-[var(--sutra-ink)] cursor-pointer"
                />
                <div>
                  <span className="font-semibold text-[13px] text-[var(--sutra-ink)]">Make repository private</span>
                  <p className="text-[11px] text-[var(--text-2)] font-light mt-0.5">
                    {privateRepo ? "Private repos require Vercel permissions." : "Public repo recommended for 1-click deployments."}
                  </p>
                </div>
              </label>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={force}
                  onChange={(e) => setForce(e.target.checked)}
                  className="w-4 h-4 accent-[var(--sutra-ink)] cursor-pointer"
                />
                <span className="font-semibold text-[13px] text-[var(--sutra-ink)]">Force redeploy if already pushed</span>
              </label>
            </div>

            {/* Required / optional env vars discovered in the generated code */}
            <div className="p-3 bg-[var(--bg-2)] border border-[var(--border)] space-y-2">
              <div className="flex items-center gap-2 font-bold text-[10px] uppercase tracking-widest text-[var(--sutra-ink)]">
                <KeyRound className="w-3.5 h-3.5 text-[var(--sutra-strong)]" />
                <span>Environment Variables</span>
              </div>
              {!envPlan ? (
                <>
                  {pendingEnv.length === 0 ? (
                    <p className="text-[11px] text-[var(--text-2)] font-light flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-[var(--sutra-strong)]" />
                      No special env vars detected — deploy will run out-of-the-box.
                    </p>
                  ) : (
                    pendingEnv.map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between gap-2 text-[11px] font-mono">
                        <span className="font-bold text-[var(--sutra-ink)]">{key}</span>
                        <Badge variant="success" className="text-[9px]">{value}</Badge>
                      </div>
                    ))
                  )}
                </>
              ) : envPlan.env.length === 0 ? (
                <p className="text-[11px] text-[var(--text-2)] font-light flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-[var(--sutra-strong)]" />
                  No env vars referenced in the generated code.
                </p>
              ) : (
                <div className="space-y-2">
                  {envPlan.env.map((spec) => (
                    <EnvChip
                      key={spec.key}
                      spec={spec}
                      value={envValues[spec.key] || ''}
                      onChange={(v) => setEnvValues((prev) => ({ ...prev, [spec.key]: v }))}
                    />
                  ))}
                </div>
              )}
            </div>

            {pendingRequired.length > 0 && (
              <div className="p-4 bg-[var(--amber)]/10 border border-[var(--amber)]/30 space-y-1.5">
                <p className="flex items-center gap-1.5 font-bold text-[10px] uppercase tracking-widest text-[var(--amber)]">
                  <Info className="w-3.5 h-3.5" />
                  Pending required variables
                </p>
                <p className="text-[11px] font-light text-[var(--text-2)]">
                  {pendingRequired.map((s) => s.key).join(', ')} are still empty. They are never
                  guessed — you can fill them above before deploying, or deploy anyway and the app
                  will show its own missing-config error until set in Render.
                </p>
              </div>
            )}

            <div className="p-4 bg-[var(--bg-2)] border-l-2 border-[var(--sutra-strong)] space-y-1.5">
              <div className="flex items-center gap-2 font-bold text-[10px] uppercase tracking-widest text-[var(--sutra-ink)]">
                <Sparkles className="w-3.5 h-3.5 text-[var(--sutra-strong)]" />
                <span>Staged 1-Click Deploy to Render</span>
              </div>
              <p className="text-[12px] font-light text-[var(--text-2)]">
                Backend deploys first. The frontend then links to the live backend URL
                (NEXT_PUBLIC_API_URL) automatically. Status is polled live — never claimed
                prematurely.
              </p>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-[var(--border)]">
              <Button type="button" variant="ghost" size="sm" onClick={onClose}>
                Cancel
              </Button>
              <Button type="button" size="sm"
                onClick={handleDeploy}
                disabled={loading || !repoName.trim()}
               
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
                <span>{loading ? 'Deploying…' : 'Deploy Now'}</span>
              </Button>
            </div>
          </div>
        ) : (
          <DeployStatusPanel
      status={liveStatus}
      result={deployResult}
      buildId={build.build_id}
      onClose={onClose}
          />
        )}
      </div>
    </div>
  );
}

/**
 * Post-deployment environment editor.
 *
 * Env vars could previously only be set before deploying, so rotating a secret
 * or repointing DATABASE_URL meant a full redeploy. This patches the live
 * Render service(s) in place and restarts them.
 *
 * NEXT_PUBLIC_* values are inlined by Vercel at build time and cannot change on
 * a running service, so those are flagged as requiring a redeploy rather than
 * silently pretending to have applied.
 */
function DeployedEnvEditor({ buildId }: { buildId: string }) {
  const [open, setOpen] = useState(false);
  const [plan, setPlan] = useState<MVPEnvPlan | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!open || plan) return;
    mvpApi
      .envPlan(buildId)
      .then((p) => {
        setPlan(p);
        const seeded: Record<string, string> = {};
        for (const spec of p.env) {
          if (spec.auto_injected) continue;
          seeded[spec.key] = spec.current || '';
        }
        setValues(seeded);
      })
      .catch(() => setError('Could not load the environment variable list.'));
  }, [open, plan, buildId]);

  const save = async () => {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const res = await mvpApi.updateEnv(buildId, { env: values, restart: true });
      if (res.failed.length > 0) {
        setError(
          `${res.failed.length} variable(s) were rejected: ${res.failed
            .map((f) => `${f.key} (${f.error})`)
            .join(', ')}`
        );
      }
      const parts = [res.message];
      if (res.restarted > 0) parts.push('Service restarting to apply.');
      if (res.requires_redeploy.length > 0) {
        parts.push(
          `${res.requires_redeploy.join(', ')} ${
            res.requires_redeploy.length === 1 ? 'is' : 'are'
          } baked in at build time and need a redeploy to take effect.`
        );
      }
      setNotice(parts.join(' '));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update environment variables.');
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <Button variant="secondary" size="default"
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest border border-[var(--border)] hover:bg-[var(--bg-2)] transition-colors"
      >
        <Settings2 className="w-3.5 h-3.5" />
        Environment
      </Button>
    );
  }

  const specs = (plan?.env || []).filter((s) => !s.auto_injected);

  return (
    <div className="space-y-3 p-4 border border-[var(--border)] bg-[var(--bg-2)]">
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-xs font-bold uppercase tracking-widest text-[var(--sutra-ink)]">
          Environment (live)
        </h4>
        <Button variant="ghost" size="icon-sm"
          type="button"
          onClick={() => setOpen(false)}
          className="text-[var(--text-3)] hover:text-[var(--sutra-ink)]"
          aria-label="Close environment editor"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      <p className="text-[11px] text-[var(--text-3)]">
        Saves straight to the running service and restarts it. Secrets stay server-side and are
        never sent to the browser.
      </p>

      {!plan && !error && (
        <div className="flex items-center gap-2 text-[11px] text-[var(--text-3)]">
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading variables...
        </div>
      )}

      {specs.length > 0 && (
        <div className="space-y-3">
          {specs.map((spec) => (
            <EnvChip
              key={spec.key}
              spec={spec}
              value={values[spec.key] ?? ''}
              onChange={(v) => setValues((prev) => ({ ...prev, [spec.key]: v }))}
            />
          ))}
        </div>
      )}

      {error && <p className="text-[11px] text-[var(--red)]">{error}</p>}
      {notice && <p className="text-[11px] text-[var(--green)]">{notice}</p>}

      <div className="flex items-center gap-2">
        <Button variant="default" size="icon-sm"
          type="button"
          onClick={save}
          disabled={saving || specs.length === 0}
          className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest bg-[var(--sutra-ink)] text-[var(--bg)] disabled:opacity-50"
        >
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
          {saving ? 'Saving' : 'Save & restart'}
        </Button>
      </div>
    </div>
  );
}

function DeployStatusPanel({
  status,
  result,
  buildId,
  onClose,
}: {
  status: MVPDeployStatus | null;
  result: MVPDeployResult;
  buildId: string;
  onClose: () => void;
}) {
  const overall = status?.overall ?? 'unknown';
  const services = status?.services || result.deploy_state?.services || {};
  const names = Object.keys(services);

  return (
    <div className="space-y-4">
      <div
        className={`flex items-start gap-3 p-4 border bg-[var(--bg-2)] ${
          overall === 'live'
            ? 'border-[var(--green)]'
            : overall === 'failed'
              ? 'border-[var(--red)]'
              : 'border-[var(--sutra-strong)]'
        }`}
      >
        {overall === 'live' ? (
          <CheckCircle2 className="w-5 h-5 text-[var(--green)] shrink-0" />
        ) : overall === 'failed' ? (
          <Info className="w-5 h-5 text-[var(--red)] shrink-0" />
        ) : (
          <Loader2 className="w-5 h-5 text-[var(--sutra-strong)] animate-spin shrink-0" />
        )}
        <div>
          <h4 className="text-[13px] font-bold uppercase tracking-widest text-[var(--sutra-ink)]">
            {overall === 'live'
              ? 'Deployment Live'
              : overall === 'failed'
                ? 'Deployment Failed'
                : 'Deploying to Render…'}
          </h4>
          <p className="text-[12px] font-light text-[var(--text-2)] mt-1">
            {overall === 'live'
              ? 'Every service is live. The app is reachable at the URLs below.'
              : 'Status is polled from Render’s deploy objects every 4s — nothing is claimed until it actually deploys.'}
          </p>
        </div>
      </div>

      {/* Ordered services: backend first, then frontend */}
      <div className="space-y-3">
        <p className="text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)]">
          Provisioned services
        </p>
        {names.length === 0 && (
          <p className="text-[11px] text-[var(--text-2)] font-light font-mono">No services reported yet…</p>
        )}
        {names.map((name) => {
          const svc = services[name] || {};
          const svcStatus = svc.status || 'building';
          const label = DEPLOY_STEP_LABELS[name] || name;
          return (
            <div key={name} className="p-4 bg-[var(--bg-2)] border border-[var(--border)] space-y-2">
              <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="flex items-center gap-2 min-w-0">
                  {svcStatus === 'live' ? (
                    <CheckCircle2 className="w-4 h-4 text-[var(--green)] shrink-0" />
                  ) : svcStatus === 'failed' ? (
                    <Info className="w-4 h-4 text-[var(--red)] shrink-0" />
                  ) : (
                    <Loader2 className="w-4 h-4 text-[var(--sutra-strong)] animate-spin shrink-0" />
                  )}
                  <div className="min-w-0">
                    <span className="block text-[11px] font-bold uppercase tracking-widest text-[var(--sutra-ink)]">{name}</span>
                    <span className="block text-[10px] text-[var(--text-3)] font-light">{label}</span>
                  </div>
                </div>
                <Badge
                  variant={
                    svcStatus === 'live'
                      ? 'success'
                      : svcStatus === 'failed'
                        ? 'destructive'
                        : 'warning'
                  }
                  className={svcStatus === 'live' ? 'text-[10px]' : 'text-[10px] animate-pulse'}
                >
                  {svcStatus}
                </Badge>
              </div>

              {svc.error && <p className="text-[11px] text-[var(--red)] font-mono">{svc.error}</p>}

              {(svc.url || svc.dashboard_url || svc.deploy_url) && (
                <div className="flex items-center gap-2 flex-wrap pt-1">
                  {svc.url && (
                    <a
                      href={svc.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg)] border border-[var(--border)] hover:border-[var(--sutra-strong)] transition-colors text-[10px] font-mono text-[var(--sutra-ink)]"
                    >
                      <Globe className="w-3 h-3 text-[var(--green)]" />
                      <span>Visit</span>
                    </a>
                  )}
                  {svc.dashboard_url && (
                    <a
                      href={svc.dashboard_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg)] border border-[var(--border)] hover:border-[var(--sutra-strong)] transition-colors text-[10px] font-mono text-[var(--sutra-ink)]"
                    >
                      <ExternalLink className="w-3 h-3" />
                      <span>Render dashboard</span>
                    </a>
                  )}
                  {svc.deploy_url && (
                    <a
                      href={svc.deploy_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg)] border border-[var(--border)] hover:border-[var(--sutra-strong)] transition-colors text-[10px] font-mono text-[var(--sutra-ink)]"
                    >
                      <Loader2 className="w-3 h-3 text-[var(--sutra-strong)]" />
                      <span>Ongoing deployment</span>
                    </a>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="space-y-2 pt-1">
        {(overall === 'live' || overall === 'building') && (
          <>
            {(status?.frontend_url || result.frontend_url) && (
              <a
                href={(status?.frontend_url || result.frontend_url)!}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between p-4 bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-strong)] transition-colors shadow-sm"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Globe className="w-5 h-5 text-[var(--green)] shrink-0" />
                  <div className="min-w-0">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--sutra-ink)] block">Frontend</span>
                    <span className="text-[11px] text-[var(--text-2)] font-mono truncate max-w-[260px] lg:max-w-sm block mt-0.5">
                      {status?.frontend_url || result.frontend_url}
                    </span>
                  </div>
                </div>
                <ExternalLink className="w-4 h-4 text-[var(--text-3)]" />
              </a>
            )}
            {status?.backend_url && (
              <a
                href={`${status.backend_url}/docs`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-between p-4 bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-strong)] transition-colors shadow-sm"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Server className="w-5 h-5 text-[var(--sutra-ink)] shrink-0" />
                  <div className="min-w-0">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--sutra-ink)] block">Backend API docs</span>
                    <span className="text-[11px] text-[var(--text-2)] font-mono truncate max-w-[260px] block mt-0.5">
                      {status.backend_url}/docs
                    </span>
                  </div>
                </div>
                <ExternalLink className="w-4 h-4 text-[var(--text-3)]" />
              </a>
            )}
          </>
        )}

        {(result.repo_url || status?.repo_url) && (
          <a
            href={(result.repo_url || status?.repo_url)!}
            target="_blank"
            rel="noreferrer"
            className="flex items-center justify-between p-4 bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-strong)] transition-colors shadow-sm"
          >
            <div className="flex items-center gap-3 min-w-0">
              <Rocket className="w-5 h-5 text-[var(--sutra-ink)] shrink-0" />
              <div className="min-w-0">
                <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--sutra-ink)] block">GitHub Repository</span>
                <span className="font-mono text-[var(--sutra-strong)] text-[11px] truncate max-w-[220px] block mt-0.5">
                  {result.repo_url || status?.repo_url}
                </span>
              </div>
            </div>
            <ExternalLink className="w-4 h-4 text-[var(--text-3)]" />
          </a>
        )}
      </div>

      {/* Env vars can be changed on the live service, not only before deploy. */}
      {overall === 'live' && <DeployedEnvEditor buildId={buildId} />}

      <div className="flex justify-end gap-3 pt-4 border-t border-[var(--border)]">
        <Button type="button" size="sm" onClick={onClose}>
          Done
        </Button>
      </div>
    </div>
  );
}

export function ConfigureModal({
  build,
  onClose,
  onConfigured,
}: {
  build: MVPBuild;
  onClose: () => void;
  onConfigured: () => void;
}) {
  const [appName, setAppName] = useState('');
  const [envText, setEnvText] = useState('');
  const [envPlan, setEnvPlan] = useState<MVPEnvPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    mvpApi
      .envPlan(build.build_id)
      .then((plan) => {
        if (cancelled) return;
        setEnvPlan(plan);
        const lines: string[] = [];
        for (const spec of plan.env) {
          if (spec.auto_injected) continue;
          // current → the backend's usable suggestion → leave blank for the
          // user. Credential hints are never written into the field for them.
          const seeded =
            spec.current ||
            (spec.recommendation_kind === 'value' ? spec.recommended : null) ||
            '';
          lines.push(`${spec.key}=${seeded}`);
        }
        if (lines.length > 0) setEnvText(lines.join('\n'));
      })
      .catch(() => setEnvPlan(null));
    return () => {
      cancelled = true;
    };
  }, [build.build_id]);

  const handleConfigure = async () => {
    setLoading(true);
    setError(null);
    const env: Record<string, unknown> = {};
    for (const line of envText.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const eq = trimmed.indexOf('=');
      if (eq === -1) {
        setError(`Invalid env line: ${trimmed}. Expected KEY=VALUE.`);
        setLoading(false);
        return;
      }
      env[trimmed.slice(0, eq).trim()] = trimmed.slice(eq + 1).trim();
    }
    try {
      await mvpApi.configure(build.build_id, {
        app_name: appName.trim() || undefined,
        env,
      });
      onConfigured();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Configure failed.');
    } finally {
      setLoading(false);
    }
  };

  const required = envPlan?.env.filter((s) => s.required && !s.auto_injected && s.key !== 'DATABASE_URL') || [];
  const optional = envPlan?.env.filter((s) => !s.required || s.key === 'DATABASE_URL') || [];
  const auto = envPlan?.env.filter((s) => s.auto_injected || s.key === 'DATABASE_URL') || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--sutra-ink)]/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-xl bg-[var(--bg)] border border-[var(--border)] p-5 sm:p-8 shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-4 mb-6">
          <h3 className="text-[14px] font-serif text-[var(--sutra-ink)] flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-[var(--sutra-strong)]" />
            Tune Build #{build.build_number}
          </h3>
          <Button variant="ghost" size="icon-sm" onClick={onClose} className="text-[var(--text-3)] hover:text-[var(--sutra-ink)] transition-colors">
            <X className="w-4 h-4" />
          </Button>
        </div>

        {error && (
          <p className="text-[11px] text-[var(--red)] bg-[var(--bg)] border border-[var(--red)] p-3 mb-6 shadow-sm">{error}</p>
        )}

        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-ink)]">App Name (optional)</label>
            <input
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
              placeholder="my-production-app"
              className="w-full px-4 py-2.5 bg-[var(--bg-2)] border border-[var(--border)] text-[var(--sutra-ink)] text-[13px] font-mono focus:outline-none focus:border-[var(--sutra-strong)] transition-colors shadow-sm"
            />
          </div>

          {envPlan && (required.length > 0 || optional.length > 0 || auto.length > 0) && (
            <div className="p-3 bg-[var(--bg-2)] border border-[var(--border)] space-y-2">
              <p className="text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-ink)]">
                Detected environment variables
              </p>
              <div className="flex flex-wrap gap-1.5">
                {required.map((s) => (
                  <code key={s.key} className="text-[10px] font-mono px-2 py-0.5 bg-[var(--bg)] border border-[var(--red)]/40 text-[var(--red)]">
                    {s.key} · required
                  </code>
                ))}
                {optional.map((s) => (
                  <code key={s.key} className="text-[10px] font-mono px-2 py-0.5 bg-[var(--bg)] border border-[var(--border)] text-[var(--text-2)]">
                    {s.key} · optional
                  </code>
                ))}
                {auto.map((s) => (
                  <code key={s.key} className="text-[10px] font-mono px-2 py-0.5 bg-[var(--bg)] border border-[var(--green)]/40 text-[var(--green)]">
                    {s.key} · auto
                  </code>
                ))}
              </div>
              {auto.length > 0 && (
                <p className="text-[10px] text-[var(--text-3)] font-light">
                  Auto-injected on deploy (service URLs the agent already knows).
                </p>
              )}
            </div>
          )}

          <div className="space-y-2">
            <label className="text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-ink)]">Environment Overrides</label>
            <textarea
              value={envText}
              onChange={(e) => setEnvText(e.target.value)}
              rows={5}
              placeholder={'SECRET_KEY=change-me\nDATABASE_URL=...'}
              className="w-full px-4 py-3 bg-[var(--bg-2)] border border-[var(--border)] text-[var(--sutra-ink)] text-[13px] font-mono focus:outline-none focus:border-[var(--sutra-strong)] transition-colors resize-none shadow-sm"
            />
            <p className="text-[11px] text-[var(--text-2)] font-light mt-1">One KEY=VALUE per line. Written to .env.local.</p>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-6 mt-6 border-t border-[var(--border)]">
          <Button type="button" variant="ghost" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" size="sm"
            onClick={handleConfigure}
            disabled={loading}
           
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
            <span>Apply</span>
          </Button>
        </div>
      </div>
    </div>
  );
}

export function BuildCard({
  build,
  isDeployed,
  onDeploy,
  onConfigure,
  onDownload,
  onDestroy,
  onDestroyPreview,
  onSandbox,
}: {
  build: MVPBuild;
  isDeployed: boolean;
  onDeploy: () => void;
  onConfigure: () => void;
  onDownload: () => void;
  onDestroy: () => void;
  onDestroyPreview?: () => void;
  onSandbox?: () => void;
}) {
  const showStepper = build.status === 'building' || build.status === 'queued';
  const overall = build.deploy_state?.status || build.render_deploy_status;
  const services = build.deploy_state?.services || {};

  return (
    <div className="sutra-card min-w-0 rounded-xl border border-[var(--border)] bg-[var(--bg)] p-4 shadow-sm transition-shadow hover:shadow-md sm:p-5">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--sutra-ink)] font-serif text-base text-[var(--sutra-canvas)]">
            {build.build_number}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h4 className="text-[13px] font-bold tracking-wide text-[var(--sutra-ink)] truncate">
                {build.app_name?.trim() || `Build #${build.build_number}`}
              </h4>
              <StatusBadge status={build.status} />
            </div>
            <p className="mt-1 text-[11px] text-[var(--text-2)]">
              {formatBuildTime(build.created_at)} <span aria-hidden>·</span> {build.file_count} files
            </p>
            <p className="mt-1 truncate font-mono text-[10px] text-[var(--text-3)]" title={build.build_id}>
              Build ID · {build.build_id}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {(build.frontend_url || build.render_service_url) && (
            <Badge asChild variant="success" className="gap-1.5 px-3 py-1.5 text-[10px]">
              <a
                href={(build.frontend_url || build.render_service_url)!}
                target="_blank"
                rel="noreferrer"
              >
                <Globe className="w-3.5 h-3.5" />
                <span>Live App</span>
              </a>
            </Badge>
          )}
          {build.repo_url && (
            <a
              href={build.repo_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-ink)] hover:text-[var(--sutra-strong)] transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>GitHub</span>
            </a>
          )}
        </div>
      </div>

      {/* Acceptance Tests Quality Badge */}
      {build.app_config?.quality && (
        <div className="flex items-center justify-between gap-2 flex-wrap p-3 rounded-lg bg-[var(--green-wash)] border border-[var(--green-wash)] text-xs">
          <div className="flex items-center gap-2 text-[var(--green)] font-mono">
            <Check className="w-4 h-4 text-[var(--green)]" />
            <span className="font-semibold">
              {build.app_config.quality.passed} /{' '}
              {build.app_config.quality.passed + (build.app_config.quality.failed || 0)} Acceptance
              Tests Passing
            </span>
          </div>
          {build.app_config.quality.repair_turns !== undefined && (
            <span className="text-[11px] font-mono text-[var(--text-3)]">
              {build.app_config.quality.repair_turns > 0
                ? `${build.app_config.quality.repair_turns} repair loop(s)`
                : 'Zero repair turns'}
            </span>
          )}
        </div>
      )}

      {showStepper && (
        <div className="p-3 bg-[var(--bg-2)] border border-[var(--border)] rounded-sm space-y-3">
          <div className="flex min-w-0 items-start justify-between gap-2 text-[11px]">
            <span className="flex min-w-0 flex-1 items-start gap-2 font-semibold text-[var(--sutra-ink)]">
              <Loader2 className="mt-0.5 w-3.5 h-3.5 shrink-0 animate-spin text-[var(--sutra-strong)]" />
              <span className="min-w-0 break-words whitespace-normal [overflow-wrap:anywhere]">
                {build.progress?.message ||
                  (build.status === 'queued'
                    ? 'Build queued in worker pipeline...'
                    : 'Synthesizing application structure...')}
              </span>
            </span>
            {build.progress?.percentage !== undefined && (
              <span className="shrink-0 font-mono font-bold text-[var(--sutra-strong)]">
                {build.progress.percentage}%
              </span>
            )}
          </div>
          {build.progress?.percentage !== undefined && (
            <div className="w-full h-1.5 bg-[var(--bg)] rounded-full overflow-hidden border border-[var(--border)]">
              <div
                className="h-full bg-gradient-to-r from-[var(--sutra-strong)] to-[var(--green)] transition-all duration-300"
                style={{ width: `${Math.max(5, build.progress.percentage)}%` }}
              />
            </div>
          )}
          <BuildStepList build={build} />
        </div>
      )}

      {overall && overall !== 'building' && overall !== 'queued' && (
        <div
          className={`flex items-center justify-between gap-2 flex-wrap p-3 border-l-2 text-[11px] ${
            overall === 'live'
              ? 'border-[var(--green)] bg-[var(--green-wash)]'
              : overall === 'failed'
                ? 'border-[var(--red)] bg-[var(--red)]/10'
                : 'border-[var(--sutra-strong)] bg-[var(--bg-2)]'
          }`}
        >
          <span className="flex items-center gap-2 font-bold uppercase tracking-widest text-[var(--sutra-ink)]">
            <Rocket className="w-3.5 h-3.5 text-[var(--sutra-strong)]" />
            Deploy: {overall}
          </span>
          {Object.values(services).length > 0 && (
            <span className="font-mono text-[var(--text-3)]">
              {Object.entries(services)
                .map(([k, v]) => `${k} → ${(v as { status?: string }).status || 'building'}`)
                .join(' · ')}
            </span>
          )}
        </div>
      )}

      <ResourceGauges engineOnline={showStepper || overall === 'building'} />

      {build.error_message && (
        <p className="text-[11px] text-[var(--red)] bg-[var(--bg)] border border-[var(--red)] p-3 font-mono shadow-sm">
          {build.error_message}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2 border-t border-[var(--border)] pt-3">
        {build.status === 'complete' && (
          <>
            <Button asChild size="sm" className="gap-1.5">
              <Link href={`/sandbox?buildId=${build.build_id}`}>
                <Code2 className="w-3.5 h-3.5 text-[var(--background)]" />
                <span>Live Sandbox</span>
              </Link>
            </Button>

            {(build.frontend_url || build.render_service_url) && (
              <Button asChild variant="secondary" size="sm">
                <a
                  href={(build.frontend_url || build.render_service_url)!}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Globe className="w-3.5 h-3.5 text-[var(--green)]" />
                  <span>Open App</span>
                </a>
              </Button>
            )}

            {build.backend_url && (
              <Button asChild variant="secondary" size="sm">
                <a href={`${build.backend_url}/docs`} target="_blank" rel="noreferrer">
                  <Server className="w-3.5 h-3.5" />
                  <span>API Docs</span>
                </a>
              </Button>
            )}

            <Button type="button" variant="secondary" size="sm" onClick={onDownload}>
              <Download className="w-3.5 h-3.5" />
              <span>Download ZIP</span>
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={onConfigure}>
              <Settings2 className="w-3.5 h-3.5" />
              <span>Tune</span>
            </Button>
            {onSandbox && (
              <Button type="button" variant="secondary" size="sm" onClick={onSandbox}>
                <Globe className="w-3.5 h-3.5 text-[var(--sutra-strong)]" />
                <span>Sandbox</span>
              </Button>
            )}
            {!isDeployed && (
              <Button type="button" size="sm" onClick={onDeploy}>
                <Rocket className="w-3.5 h-3.5" />
                <span>Deploy</span>
              </Button>
            )}

            {build.render_service_url && onDestroyPreview && (
              <Button variant="secondary" size="default"
                onClick={onDestroyPreview}
                className="flex items-center gap-2 bg-[var(--bg)] hover:bg-[var(--bg-2)] text-[var(--red)] border border-[var(--border)] transition-colors text-[10px] uppercase tracking-widest font-bold"
              >
                <PowerOff className="w-3.5 h-3.5" />
                <span>Teardown</span>
              </Button>
            )}
          </>
        )}
        {(build.status === 'failed' || build.status === 'cancelled') && (
          <Button variant="secondary" size="default"
            onClick={onDestroy}
            className="flex items-center gap-2 bg-[var(--bg)] hover:bg-[var(--bg-2)] text-[var(--red)] border border-[var(--border)] transition-colors text-[10px] uppercase tracking-widest font-bold"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Destroy</span>
          </Button>
        )}
      </div>

      <FileTree build={build} />
    </div>
  );
}
