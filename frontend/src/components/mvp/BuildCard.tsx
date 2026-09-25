'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Box,
  Check,
  CheckCircle2,
  CircleDashed,
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

export const STATUS_STYLES: Record<MVPBuildStatus, string> = {
  queued: 'badge-amber',
  pending: 'badge-amber',
  building: 'badge-blue animate-pulse',
  complete: 'badge-green',
  failed: 'badge-red',
  cancelled: 'badge-gray',
};

export function StatusBadge({ status }: { status: MVPBuildStatus }) {
  return <span className={`badge ${STATUS_STYLES[status]}`}>{status}</span>;
}

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
      return PROGRESS_STEPS.map((def) => {
        const match = incoming.find((s) => s.key === def.key);
        const status = match?.status || 'pending';
        return { ...def, status };
      });
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
  return (
    <ol className="grid grid-cols-1 sm:grid-cols-5 gap-1.5">
      {steps.map((step) => (
        <li key={step.key} className="flex items-start gap-2 min-w-0">
          {step.status === 'completed' ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-[var(--green)] shrink-0 mt-0.5" />
          ) : step.status === 'active' ? (
            <Loader2 className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] animate-spin shrink-0 mt-0.5" />
          ) : (
            <CircleDashed className="w-3.5 h-3.5 text-[var(--text-3)] shrink-0 mt-0.5" />
          )}
          <span
            className={`text-[10px] leading-tight min-w-0 ${
              step.status === 'completed'
                ? 'text-[var(--text-2)] line-through decoration-[var(--green)]/40'
                : step.status === 'active'
                  ? 'font-semibold text-[var(--sutra-charcoal)]'
                  : 'text-[var(--text-3)]'
            }`}
          >
            {step.label}
          </span>
        </li>
      ))}
    </ol>
  );
}

