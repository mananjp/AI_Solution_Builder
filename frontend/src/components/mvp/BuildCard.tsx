'use client';

import React, { useState } from 'react';
import {
  Box,
  Check,
  Clock,
  Download,
  ExternalLink,
  FolderTree,
  Globe,
  LayoutDashboard,
  Loader2,
  PowerOff,
  Rocket,
  Server,
  Settings2,
  Sparkles,
  Trash2,
  Triangle,
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
    <div className="pt-3 border-t border-[#1a1a1a]">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-[11px] font-medium text-[#a1a1a1] hover:text-white transition-colors"
      >
        <FolderTree className="w-3.5 h-3.5 text-[#6366f1]" />
        <span>Generated Files ({build.file_count})</span>
        <span className="text-[#555] font-mono">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="mt-2 max-h-64 overflow-y-auto rounded-lg bg-[#0a0a0a] border border-[#1a1a1a] p-3">
          {files.length === 0 ? (
            <p className="text-[11px] text-[#555] font-mono">No file tree returned yet.</p>
          ) : (
            <ul className="space-y-1">
              {files.map((f) => (
                <li key={f.path} className="flex items-center gap-2 text-[11px] font-mono">
                  <Box className="w-3 h-3 text-[#555] shrink-0" />
                  <span className={f.is_dir ? 'font-semibold text-white' : 'text-[#a1a1a1]'}>{f.path}</span>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 animate-fade-in">
      <div className="w-full max-w-lg rounded-xl bg-[#111] border border-[#242424] p-6 space-y-4 shadow-2xl relative">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Rocket className="w-4 h-4 text-[#6366f1]" />
            <span>Deploy Build #{build.build_number}</span>
          </h3>
          <button onClick={onClose} className="text-[#555] hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <p className="text-[12px] text-[#f87171] bg-[#ef444410] border border-[#ef444420] rounded-lg p-3">
            {error}
          </p>
        )}

        {!deployResult ? (
          <>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-[#a1a1a1]">Repository Name</label>
              <input
                value={repoName}
                onChange={(e) => setRepoName(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-[#0a0a0a] border border-[#2e2e2e] text-white text-xs font-mono focus:outline-none focus:border-[#6366f1] transition-colors"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-[#a1a1a1]">Description (optional)</label>
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Auto-generated MVP by AI Solution Builder"
                className="w-full px-3 py-2 rounded-lg bg-[#0a0a0a] border border-[#2e2e2e] text-white text-xs focus:outline-none focus:border-[#6366f1] transition-colors"
              />
            </div>

            <div className="space-y-2.5 pt-1">
              <label className="flex items-start gap-2 text-xs text-[#a1a1a1] cursor-pointer">
                <input
                  type="checkbox"
                  checked={privateRepo}
                  onChange={(e) => setPrivateRepo(e.target.checked)}
                  className="mt-0.5 accent-[#6366f1] rounded"
                />
                <div>
                  <span className="font-medium text-white">Make repository private</span>
                  <p className="text-[11px] text-[#555] mt-0.5">
                    {privateRepo ? "Private repos require Vercel permissions." : "Public repo recommended for 1-click deployments."}
                  </p>
                </div>
              </label>
              <label className="flex items-center gap-2 text-xs text-[#a1a1a1] cursor-pointer">
                <input
                  type="checkbox"
                  checked={force}
                  onChange={(e) => setForce(e.target.checked)}
                  className="accent-[#6366f1] rounded"
                />
                Force redeploy if already pushed
              </label>
            </div>

            <div className="p-3 rounded-lg bg-[#161616] border border-[#242424] text-xs space-y-1">
              <div className="flex items-center gap-1.5 font-medium text-white">
                <Sparkles className="w-3.5 h-3.5 text-[#6366f1]" />
                <span>1-Click Deploy to GitHub &amp; Render</span>
              </div>
              <p className="text-[11px] text-[#666]">
                Pushes code to GitHub and auto-provisions on Render.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={onClose}
                className="px-3.5 py-2 rounded-lg bg-[#161616] hover:bg-[#1f1f1f] text-xs font-medium text-[#a1a1a1] border border-[#242424] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeploy}
                disabled={loading || !repoName.trim()}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-xs font-medium transition-colors disabled:opacity-40"
              >
                {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Rocket className="w-3.5 h-3.5" />}
                <span>{loading ? 'Deploying…' : 'Deploy Now'}</span>
              </button>
            </div>
          </>
        ) : (
          <div className="space-y-3 py-1">
            <div className="flex items-center gap-3 p-3.5 rounded-lg bg-[#22c55e10] border border-[#22c55e20] text-[#4ade80]">
              <Check className="w-4 h-4 shrink-0" />
              <div>
                <h4 className="text-xs font-semibold text-white">Deployment Successful</h4>
                <p className="text-[11px] text-[#a1a1a1] mt-0.5">Pushed to GitHub and configured for Render.</p>
              </div>
            </div>

            <div className="space-y-2">
              {(deployResult.frontend_url || deployResult.render_service_url) && (
                <a
                  href={(deployResult.frontend_url || deployResult.render_service_url)!}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between p-3 rounded-lg bg-[#161616] border border-[#242424] hover:border-[#2e2e2e] text-white transition-colors"
                >
                  <div className="flex items-center gap-2.5">
                    <Globe className="w-4 h-4 text-[#4ade80]" />
                    <div>
                      <span className="text-xs font-medium block">Frontend Application</span>
                      <span className="text-[11px] text-[#666] font-mono truncate max-w-xs block">
                        {deployResult.frontend_url || deployResult.render_service_url}
                      </span>
                    </div>
                  </div>
                  <ExternalLink className="w-3.5 h-3.5 text-[#555]" />
                </a>
              )}

              {deployResult.repo_url && (
                <a
                  href={deployResult.repo_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between p-3 rounded-lg bg-[#161616] border border-[#242424] hover:border-[#2e2e2e] text-white transition-colors"
                >
                  <div className="flex items-center gap-2.5 text-xs font-medium">
                    <Rocket className="w-3.5 h-3.5 text-[#6366f1]" />
                    <span>GitHub Repository:</span>
                    <span className="font-mono text-[#818cf8] truncate max-w-[200px]">{deployResult.repo_url}</span>
                  </div>
                  <ExternalLink className="w-3.5 h-3.5 text-[#555]" />
                </a>
              )}
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-xs font-medium transition-colors"
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 animate-fade-in">
      <div className="w-full max-w-md rounded-xl bg-[#111] border border-[#242424] p-6 space-y-4 shadow-2xl">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-[#6366f1]" />
            Tune Build #{build.build_number}
          </h3>
          <button onClick={onClose} className="text-[#555] hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <p className="text-[11px] text-[#f87171] bg-[#ef444410] border border-[#ef444420] rounded-lg p-3">{error}</p>
        )}

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-[#a1a1a1]">App Name (optional)</label>
          <input
            value={appName}
            onChange={(e) => setAppName(e.target.value)}
            placeholder="my-production-app"
            className="w-full px-3 py-2 rounded-lg bg-[#0a0a0a] border border-[#2e2e2e] text-white text-xs font-mono focus:outline-none focus:border-[#6366f1] transition-colors"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-medium text-[#a1a1a1]">Environment Overrides</label>
          <textarea
            value={envText}
            onChange={(e) => setEnvText(e.target.value)}
            rows={5}
            placeholder={'SECRET_KEY=change-me\nDATABASE_URL=...'}
            className="w-full px-3 py-2 rounded-lg bg-[#0a0a0a] border border-[#2e2e2e] text-white text-xs font-mono focus:outline-none focus:border-[#6366f1] transition-colors resize-none"
          />
          <p className="text-[11px] text-[#555]">One KEY=VALUE per line. Written to .env.local.</p>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-3.5 py-2 rounded-lg bg-[#161616] hover:bg-[#1f1f1f] text-xs font-medium text-[#a1a1a1] border border-[#242424] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfigure}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-xs font-medium transition-colors disabled:opacity-40"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
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
    <div className="p-4 rounded-xl bg-[#0a0a0a] border border-[#1a1a1a] space-y-3 transition-colors hover:border-[#242424]">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#161616] border border-[#242424] text-[#818cf8] flex items-center justify-center text-xs font-semibold">
            v{build.build_number}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-xs font-semibold text-white">Build #{build.build_number}</h4>
              <StatusBadge status={build.status} />
            </div>
            <p className="text-[11px] text-[#555] font-mono mt-0.5">
              {build.file_count} files · {build.build_id.slice(0, 8)}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {(build.frontend_url || build.render_service_url) && (
            <a
              href={(build.frontend_url || build.render_service_url)!}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-full badge badge-green text-[11px]"
            >
              <Globe className="w-3 h-3" />
              <span>Live App</span>
            </a>
          )}
          {build.repo_url && (
            <a
              href={build.repo_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 text-[11px] font-medium text-[#666] hover:text-white transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              <span>GitHub</span>
            </a>
          )}
        </div>
      </div>

      {build.error_message && (
        <p className="text-[11px] text-[#f87171] bg-[#ef444410] border border-[#ef444420] rounded-lg p-2 font-mono">
          {build.error_message}
        </p>
      )}

      <div className="flex items-center gap-2 flex-wrap pt-1">
        {build.status === 'complete' && (
          <>
            {(build.frontend_url || build.render_service_url) && (
              <a
                href={(build.frontend_url || build.render_service_url)!}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#22c55e10] hover:bg-[#22c55e20] text-[#4ade80] border border-[#22c55e20] text-xs font-medium transition-colors"
              >
                <Globe className="w-3.5 h-3.5" />
                <span>Open App</span>
              </a>
            )}

            {build.backend_url && (
              <a
                href={`${build.backend_url}/docs`}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#161616] hover:bg-[#1f1f1f] text-xs font-medium text-[#a1a1a1] border border-[#242424] transition-colors"
              >
                <Server className="w-3.5 h-3.5 text-[#6366f1]" />
                <span>API Docs</span>
              </a>
            )}

            <button
              onClick={onDownload}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#161616] hover:bg-[#1f1f1f] text-xs font-medium text-[#a1a1a1] border border-[#242424] transition-colors"
            >
              <Download className="w-3.5 h-3.5 text-[#6366f1]" />
              <span>Download ZIP</span>
            </button>
            <button
              onClick={onConfigure}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#161616] hover:bg-[#1f1f1f] text-xs font-medium text-[#a1a1a1] border border-[#242424] transition-colors"
            >
              <Settings2 className="w-3.5 h-3.5 text-[#6366f1]" />
              <span>Tune</span>
            </button>
            {!isDeployed && (
              <button
                onClick={onDeploy}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-xs font-medium transition-colors"
              >
                <Rocket className="w-3.5 h-3.5" />
                <span>Deploy</span>
              </button>
            )}

            {build.render_service_url && onDestroyPreview && (
              <button
                onClick={onDestroyPreview}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#ef444410] hover:bg-[#ef444420] text-xs font-medium text-[#f87171] border border-[#ef444420] transition-colors"
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
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#ef444410] hover:bg-[#ef444420] text-xs font-medium text-[#f87171] border border-[#ef444420] transition-colors"
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