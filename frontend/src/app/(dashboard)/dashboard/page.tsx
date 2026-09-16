'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Sparkles,
  Plus,
  Layers,
  FolderKanban,
  Clock,
  ArrowUpRight,
  Trash2,
  Compass,
  Rocket,
  Zap,
  Wrench,
  Loader2,
  CircleCheck,
  Radio,
  RefreshCw,
} from 'lucide-react';
import { workspaceApi, solutionApi, mvpApi, opencodeApi } from '@/lib/api';
import { Solution, Workspace, MVPBuild, MVPTemplate, MVPDeployResult } from '@/types';
import { BuildCard, ConfigureModal, DeployModal } from '@/components/mvp/BuildCard';

const QUICK_TEMPLATES: MVPTemplate[] = [
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

export default function DashboardPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('');

  const [sidecarHealthy, setSidecarHealthy] = useState<boolean | null>(null);
  const [builds, setBuilds] = useState<MVPBuild[]>([]);
  const [templates, setTemplates] = useState<MVPTemplate[]>(QUICK_TEMPLATES);
  const [buildingTemplate, setBuildingTemplate] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deployTarget, setDeployTarget] = useState<MVPBuild | null>(null);
  const [configureTarget, setConfigureTarget] = useState<MVPBuild | null>(null);

  // New Workspace form state
  const [newWsName, setNewWsName] = useState('');
  const [creatingWs, setCreatingWs] = useState(false);

  useEffect(() => {
    async function loadData() {
      try {
        const wsList = await workspaceApi.list();
        if (wsList && wsList.length > 0) {
          setWorkspaces(wsList);
          setSelectedWorkspace(wsList[0].id);
          const solList = await solutionApi.list(wsList[0].id);
          setSolutions(solList);
        } else {
          try {
            const defaultWs = await workspaceApi.create({
              name: 'Primary Enterprise Systems',
              description: 'Flagship product architecture and engineering specs',
            });
            setWorkspaces([defaultWs]);
            setSelectedWorkspace(defaultWs.id);
          } catch {
            setWorkspaces([
              { id: 'ws-demo-1', org_id: 'org-1', name: 'Primary Enterprise Systems', description: 'Core product architecture', created_at: new Date().toISOString() }
            ]);
            setSelectedWorkspace('ws-demo-1');
          }
        }
      } catch {
        setWorkspaces([
          { id: 'ws-demo-1', org_id: 'org-1', name: 'Primary Enterprise Systems', description: 'Flagship product architecture and engineering specs', created_at: new Date().toISOString() }
        ]);
        setSelectedWorkspace('ws-demo-1');
        setSolutions([
          {
            id: 'sol-demo-1',
            workspace_id: 'ws-demo-1',
            title: 'Omnichannel Retail POS & Inventory Platform',
            description: 'Multi-store point-of-sale with real-time stock sync, offline barcode scanning, and staff scheduling.',
            status: 'complete',
            created_at: new Date().toISOString(),
          },
          {
            id: 'sol-demo-2',
            workspace_id: 'ws-demo-1',
            title: 'HIPAA-Compliant Telehealth & EHR Portal',
            description: 'Doctor appointments, encrypted WebRTC consultations, prescription workflow, and audit logging.',
            status: 'complete',
            created_at: new Date().toISOString(),
          }
        ]);
      }
    }
    loadData();
  }, []);

  // Probe the OpenCode sidecar for the dashboard banner.
  useEffect(() => {
    opencodeApi
      .health()
      .then((res) => setSidecarHealthy(Boolean(res.healthy)))
      .catch(() => setSidecarHealthy(false));
  }, []);

  // Load premade templates + any builds created from them.
  useEffect(() => {
    mvpApi
      .listTemplates()
      .then((list) => {
        if (list && list.length > 0) setTemplates(list);
      })
      .catch(() => undefined);
  }, []);

  // Poll the latest quick-build status while any build is still active.
  useEffect(() => {
    const activeBuildIds = builds
      .filter((b) => b.status === 'queued' || b.status === 'pending' || b.status === 'building')
      .map((b) => b.build_id);
    if (activeBuildIds.length === 0) return;
    const timer = setInterval(async () => {
      for (const buildId of activeBuildIds) {
        try {
          const fresh = await mvpApi.getStatus(buildId);
          setBuilds((prev) => prev.map((b) => (b.build_id === buildId ? fresh : b)));
        } catch {
          // ignore transient failures; next poll will retry
        }
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [builds]);

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setCreatingWs(true);
    try {
      const created = await workspaceApi.create({ name: newWsName });
      setWorkspaces([...workspaces, created]);
      setSelectedWorkspace(created.id);
      setNewWsName('');
    } catch {
      const mockWs: Workspace = {
        id: `ws-${Date.now()}`,
        org_id: 'demo-org',
        name: newWsName,
        created_at: new Date().toISOString(),
      };
      setWorkspaces([...workspaces, mockWs]);
      setSelectedWorkspace(mockWs.id);
      setNewWsName('');
    } finally {
      setCreatingWs(false);
    }
  };

  const handleDeleteSolution = async (id: string) => {
    try {
      await solutionApi.delete(id);
      setSolutions(solutions.filter(s => s.id !== id));
    } catch {
      setSolutions(solutions.filter(s => s.id !== id));
    }
  };

  const handleQuickBuild = async (template: MVPTemplate) => {
    setBuildingTemplate(template.slug);
    setActionError(null);
    try {
      const build = await mvpApi.quickBuild({
        template: template.slug,
        app_name: template.app_name,
      });
      setBuilds((prev) => [build, ...prev]);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to start quick build.');
    } finally {
      setBuildingTemplate(null);
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
      setBuilds((prev) => prev.filter((b) => b.build_id !== build.build_id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Destroy failed.');
    }
  };

  const handleDeployed = (result: MVPDeployResult | string) => {
    const repoUrl = typeof result === 'string' ? result : result.repo_url;
    const renderUrl = typeof result === 'string' ? null : result.render_service_url;
    const renderDash = typeof result === 'string' ? null : result.render_dashboard_url;
    const renderDeploy = typeof result === 'string' ? null : result.render_deploy_url;
    setBuilds((prev) =>
      prev.map((b) =>
        b.status === 'complete' && b.build_id === deployTarget?.build_id
          ? {
              ...b,
              repo_url: repoUrl,
              render_service_url: renderUrl,
              render_dashboard_url: renderDash,
              render_deploy_url: renderDeploy,
            }
          : b
      )
    );
  };

  return (
    <div className="space-y-8">
      {/* Top Banner */}
      <div className="relative p-8 rounded-3xl bg-gradient-to-r from-indigo-950/60 via-slate-900/80 to-purple-950/40 border border-white/5 overflow-hidden shadow-2xl">
        <div className="relative z-10 max-w-2xl space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>AI Solution Builder</span>
          </div>
          <h2 className="text-3xl font-extrabold text-white tracking-tight">
            Build Working Apps in Two Ways
          </h2>
          <p className="text-sm text-slate-300 leading-relaxed">
            Spin up a production-grade app from a premade template in one click, or chat
            directly with the AI developer to design something completely custom.
          </p>
          <div className="pt-2 flex flex-wrap items-center gap-3">
            <Link
              href="/chat"
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-200 text-xs font-semibold transition-colors"
            >
              <Wrench className="w-4 h-4 text-indigo-400" />
              <span>Custom App Builder</span>
            </Link>
          </div>
        </div>

        {/* Ambient background decoration */}
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-gradient-to-l from-indigo-500/10 to-transparent pointer-events-none" />
      </div>

      {/* Sidecar health banner */}
      {sidecarHealthy !== null && (
        <div
          className={`flex items-center gap-3 px-5 py-3.5 rounded-2xl border transition-colors ${
            sidecarHealthy
              ? 'bg-emerald-950/30 border-emerald-500/30 text-emerald-300'
              : 'bg-amber-950/30 border-amber-500/30 text-amber-300'
          }`}
        >
          {sidecarHealthy ? (
            <CircleCheck className="w-4 h-4 flex-shrink-0" />
          ) : (
            <Radio className="w-4 h-4 flex-shrink-0 animate-pulse" />
          )}
          <p className="text-xs font-medium">
            {sidecarHealthy
              ? 'AI build engine is online. Custom builds and premade app builds are ready to go.'
              : 'The AI build engine is unreachable. You can still design blueprints, but app builds may be delayed.'}
          </p>
        </div>
      )}

      {/* Two-Path Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Path 1: Premade Apps */}
        <div className="p-6 rounded-2xl bg-slate-900/40 border border-white/5 space-y-5" id="premade">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Zap className="w-4 h-4 text-cyan-400" />
                <span>Premade Apps</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                One-click builds from polished templates. Scaffolded, verified, and ready to download or deploy.
              </p>
            </div>
            <button
              onClick={async () => {
                const refreshed: MVPBuild[] = [];
                for (const build of builds) {
                  try {
                    refreshed.push(await mvpApi.getStatus(build.build_id));
                  } catch {
                    refreshed.push(build);
                  }
                }
                if (refreshed.length > 0) setBuilds(refreshed);
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-[11px] font-semibold text-slate-300 border border-white/10 transition-colors"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Refresh</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {templates.map((tpl) => (
              <div
                key={tpl.slug}
                className="p-4 rounded-2xl bg-slate-950/40 border border-white/5 hover:border-cyan-500/30 transition-all flex flex-col gap-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">{tpl.title}</span>
                  <span className="px-2 py-0.5 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-[10px] font-semibold text-cyan-300">
                    {tpl.industry}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed flex-1">{tpl.description}</p>
                <button
                  onClick={() => handleQuickBuild(tpl)}
                  disabled={buildingTemplate !== null}
                  className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-cyan-600/20 transition-all hover:scale-[1.02] disabled:opacity-40 disabled:hover:scale-100"
                >
                  {buildingTemplate === tpl.slug ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Starting build...</span>
                    </>
                  ) : (
                    <>
                      <Rocket className="w-3.5 h-3.5" />
                      <span>Build App</span>
                    </>
                  )}
                </button>
              </div>
            ))}
          </div>

          {actionError && (
            <p className="text-[11px] text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl px-3 py-2">
              {actionError}
            </p>
          )}

          {builds.length > 0 && (
            <div className="space-y-4 pt-2 border-t border-white/5">
              <h4 className="text-sm font-bold text-white">Your Quick Builds</h4>
              {builds.map((build) => (
                <BuildCard
                  key={build.build_id}
                  build={build}
                  isDeployed={Boolean(build.repo_url)}
                  onDeploy={() => setDeployTarget(build)}
                  onConfigure={() => setConfigureTarget(build)}
                  onDownload={() => handleDownload(build)}
                  onDestroy={() => handleDestroy(build)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Path 2: Custom App Builder */}
        <div className="p-6 rounded-2xl bg-gradient-to-br from-indigo-950/40 to-slate-900/60 border border-indigo-500/20 space-y-5 flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Wrench className="w-5 h-5 text-indigo-400" />
              <h3 className="text-base font-bold text-white">Custom App Builder</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Skip the templates. Chat directly with the AI developer — describe your idea, iterate
              on the scaffolded FastAPI + Next.js workspace, and finalize a build when you are happy.
            </p>
            <ul className="space-y-2 pt-1">
              {[
                'Persistent conversational session per build',
                'Live editing of your FastAPI + Next.js workspace',
                'Upload a spec or PRD for context',
                'Finalize, download, tune, or deploy to GitHub',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2 text-[11px] text-slate-300">
                  <CircleCheck className="w-3.5 h-3.5 text-emerald-400 mt-0.5 flex-shrink-0" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          <Link
            href="/chat"
            className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-indigo-600 via-purple-600 to-cyan-500 hover:opacity-95 text-white text-xs font-bold shadow-xl shadow-indigo-600/30 transition-all hover:scale-[1.02]"
          >
            <Sparkles className="w-4 h-4" />
            <span>Open Custom App Builder</span>
            <ArrowUpRight className="w-4 h-4" />
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-slate-900/40 border border-white/5 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-400 font-medium">Active Solutions</p>
            <p className="text-2xl font-bold text-white mt-1">{solutions.length}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <Layers className="w-5 h-5" />
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/40 border border-white/5 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-400 font-medium">Workspaces</p>
            <p className="text-2xl font-bold text-white mt-1">{workspaces.length}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
            <FolderKanban className="w-5 h-5" />
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/40 border border-white/5 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-400 font-medium">Premade App Builds</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">{builds.length}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Rocket className="w-5 h-5" />
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/40 border border-white/5 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-400 font-medium">AI Build Engine</p>
            <p className="text-2xl font-bold text-indigo-400 mt-1">
              {sidecarHealthy === null ? '…' : sidecarHealthy ? 'Online' : 'Offline'}
            </p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <Radio className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Solutions Section */}
      <div className="space-y-4" id="blueprints">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-white">Generated Solution Blueprints</h3>
            <p className="text-xs text-slate-400 mt-0.5">Explore full architecture specs, database schemas, and roadmaps</p>
          </div>
          <Link
            href="/chat"
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-indigo-400 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Generate New</span>
          </Link>
        </div>

        {solutions.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {solutions.map((solution) => (
              <div
                key={solution.id}
                className="p-5 rounded-2xl bg-slate-900/40 border border-white/5 hover:border-indigo-500/30 transition-all flex flex-col justify-between group"
              >
                <div>
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <span className="text-[11px] px-2.5 py-0.5 rounded-full font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      {solution.status.toUpperCase()}
                    </span>
                    <button
                      onClick={() => handleDeleteSolution(solution.id)}
                      className="text-slate-500 hover:text-rose-400 transition-colors p-1"
                      title="Delete solution"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  <h4 className="text-base font-bold text-white group-hover:text-indigo-300 transition-colors">
                    {solution.title}
                  </h4>
                  <p className="text-xs text-slate-400 mt-1.5 line-clamp-2 leading-relaxed">
                    {solution.description || 'Enterprise solution blueprint with architecture, schemas, and roadmap.'}
                  </p>
                </div>

                <div className="mt-5 pt-4 border-t border-white/5 flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{new Date(solution.created_at).toLocaleDateString()}</span>
                  </div>

                  <Link
                    href={`/solution/${solution.id}`}
                    className="flex items-center gap-1.5 text-xs font-semibold text-indigo-400 hover:text-indigo-300 group-hover:translate-x-0.5 transition-transform"
                  >
                    <span>View Blueprints</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-12 text-center rounded-2xl bg-slate-900/20 border border-dashed border-white/10 space-y-3">
            <Layers className="w-10 h-10 text-slate-600 mx-auto" />
            <h4 className="text-sm font-semibold text-slate-300">No solutions generated yet</h4>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Build a premade app above, or start a custom session with the AI developer.
            </p>
            <Link
              href="/chat"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 hover:bg-indigo-500 transition-all"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Start Building</span>
            </Link>
          </div>
        )}
      </div>

      {/* Workspaces & Industry Templates Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 pt-4">
        {/* Workspace Manager */}
        <div className="p-6 rounded-2xl bg-slate-900/40 border border-white/5 space-y-4" id="workspaces">
          <h4 className="font-bold text-white text-sm flex items-center gap-2">
            <FolderKanban className="w-4 h-4 text-cyan-400" />
            <span>Workspaces</span>
          </h4>
          <p className="text-xs text-slate-400">Organize your software solutions by product line or client.</p>

          <form onSubmit={handleCreateWorkspace} className="flex gap-2">
            <input
              type="text"
              value={newWsName}
              onChange={(e) => setNewWsName(e.target.value)}
              placeholder="New workspace name..."
              className="flex-1 px-3 py-2 rounded-xl bg-slate-950 border border-white/10 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-indigo-500"
            />
            <button
              type="submit"
              disabled={creatingWs || !newWsName.trim()}
              className="px-3 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition-colors disabled:opacity-40"
            >
              Add
            </button>
          </form>

          <div className="space-y-2 pt-2">
            {workspaces.map((ws) => (
              <div
                key={ws.id}
                onClick={() => setSelectedWorkspace(ws.id)}
                className={`p-3 rounded-xl border text-xs cursor-pointer transition-all ${
                  selectedWorkspace === ws.id
                    ? 'bg-indigo-950/30 border-indigo-500/50 text-indigo-300'
                    : 'bg-white/[0.02] border-white/5 text-slate-400 hover:border-white/10'
                }`}
              >
                <div className="font-semibold text-slate-200">{ws.name}</div>
                {ws.description && <div className="text-[11px] text-slate-500 mt-0.5">{ws.description}</div>}
              </div>
            ))}
          </div>
        </div>

        {/* Industry Templates Quickstart */}
        <div className="lg:col-span-2 p-6 rounded-2xl bg-slate-900/40 border border-white/5 space-y-4" id="templates">
          <h4 className="font-bold text-white text-sm flex items-center gap-2">
            <Compass className="w-4 h-4 text-purple-400" />
            <span>Blueprints by Industry</span>
          </h4>
          <p className="text-xs text-slate-400">Pre-seeded vertical prompts to kick off a custom architecture session.</p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            {[
              {
                title: 'Retail & Omnichannel Commerce',
                desc: 'Point-of-Sale, Real-time Stock Sync, Multi-Store, Customer Loyalty Engine',
                prompt: 'I want to build an omnichannel retail system with inventory management, POS terminal support, and loyalty rewards.',
              },
              {
                title: 'Healthcare EHR & Telemedicine',
                desc: 'HIPAA Patient Portal, Encrypted Video Consults, Digital Prescriptions, Audit Trails',
                prompt: 'I want to build a telemedicine platform with HIPAA compliance, scheduling, WebRTC video, and electronic health records.',
              },
              {
                title: 'Logistics & Fleet Dispatch',
                desc: 'Live GPS Tracking, Route Optimization, Driver Mobile Apps, POD Scanning',
                prompt: 'I want to build a freight dispatch system with automated route planning, live driver tracking, and digital proof of delivery.',
              },
              {
                title: 'B2B SaaS Multi-Tenant Platform',
                desc: 'RBAC Authorization, Usage Metering, Stripe Invoicing, Team Workspaces',
                prompt: 'I want to build a multi-tenant B2B SaaS platform with organization billing, role-based access, and audit logs.',
              },
            ].map((t, idx) => (
              <Link
                key={idx}
                href={`/chat?prompt=${encodeURIComponent(t.prompt)}`}
                className="p-4 rounded-xl bg-white/[0.02] hover:bg-indigo-950/20 border border-white/5 hover:border-indigo-500/30 transition-all text-left group"
              >
                <h5 className="font-semibold text-xs text-white group-hover:text-indigo-300 transition-colors">
                  {t.title}
                </h5>
                <p className="text-[11px] text-slate-400 mt-1 leading-relaxed">{t.desc}</p>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {deployTarget && <DeployModal build={deployTarget} onClose={() => setDeployTarget(null)} onDeployed={handleDeployed} />}
      {configureTarget && (
        <ConfigureModal build={configureTarget} onClose={() => setConfigureTarget(null)} onConfigured={() => undefined} />
      )}
    </div>
  );
}