function FileTree({ build }: { build: MVPBuild }) {
  const [open, setOpen] = useState(false);
  const files = build.files || [];

  return (
    <div className="pt-3 border-t border-[var(--border)] mt-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-[11px] uppercase tracking-widest font-bold text-[var(--text-3)] hover:text-[var(--sutra-charcoal)] transition-colors"
      >
        <FolderTree className="w-3.5 h-3.5 text-[var(--sutra-charcoal)]" />
        <span>Generated Files ({build.file_count})</span>
        <span className="text-[var(--sutra-muted-gold)] font-mono">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="mt-3 max-h-64 overflow-y-auto overflow-x-hidden rounded-sm bg-[var(--bg-2)] border border-[var(--border)] p-4 shadow-inner">
          {files.length === 0 ? (
            <p className="text-[11px] text-[var(--text-3)] font-mono">No file tree returned yet.</p>
          ) : (
            <ul className="space-y-1.5 min-w-0">
              {files.map((f) => (
                <li key={f.path} className="flex items-start gap-2 text-[11px] font-mono min-w-0">
                  <Box className="w-3.5 h-3.5 text-[var(--text-3)] shrink-0 mt-0.5" />
                  <span className={`min-w-0 break-all ${f.is_dir ? 'font-semibold text-[var(--sutra-charcoal)]' : 'text-[var(--text-2)] font-light'}`}>{f.path}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

const DEPLOY_STEP_LABELS: Record<string, string> = {
  backend: 'Backend API service',
  frontend: 'Frontend app (links to backend URL)',
};

function EnvChip({ spec, value, onChange }: { spec: MVPEnvVarSpec; value: string; onChange: (v: string) => void }) {
  return (
    <div className="p-3 bg-[var(--bg-2)] border border-[var(--border)] space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <code className="text-[11px] font-mono font-bold text-[var(--sutra-charcoal)]">
          {spec.key}
        </code>
        <div className="flex items-center gap-1.5">
          {spec.auto_injected && <span className="badge badge-green text-[9px]">auto-injected</span>}
          {spec.required ? (
            <span className="badge badge-red text-[9px]">required</span>
          ) : (
            <span className="badge badge-amber text-[9px]">optional</span>
          )}
          {spec.kind === 'build' && <span className="badge badge-gray text-[9px]">build-time</span>}
        </div>
      </div>
      {spec.description && (
        <p className="text-[10px] leading-snug text-[var(--text-2)] font-light">{spec.description}</p>
      )}
      {spec.auto_injected && spec.current ? (
        <p className="text-[10px] font-mono text-[var(--sutra-muted-gold)] break-all">
          Set automatically: {spec.current}
        </p>
      ) : (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={spec.current || spec.default || `Value for ${spec.key}`}
          className="w-full px-3 py-2 bg-[var(--bg)] border border-[var(--border)] text-[var(--sutra-charcoal)] text-[11px] font-mono focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors"
        />
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
          if (spec.current && !spec.auto_injected) initial[spec.key] = spec.current;
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
        overall: (current.status as MVPDeployStatus['overall']) || 'building',
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
    return envPlan.env.filter((spec) => spec.required && !spec.auto_injected && !envValues[spec.key]?.trim());
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--sutra-charcoal)]/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-2xl bg-[var(--bg)] border border-[var(--sutra-muted-gold)] p-5 sm:p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-4 mb-6">
          <h3 className="text-[14px] font-serif text-[var(--sutra-charcoal)] flex items-center gap-2">
            <Rocket className="w-4 h-4 text-[var(--sutra-muted-gold)]" />
            <span>Deploy Build #{build.build_number}</span>
          </h3>
          <button onClick={onClose} className="text-[var(--text-3)] hover:text-[var(--sutra-charcoal)] transition-colors">
            <X className="w-4 h-4" />
          </button>
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
                <label className="text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">Repository Name</label>
                <input
                  value={repoName}
                  onChange={(e) => setRepoName(e.target.value)}
                  className="w-full px-4 py-2.5 bg-[var(--bg-2)] border border-[var(--border)] text-[var(--sutra-charcoal)] text-[13px] font-mono focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors shadow-sm"
                />
              </div>
              <div className="space-y-2">
                <label className="text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">Description (optional)</label>
                <input
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Auto-generated MVP by AI Solution Builder"
                  className="w-full px-4 py-2.5 bg-[var(--bg-2)] border border-[var(--border)] text-[var(--sutra-charcoal)] text-[13px] font-light focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors shadow-sm"
                />
              </div>
            </div>

            <div className="space-y-3 pt-1">
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={privateRepo}
                  onChange={(e) => setPrivateRepo(e.target.checked)}
                  className="mt-1 w-4 h-4 accent-[var(--sutra-charcoal)] cursor-pointer"
                />
                <div>
                  <span className="font-semibold text-[13px] text-[var(--sutra-charcoal)]">Make repository private</span>
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
                  className="w-4 h-4 accent-[var(--sutra-charcoal)] cursor-pointer"
                />
                <span className="font-semibold text-[13px] text-[var(--sutra-charcoal)]">Force redeploy if already pushed</span>
              </label>
            </div>

            {/* Required / optional env vars discovered in the generated code */}
            <div className="p-3 bg-[var(--bg-2)] border border-[var(--border)] space-y-2">
              <div className="flex items-center gap-2 font-bold text-[10px] uppercase tracking-widest text-[var(--sutra-charcoal)]">
                <KeyRound className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
                <span>Environment Variables</span>
              </div>
              {!envPlan ? (
                <>
                  {pendingEnv.length === 0 ? (
                    <p className="text-[11px] text-[var(--text-2)] font-light flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
                      No special env vars detected — deploy will run out-of-the-box.
                    </p>
                  ) : (
                    pendingEnv.map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between gap-2 text-[11px] font-mono">
                        <span className="font-bold text-[var(--sutra-charcoal)]">{key}</span>
                        <span className="badge badge-green text-[9px]">{value}</span>
                      </div>
                    ))
                  )}
                </>
              ) : envPlan.env.length === 0 ? (
                <p className="text-[11px] text-[var(--text-2)] font-light flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
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
              <div className="p-4 bg-[#f59e0b]/10 border border-[#f59e0b]/30 space-y-1.5">
                <p className="flex items-center gap-1.5 font-bold text-[10px] uppercase tracking-widest text-amber-700 dark:text-amber-400">
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

            <div className="p-4 bg-[var(--bg-2)] border-l-2 border-[var(--sutra-muted-gold)] space-y-1.5">
              <div className="flex items-center gap-2 font-bold text-[10px] uppercase tracking-widest text-[var(--sutra-charcoal)]">
                <Sparkles className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
                <span>Staged 1-Click Deploy to Render</span>
              </div>
              <p className="text-[12px] font-light text-[var(--text-2)]">
                Backend deploys first. The frontend then links to the live backend URL
                (NEXT_PUBLIC_API_URL) automatically. Status is polled live — never claimed
                prematurely.
              </p>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-[var(--border)]">
              <button onClick={onClose} className="btn btn-ghost px-5 py-2.5">
                Cancel
              </button>
              <button
                onClick={handleDeploy}
                disabled={loading || !repoName.trim()}
                className="btn btn-primary px-6 py-2.5"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
                <span>{loading ? 'Deploying…' : 'Deploy Now'}</span>
              </button>
            </div>
          </div>
        ) : (
          <DeployStatusPanel
            status={liveStatus}
            result={deployResult}
            onClose={onClose}
          />
        )}
      </div>
    </div>
  );
}

function DeployStatusPanel({
  status,
  result,
  onClose,
}: {
  status: MVPDeployStatus | null;
  result: MVPDeployResult;
  onClose: () => void;
}) {
  const overall = status?.overall || 'building';
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
              : 'border-[var(--sutra-muted-gold)]'
        }`}
      >
        {overall === 'live' ? (
          <CheckCircle2 className="w-5 h-5 text-[var(--green)] shrink-0" />
        ) : overall === 'failed' ? (
          <Info className="w-5 h-5 text-[var(--red)] shrink-0" />
        ) : (
          <Loader2 className="w-5 h-5 text-[var(--sutra-muted-gold)] animate-spin shrink-0" />
        )}
        <div>
          <h4 className="text-[13px] font-bold uppercase tracking-widest text-[var(--sutra-charcoal)]">
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
                    <Loader2 className="w-4 h-4 text-[var(--sutra-muted-gold)] animate-spin shrink-0" />
                  )}
                  <div className="min-w-0">
                    <span className="block text-[11px] font-bold uppercase tracking-widest text-[var(--sutra-charcoal)]">{name}</span>
                    <span className="block text-[10px] text-[var(--text-3)] font-light">{label}</span>
                  </div>
                </div>
                <span
                  className={`badge ${
                    svcStatus === 'live'
                      ? 'badge-green'
                      : svcStatus === 'failed'
                        ? 'badge-red'
                        : 'badge-amber animate-pulse'
                  } text-[10px]`}
                >
                  {svcStatus}
                </span>
              </div>

              {svc.error && <p className="text-[11px] text-[var(--red)] font-mono">{svc.error}</p>}

              {(svc.url || svc.dashboard_url || svc.deploy_url) && (
                <div className="flex items-center gap-2 flex-wrap pt-1">
                  {svc.url && (
                    <a
                      href={svc.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] transition-colors text-[10px] font-mono text-[var(--sutra-charcoal)]"
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
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] transition-colors text-[10px] font-mono text-[var(--sutra-charcoal)]"
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
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[var(--bg)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] transition-colors text-[10px] font-mono text-[var(--sutra-charcoal)]"
                    >
                      <Loader2 className="w-3 h-3 text-[var(--sutra-muted-gold)]" />
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
                className="flex items-center justify-between p-4 bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] transition-colors shadow-sm"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Globe className="w-5 h-5 text-[var(--green)] shrink-0" />
                  <div className="min-w-0">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--sutra-charcoal)] block">Frontend</span>
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
                className="flex items-center justify-between p-4 bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] transition-colors shadow-sm"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Server className="w-5 h-5 text-[var(--sutra-charcoal)] shrink-0" />
                  <div className="min-w-0">
                    <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--sutra-charcoal)] block">Backend API docs</span>
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
            className="flex items-center justify-between p-4 bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] transition-colors shadow-sm"
          >
            <div className="flex items-center gap-3 min-w-0">
              <Rocket className="w-5 h-5 text-[var(--sutra-charcoal)] shrink-0" />
              <div className="min-w-0">
                <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--sutra-charcoal)] block">GitHub Repository</span>
                <span className="font-mono text-[var(--sutra-muted-gold)] text-[11px] truncate max-w-[220px] block mt-0.5">
                  {result.repo_url || status?.repo_url}
                </span>
              </div>
            </div>
            <ExternalLink className="w-4 h-4 text-[var(--text-3)]" />
          </a>
        )}
      </div>

      <div className="flex justify-end gap-3 pt-4 border-t border-[var(--border)]">
        <button onClick={onClose} className="btn btn-primary px-6 py-2.5">
          Done
        </button>
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
          lines.push(spec.current ? `${spec.key}=${spec.current}` : `${spec.key}=`);
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

  const required = envPlan?.env.filter((s) => s.required) || [];
  const optional = envPlan?.env.filter((s) => !s.required) || [];
  const auto = envPlan?.env.filter((s) => s.auto_injected) || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--sutra-charcoal)]/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-xl bg-[var(--bg)] border border-[var(--border)] p-5 sm:p-8 shadow-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-4 mb-6">
          <h3 className="text-[14px] font-serif text-[var(--sutra-charcoal)] flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-[var(--sutra-muted-gold)]" />
            Tune Build #{build.build_number}
          </h3>
          <button onClick={onClose} className="text-[var(--text-3)] hover:text-[var(--sutra-charcoal)] transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <p className="text-[11px] text-[var(--red)] bg-[var(--bg)] border border-[var(--red)] p-3 mb-6 shadow-sm">{error}</p>
        )}

        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">App Name (optional)</label>
            <input
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
              placeholder="my-production-app"
              className="w-full px-4 py-2.5 bg-[var(--bg-2)] border border-[var(--border)] text-[var(--sutra-charcoal)] text-[13px] font-mono focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors shadow-sm"
            />
          </div>

          {envPlan && (required.length > 0 || optional.length > 0 || auto.length > 0) && (
            <div className="p-3 bg-[var(--bg-2)] border border-[var(--border)] space-y-2">
              <p className="text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">
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
            <label className="text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">Environment Overrides</label>
            <textarea
              value={envText}
              onChange={(e) => setEnvText(e.target.value)}
              rows={5}
              placeholder={'SECRET_KEY=change-me\nDATABASE_URL=...'}
              className="w-full px-4 py-3 bg-[var(--bg-2)] border border-[var(--border)] text-[var(--sutra-charcoal)] text-[13px] font-mono focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors resize-none shadow-sm"
            />
            <p className="text-[11px] text-[var(--text-2)] font-light mt-1">One KEY=VALUE per line. Written to .env.local.</p>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-6 mt-6 border-t border-[var(--border)]">
          <button onClick={onClose} className="btn btn-ghost px-5 py-2.5">
            Cancel
          </button>
          <button
            onClick={handleConfigure}
            disabled={loading}
            className="btn btn-primary px-6 py-2.5"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
            <span>Apply</span>
          </button>
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
    <div className="sutra-card p-5 bg-[var(--bg)] space-y-4 shadow-sm border-l-2 border-l-[var(--sutra-muted-gold)] hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)] flex items-center justify-center font-serif text-lg shrink-0">
            {build.build_number}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h4 className="text-[12px] font-bold uppercase tracking-widest text-[var(--sutra-charcoal)]">Build Orchestration</h4>
              <StatusBadge status={build.status} />
            </div>
            <p className="text-[11px] text-[var(--text-2)] font-mono mt-1 break-all">
              {build.file_count} files · {build.build_id.slice(0, 8)}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {(build.frontend_url || build.render_service_url) && (
            <a
              href={(build.frontend_url || build.render_service_url)!}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 badge badge-green text-[10px]"
            >
              <Globe className="w-3.5 h-3.5" />
              <span>Live App</span>
            </a>
          )}
          {build.repo_url && (
            <a
              href={build.repo_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)] hover:text-[var(--sutra-muted-gold)] transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>GitHub</span>
            </a>
          )}
        </div>
      </div>

      {/* Acceptance Tests Quality Badge */}
      {build.app_config?.quality && (
        <div className="flex items-center justify-between gap-2 flex-wrap p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs">
          <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-mono">
            <Check className="w-4 h-4 text-emerald-500" />
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
          <div className="flex items-center justify-between text-[11px]">
            <span className="font-semibold text-[var(--sutra-charcoal)] flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--sutra-muted-gold)]" />
              <span>
                {build.progress?.message ||
                  (build.status === 'queued'
                    ? 'Build queued in worker pipeline...'
                    : 'Synthesizing application structure...')}
              </span>
            </span>
            {build.progress?.percentage !== undefined && (
              <span className="font-mono font-bold text-[var(--sutra-muted-gold)]">
                {build.progress.percentage}%
              </span>
            )}
          </div>
          {build.progress?.percentage !== undefined && (
            <div className="w-full h-1.5 bg-[var(--bg)] rounded-full overflow-hidden border border-[var(--border)]">
              <div
                className="h-full bg-gradient-to-r from-[var(--sutra-muted-gold)] to-[var(--green)] transition-all duration-300"
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
              ? 'border-[var(--green)] bg-emerald-500/10'
              : overall === 'failed'
                ? 'border-[var(--red)] bg-[var(--red)]/10'
                : 'border-[var(--sutra-muted-gold)] bg-[var(--bg-2)]'
          }`}
        >
          <span className="flex items-center gap-2 font-bold uppercase tracking-widest text-[var(--sutra-charcoal)]">
            <Rocket className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
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

      <div className="flex items-center gap-3 flex-wrap pt-2">
        {build.status === 'complete' && (
          <>
            <Link
              href={`/sandbox?buildId=${build.build_id}`}
              className="btn btn-primary px-4 py-2 flex items-center gap-1.5 shadow-sm"
            >
              <Code2 className="w-3.5 h-3.5 text-white" />
              <span>Live Sandbox</span>
            </Link>

            {(build.frontend_url || build.render_service_url) && (
              <a
                href={(build.frontend_url || build.render_service_url)!}
                target="_blank"
                rel="noreferrer"
                className="btn btn-secondary px-4 py-2"
              >
                <Globe className="w-3.5 h-3.5 text-[var(--green)]" />
                <span>Open App</span>
              </a>
            )}

            {build.backend_url && (
              <a
                href={`${build.backend_url}/docs`}
                target="_blank"
                rel="noreferrer"
                className="btn btn-secondary px-4 py-2"
              >
                <Server className="w-3.5 h-3.5" />
                <span>API Docs</span>
              </a>
            )}

            <button onClick={onDownload} className="btn btn-secondary px-4 py-2">
              <Download className="w-3.5 h-3.5" />
              <span>Download ZIP</span>
            </button>
            <button onClick={onConfigure} className="btn btn-secondary px-4 py-2">
              <Settings2 className="w-3.5 h-3.5" />
              <span>Tune</span>
            </button>
            {onSandbox && (
              <button onClick={onSandbox} className="btn btn-secondary px-4 py-2">
                <Globe className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
                <span>Sandbox</span>
              </button>
            )}
            {!isDeployed && (
              <button onClick={onDeploy} className="btn btn-primary px-5 py-2">
                <Rocket className="w-3.5 h-3.5" />
                <span>Deploy</span>
              </button>
            )}

            {build.render_service_url && onDestroyPreview && (
              <button
                onClick={onDestroyPreview}
                className="flex items-center gap-2 px-4 py-2 bg-[var(--bg)] hover:bg-[var(--bg-2)] text-[var(--red)] border border-[var(--border)] transition-colors shadow-sm text-[10px] uppercase tracking-widest font-bold"
              >
                <PowerOff className="w-3.5 h-3.5" />
                <span>Teardown</span>
              </button>
            )}
          </>
        )}
        {(build.status === 'failed' || build.status === 'cancelled') && (
          <button
            onClick={onDestroy}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--bg)] hover:bg-[var(--bg-2)] text-[var(--red)] border border-[var(--border)] transition-colors shadow-sm text-[10px] uppercase tracking-widest font-bold"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Destroy</span>
          </button>
        )}
      </div>

      <FileTree build={build} />
    </div>
  );
}