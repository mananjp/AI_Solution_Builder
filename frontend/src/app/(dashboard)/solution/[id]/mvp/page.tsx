'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  ArrowRight,
  Box,
  Check,
  Download,
  ExternalLink,
  FolderTree,
  Loader2,
  Play,
  RefreshCw,
  Rocket,
  Settings2,
  Trash2,
  X,
} from 'lucide-react';
import { mvpApi, solutionApi } from '@/lib/api';
import { MVPBuild, MVPBuildStatus, MVPTemplate, Solution } from '@/types';

const STATUS_STYLES: Record<MVPBuildStatus, string> = {
  queued: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30 animate-pulse',
  pending: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  building: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30 animate-pulse',
  complete: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  failed: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  cancelled: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
};

const SAMPLE_TEMPLATES: MVPTemplate[] = [
  {
    slug: 'todo',
    title: 'Todo List Workspace',
    description: 'A minimal single-module CRUD app — items, tags, and completion states.',
    app_name: 'todo-app',
    industry: 'Productivity',
  },
  {
    slug: 'calculator',
    title: 'Calculator',
    description: 'A simple interactive calculator with a persistent history ledger.',
    app_name: 'calculator',
    industry: 'Utilities',
  },
  {
    slug: 'portfolio',
    title: 'Portfolio Site',
    description: 'A public-facing portfolio with project showcases and contact forms.',
    app_name: 'portfolio',
    industry: 'Web',
  },
];

