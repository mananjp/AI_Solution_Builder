'use client';

import React, { useState } from 'react';
import {
  Box,
  Check,
  Download,
  ExternalLink,
  FolderTree,
  Loader2,
  Rocket,
  Settings2,
  Trash2,
  X,
} from 'lucide-react';
import { mvpApi } from '@/lib/api';
import { MVPBuild, MVPBuildStatus } from '@/types';

export const STATUS_STYLES: Record<MVPBuildStatus, string> = {
  queued: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 animate-pulse',
  pending: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  building: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30 animate-pulse',
  complete: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  failed: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  cancelled: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
};

export function StatusBadge({ status }: { status: MVPBuildStatus }) {
  return (
    <span
      className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider border ${STATUS_STYLES[status]}`}
    >
      {status}
    </span>
  );
}

function FileTree({ build }: { build: MVPBuild }) {
  const [open, setOpen] = useState(false);
  const files = build.files || [];

  return (
    <div className="pt-3 border-t border-white/5">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-[11px] font-semibold text-slate-300 hover:text-white transition-colors"
      >
        <FolderTree className="w-3.5 h-3.5 text-indigo-400" />
        <span>Generated Files ({build.file_count})</span>
        <span className="text-slate-500 font-mono">{open ? '▾' : '▸'}</span>
      </button>
      {open && (
        <div className="mt-2 max-h-64 overflow-y-auto rounded-xl bg-slate-950/70 border border-white/5 p-3">
          {files.length === 0 ? (
            <p className="text-[11px] text-slate-500 font-mono">No file tree returned yet.</p>
          ) : (
            <ul className="space-y-1">
              {files.map((f) => (
                <li key={f.path} className="flex items-center gap-2 text-[11px] font-mono">
                  <Box className="w-3 h-3 text-slate-600 flex-shrink-0" />
                  <span className={f.is_dir ? 'font-bold text-indigo-300' : 'text-slate-400'}>{f.path}</span>
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
  onDeployed: (repoUrl: string) => void;
}) {
  const [repoName, setRepoName] = useState(`mvp-${build.build_id.slice(0, 8)}`);
  const [description, setDescription] = useState('');
  const [privateRepo, setPrivateRepo] = useState(true);
  const [force, setForce] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      onDeployed(res.repo_url);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Deploy failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl bg-[#0e1424] border border-white/10 p-6 space-y-4 shadow-2xl">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Rocket className="w-4 h-4 text-indigo-400" />
            Deploy Build #{build.build_number}
          </h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <p className="text-[11px] text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl px-3 py-2">
            {error}
          </p>
        )}

        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-300">Repository Name</label>
          <input
            value={repoName}
            onChange={(e) => setRepoName(e.target.value)}
            className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-white/10 text-white text-xs font-mono focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-300">Description (optional)</label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Auto-generated MVP by AI Solution Builder"
            className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-white/10 text-white text-xs focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        <div className="space-y-2.5 pt-1">
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={privateRepo}
              onChange={(e) => setPrivateRepo(e.target.checked)}
              className="accent-indigo-500"
            />
            Private repository
          </label>
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={force}
              onChange={(e) => setForce(e.target.checked)}
              className="accent-indigo-500"
            />
            Force redeploy if already pushed
          </label>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-slate-300 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleDeploy}
            disabled={loading || !repoName.trim()}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white text-xs font-semibold shadow-lg shadow-indigo-600/25 transition-all hover:scale-105 disabled:opacity-40"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Rocket className="w-3.5 h-3.5" />}
            <span>Deploy to GitHub</span>
          </button>
        </div>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl bg-[#0e1424] border border-white/10 p-6 space-y-4 shadow-2xl">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-indigo-400" />
            Tune Build #{build.build_number}
          </h3>
          <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <p className="text-[11px] text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl px-3 py-2">{error}</p>
        )}

        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-300">App Name (optional)</label>
          <input
            value={appName}
            onChange={(e) => setAppName(e.target.value)}
            placeholder="my-production-app"
            className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-white/10 text-white text-xs font-mono focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-300">Environment Overrides</label>
          <textarea
            value={envText}
            onChange={(e) => setEnvText(e.target.value)}
            rows={6}
            placeholder={'SECRET_KEY=change-me\nDATABASE_URL=...'}
            className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-white/10 text-white text-xs font-mono focus:outline-none focus:border-indigo-500 transition-colors resize-none"
          />
          <p className="text-[11px] text-slate-500">One KEY=VALUE per line. Written to .env.local.</p>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-slate-300 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfigure}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white text-xs font-semibold shadow-lg shadow-indigo-600/25 transition-all hover:scale-105 disabled:opacity-40"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
            <span>Apply Overlay</span>
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
}: {
  build: MVPBuild;
  isDeployed: boolean;
  onDeploy: () => void;
  onConfigure: () => void;
  onDownload: () => void;
  onDestroy: () => void;
}) {
  return (
    <div className="p-5 rounded-2xl bg-slate-900/40 border border-white/5 space-y-3 transition-all hover:border-white/10">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-indigo-500/15 border border-indigo-500/20 text-indigo-300 flex items-center justify-center text-xs font-bold">
            v{build.build_number}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-bold text-white">Build #{build.build_number}</h4>
              <StatusBadge status={build.status} />
            </div>
            <p className="text-[11px] text-slate-500 font-mono mt-0.5">
              {build.file_count} files · {build.build_id.slice(0, 8)}
            </p>
          </div>
        </div>

        {build.repo_url && (
          <a
            href={build.repo_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            <ExternalLink className="w-3 h-3" />
            <span>Deployed</span>
          </a>
        )}
      </div>

      {build.error_message && (
        <p className="text-[11px] text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl px-3 py-2 font-mono">
          {build.error_message}
        </p>
      )}

      <div className="flex items-center gap-2 flex-wrap">
        {build.status === 'complete' && (
          <>
            <button
              onClick={onDownload}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-slate-200 border border-white/10 transition-colors"
            >
              <Download className="w-3.5 h-3.5 text-indigo-400" />
              <span>Download ZIP</span>
            </button>
            <button
              onClick={onConfigure}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-slate-200 border border-white/10 transition-colors"
            >
              <Settings2 className="w-3.5 h-3.5 text-cyan-400" />
              <span>Tune</span>
            </button>
            <button
              onClick={onDeploy}
              disabled={isDeployed}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all hover:scale-105 disabled:opacity-40"
            >
              <Rocket className="w-3.5 h-3.5" />
              <span>{isDeployed ? 'Deployed' : 'Deploy to GitHub'}</span>
            </button>
          </>
        )}
        {(build.status === 'failed' || build.status === 'cancelled') && (
          <button
            onClick={onDestroy}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-xs font-semibold text-rose-400 border border-rose-500/20 transition-colors"
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