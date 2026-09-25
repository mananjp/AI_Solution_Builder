'use client';

import React, { useState } from 'react';
import {
  Box,
  Check,
  Download,
  ExternalLink,
  FolderTree,
  Globe,
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
import { MVPBuild, MVPBuildStatus, MVPDeployResult } from '@/types';

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
  const [deployResult, setDeployResult] = useState<MVPDeployResult | null>(null);

  const handleDeploy = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await mvpApi.deploy(build.build_id, {
        repo_name: repoName.trim(),
        description,
        private: privateRepo,
        force,
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
      <div className="w-full max-w-lg bg-[var(--bg)] border border-[var(--sutra-muted-gold)] p-5 sm:p-8 shadow-2xl relative max-h-[90vh] overflow-y-auto">
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

            <div className="space-y-3 pt-2">
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

            <div className="p-4 bg-[var(--bg-2)] border-l-2 border-[var(--sutra-muted-gold)] space-y-1.5 mt-2">
              <div className="flex items-center gap-2 font-bold text-[10px] uppercase tracking-widest text-[var(--sutra-charcoal)]">
                <Sparkles className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
                <span>1-Click Deploy to GitHub & Render</span>
              </div>
              <p className="text-[12px] font-light text-[var(--text-2)]">
                Pushes code to GitHub and auto-provisions on Render.
              </p>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-[var(--border)]">
              <button
                onClick={onClose}
                className="btn btn-ghost px-5 py-2.5"
              >
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
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-4 border border-[var(--green)] bg-[var(--bg-2)]">
              <Check className="w-5 h-5 text-[var(--green)] shrink-0" />
              <div>
                <h4 className="text-[13px] font-bold uppercase tracking-widest text-[var(--sutra-charcoal)]">Deployment Successful</h4>
                <p className="text-[12px] font-light text-[var(--text-2)] mt-1">Pushed to GitHub and configured for Render.</p>
              </div>
            </div>

            <div className="space-y-3">
              {(deployResult.frontend_url || deployResult.render_service_url) && (
                <a
                  href={(deployResult.frontend_url || deployResult.render_service_url)!}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between p-4 bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] transition-colors shadow-sm"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Globe className="w-5 h-5 text-[var(--green)] shrink-0" />
                    <div className="min-w-0">
                      <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--sutra-charcoal)] block">Frontend Application</span>
                      <span className="text-[11px] text-[var(--text-2)] font-mono truncate max-w-[240px] lg:max-w-xs block mt-0.5">
                        {deployResult.frontend_url || deployResult.render_service_url}
                      </span>
                    </div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-[var(--text-3)]" />
                </a>
              )}

              {deployResult.repo_url && (
                <a
                  href={deployResult.repo_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between p-4 bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] transition-colors shadow-sm"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <Rocket className="w-5 h-5 text-[var(--sutra-charcoal)] shrink-0" />
                    <div className="min-w-0">
                      <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--sutra-charcoal)] block">GitHub Repository</span>
                      <span className="font-mono text-[var(--sutra-muted-gold)] text-[11px] truncate max-w-[220px] lg:max-w-[200px] block mt-0.5">{deployResult.repo_url}</span>
                    </div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-[var(--text-3)]" />
                </a>
              )}
            </div>

            <div className="flex justify-end pt-4 border-t border-[var(--border)]">
              <button
                onClick={onClose}
                className="btn btn-primary px-6 py-2.5"
              >
                Done
              </button>
            </div>
          </div>
        )}
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--sutra-charcoal)]/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-md bg-[var(--bg)] border border-[var(--border)] p-5 sm:p-8 shadow-2xl max-h-[90vh] overflow-y-auto">
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
          <button
            onClick={onClose}
            className="btn btn-ghost px-5 py-2.5"
          >
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
}: {
  build: MVPBuild;
  isDeployed: boolean;
  onDeploy: () => void;
  onConfigure: () => void;
  onDownload: () => void;
  onDestroy: () => void;
  onDestroyPreview?: () => void;
}) {
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

      {(build.status === 'building' || build.status === 'queued') && (

        <div className="p-3 bg-[var(--bg-2)] border border-[var(--border)] rounded-sm space-y-2">
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
        </div>
      )}

      {build.error_message && (
        <p className="text-[11px] text-[var(--red)] bg-[var(--bg)] border border-[var(--red)] p-3 font-mono shadow-sm">
          {build.error_message}
        </p>
      )}


      <div className="flex items-center gap-3 flex-wrap pt-2">
        {build.status === 'complete' && (
          <>
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

            <button
              onClick={onDownload}
              className="btn btn-secondary px-4 py-2"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download ZIP</span>
            </button>
            <button
              onClick={onConfigure}
              className="btn btn-secondary px-4 py-2"
            >
              <Settings2 className="w-3.5 h-3.5" />
              <span>Tune</span>
            </button>
            {!isDeployed && (
              <button
                onClick={onDeploy}
                className="btn btn-primary px-5 py-2"
              >
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