function StatusBadge({ status }: { status: MVPBuildStatus }) {
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

function DeployModal({
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

function ConfigureModal({
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

function BuildCard({
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

export default function MvpPage() {
  const params = useParams();
  const solutionId = (params?.id as string) || 'sol-demo-1';

  const [solution, setSolution] = useState<Solution | null>(null);
  const [templates, setTemplates] = useState<MVPTemplate[]>([]);
  const [builds, setBuilds] = useState<MVPBuild[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>('todo');
  const [appName, setAppName] = useState('');
  const [forceBuild, setForceBuild] = useState(false);
  const [starting, setStarting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deployTarget, setDeployTarget] = useState<MVPBuild | null>(null);
  const [configureTarget, setConfigureTarget] = useState<MVPBuild | null>(null);

  const loadBuilds = useCallback(async () => {
    try {
      setBuilds(await mvpApi.listBuilds(solutionId));
    } catch {
      // backend unavailable — keep current list
    }
  }, [solutionId]);

  useEffect(() => {
    solutionApi
      .get(solutionId)
      .then(setSolution)
      .catch(() => {
        setSolution({
          id: solutionId,
          workspace_id: 'ws-demo-1',
          title: 'Omnichannel Retail POS & Inventory Platform',
          description: 'Enterprise architecture generated by AI Solution Builder.',
          status: 'complete',
          created_at: new Date().toISOString(),
        });
      });
  }, [solutionId]);

  useEffect(() => {
    mvpApi
      .listTemplates()
      .then(setTemplates)
      .catch(() => setTemplates(SAMPLE_TEMPLATES));
  }, []);

  useEffect(() => {
    let cancelled = false;
    mvpApi
      .listBuilds(solutionId)
      .then((list) => {
        if (!cancelled) setBuilds(list);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [solutionId]);

  // Poll builds while any is active
  useEffect(() => {
    const hasActive = builds.some(
      (b) => b.status === 'pending' || b.status === 'queued' || b.status === 'building'
    );
    if (!hasActive) return;
    const timer = setInterval(loadBuilds, 3000);
    return () => clearInterval(timer);
  }, [builds, loadBuilds]);

  const handleStartBuild = async () => {
    setStarting(true);
    setActionError(null);
    try {
      await mvpApi.triggerBuild(solutionId, {
        app_name: appName.trim() || undefined,
        template: selectedTemplate || undefined,
        force: forceBuild,
      });
      setAppName('');
      await loadBuilds();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to start build.');
    } finally {
      setStarting(false);
    }
  };

  const handleDownload = async (build: MVPBuild) => {
    try {
      await mvpApi.downloadBuild(build.build_id, `mvp_${build.solution_id.slice(0, 8)}_build${build.build_number}.zip`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Download failed.');
    }
  };

  const handleDestroy = async (build: MVPBuild) => {
    if (!window.confirm(`Destroy build #${build.build_number}? The workspace will be deleted.`)) return;
    try {
      await mvpApi.destroy(build.build_id);
      await loadBuilds();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Destroy failed.');
    }
  };

  const handleDeployed = (repoUrl: string) => {
    setBuilds((prev) => prev.map((b) => (b.status === 'complete' && b.build_id === deployTarget?.build_id ? { ...b, repo_url: repoUrl } : b)));
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Link
          href={`/solution/${solutionId}`}
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Blueprints</span>
        </Link>

        <div className="flex items-center gap-2 text-[11px] text-slate-500">
          <span>Deploy prep:</span>
          <Link
            href="/settings"
            className="px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 font-semibold border border-white/10 transition-colors"
          >
            Save GitHub Token
          </Link>
        </div>
      </div>

      {/* Hero */}
      <div className="p-8 rounded-3xl bg-gradient-to-r from-indigo-950/60 via-slate-900/80 to-purple-950/40 border border-white/5 shadow-2xl relative overflow-hidden">
        <div className="relative z-10 space-y-2 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold">
            <Rocket className="w-3.5 h-3.5 text-indigo-400" />
            <span>OpenCode MVP Builder</span>
          </div>
          <h2 className="text-2xl font-extrabold text-white tracking-tight">
            Build a Deployable App from {solution?.title || 'this Solution'}
          </h2>
          <p className="text-xs text-slate-300 leading-relaxed">
            Generate a working FastAPI + Next.js project from your validated blueprints, then push it straight to a fresh
            GitHub repo ready for a Render blueprint auto-deploy.
          </p>
        </div>
      </div>

      {/* Start New Build */}
      <div className="p-6 rounded-2xl bg-slate-900/40 border border-white/5 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Play className="w-4 h-4 text-emerald-400" />
              <span>Start a New Build</span>
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Pick a starter template and the full-blueprint slot-fill takes care of the rest. Costs MVP-build credits.
            </p>
          </div>
          <button
            onClick={loadBuilds}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-[11px] font-semibold text-slate-300 border border-white/10 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Refresh</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {templates.map((tpl) => {
            const selected = selectedTemplate === tpl.slug;
            return (
              <button
                key={tpl.slug}
                onClick={() => setSelectedTemplate(selected ? null : tpl.slug)}
                className={`p-5 rounded-2xl border text-left transition-all ${
                  selected
                    ? 'bg-indigo-950/40 border-indigo-500/50 shadow-lg shadow-indigo-500/10'
                    : 'bg-slate-900/60 border-white/5 hover:border-white/15'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">{tpl.title}</span>
                  {selected && <Check className="w-4 h-4 text-indigo-400" />}
                </div>
                <p className="text-[11px] text-slate-400 mt-1.5 leading-relaxed">{tpl.description}</p>
                <div className="mt-3 flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-semibold text-slate-400">
                    {tpl.industry}
                  </span>
                  <code className="text-[10px] text-indigo-300 font-mono">{tpl.app_name}</code>
                </div>
              </button>
            );
          })}
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-end gap-3">
          <div className="flex-1 space-y-1.5">
            <label className="text-xs font-semibold text-slate-300">App Name (optional)</label>
            <input
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
              placeholder={`e.g. ${templates[0]?.app_name || 'my-app'}`}
              className="w-full px-4 py-3 rounded-xl bg-slate-900 border border-white/10 text-white text-xs font-mono focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-300 pb-3 cursor-pointer">
            <input
              type="checkbox"
              checked={forceBuild}
              onChange={(e) => setForceBuild(e.target.checked)}
              className="accent-indigo-500"
            />
            Force (solution not yet complete)
          </label>
          <button
            onClick={handleStartBuild}
            disabled={starting || (!selectedTemplate && !appName.trim())}
            className="flex items-center gap-2 px-7 py-3 rounded-xl bg-gradient-to-r from-indigo-600 via-purple-600 to-cyan-500 hover:opacity-95 text-white text-xs font-bold shadow-xl shadow-indigo-600/30 transition-all hover:scale-105 disabled:opacity-40"
          >
            {starting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
            <span>Start MVP Build</span>
          </button>
        </div>

        {actionError && (
          <p className="text-[11px] text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl px-3 py-2">{actionError}</p>
        )}
      </div>

      {/* Builds */}
      <div className="space-y-4">
        <div>
          <h3 className="text-base font-bold text-white">Builds</h3>
          <p className="text-xs text-slate-500 mt-0.5">
            {builds.length} build{builds.length === 1 ? '' : 's'} for this solution. Status refreshes automatically while
            building.
          </p>
        </div>

        {builds.length === 0 ? (
          <div className="p-10 rounded-2xl bg-slate-900/40 border border-dashed border-white/10 text-center">
            <Rocket className="w-8 h-8 text-slate-600 mx-auto mb-2" />
            <p className="text-xs text-slate-500">No builds yet — start your first MVP build above.</p>
          </div>
        ) : (
          builds.map((build) => (
            <BuildCard
              key={build.build_id}
              build={build}
              isDeployed={Boolean(build.repo_url)}
              onDeploy={() => setDeployTarget(build)}
              onConfigure={() => setConfigureTarget(build)}
              onDownload={() => handleDownload(build)}
              onDestroy={() => handleDestroy(build)}
            />
          ))
        )}
      </div>

      {deployTarget && <DeployModal build={deployTarget} onClose={() => setDeployTarget(null)} onDeployed={handleDeployed} />}
      {configureTarget && (
        <ConfigureModal build={configureTarget} onClose={() => setConfigureTarget(null)} onConfigured={loadBuilds} />
      )}

      {/* Footer CTA */}
      <div className="flex justify-end">
        <Link
          href="/chat"
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-slate-300 border border-white/10 transition-colors"
        >
          <span>Iterate Blueprints with AI</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  );
}