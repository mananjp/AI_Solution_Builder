'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Plus, Layers, FolderKanban, Clock, ArrowUpRight, Trash2,
  Compass, Rocket, Zap, Wrench, Loader2, RefreshCw, Circle,
} from 'lucide-react';
import { workspaceApi, solutionApi, mvpApi, opencodeApi } from '@/lib/api';
import { Solution, Workspace, MVPBuild, MVPTemplate, MVPDeployResult } from '@/types';
import { BuildCard, ConfigureModal, DeployModal } from '@/components/mvp/BuildCard';

const FALLBACK_TEMPLATES: MVPTemplate[] = [
  { slug: 'todo', title: 'Todo List', description: 'Simple CRUD app with items, tags, and completion states.', app_name: 'todo-app', industry: 'Productivity' },
  { slug: 'calculator', title: 'Calculator', description: 'Interactive calculator with a persistent history ledger.', app_name: 'calculator', industry: 'Utilities' },
  { slug: 'portfolio', title: 'Portfolio Site', description: 'Public portfolio with project showcases and a contact form.', app_name: 'portfolio', industry: 'Web' },
];

const INDUSTRY_PROMPTS = [
  {
    title: 'Retail & Omnichannel Commerce',
    desc: 'POS, real-time stock sync, multi-store, loyalty engine',
    prompt: 'I want to build an omnichannel retail system with inventory management, POS terminal support, and loyalty rewards.',
  },
  {
    title: 'Healthcare EHR & Telemedicine',
    desc: 'HIPAA patient portal, video consults, prescriptions, audit trails',
    prompt: 'I want to build a telemedicine platform with HIPAA compliance, scheduling, WebRTC video, and electronic health records.',
  },
  {
    title: 'Logistics & Fleet Dispatch',
    desc: 'Live GPS tracking, route optimization, driver apps, POD scanning',
    prompt: 'I want to build a freight dispatch system with automated route planning, live driver tracking, and digital proof of delivery.',
  },
  {
    title: 'B2B SaaS Multi-Tenant Platform',
    desc: 'RBAC, usage metering, Stripe invoicing, team workspaces',
    prompt: 'I want to build a multi-tenant B2B SaaS platform with organization billing, role-based access, and audit logs.',
  },
];

export default function DashboardPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState('');
  const [engineOnline, setEngineOnline] = useState<boolean | null>(null);
  const [builds, setBuilds] = useState<MVPBuild[]>([]);
  const [templates, setTemplates] = useState<MVPTemplate[]>(FALLBACK_TEMPLATES);
  const [buildingSlug, setBuildingSlug] = useState<string | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const [deployTarget, setDeployTarget] = useState<MVPBuild | null>(null);
  const [configureTarget, setConfigureTarget] = useState<MVPBuild | null>(null);
  const [newWsName, setNewWsName] = useState('');
  const [creatingWs, setCreatingWs] = useState(false);

  // Load workspaces + solutions
  useEffect(() => {
    async function load() {
      try {
        const wsList = await workspaceApi.list();
        if (wsList?.length > 0) {
          setWorkspaces(wsList);
          setSelectedWorkspace(wsList[0].id);
          const sols = await solutionApi.list(wsList[0].id);
          setSolutions(sols);
        } else {
          const ws = await workspaceApi.create({ name: 'Primary Workspace', description: 'Core architecture zone' });
          setWorkspaces([ws]);
          setSelectedWorkspace(ws.id);
        }
      } catch {
        const demoWs = { id: 'ws-demo', org_id: 'demo-org', name: 'Primary Workspace', description: 'Core architecture zone', created_at: new Date().toISOString() };
        setWorkspaces([demoWs]);
        setSelectedWorkspace('ws-demo');
        setSolutions([
          { id: 'sol-1', workspace_id: 'ws-demo', title: 'Omnichannel Retail POS & Inventory', description: 'Multi-store POS with real-time stock sync, offline barcode scanning, and staff scheduling.', status: 'complete', created_at: new Date().toISOString() },
          { id: 'sol-2', workspace_id: 'ws-demo', title: 'HIPAA-Compliant Telehealth & EHR Portal', description: 'Doctor appointments, encrypted WebRTC consultations, prescription workflow, and audit logging.', status: 'complete', created_at: new Date().toISOString() },
        ]);
      }
    }
    load();
  }, []);

  // Ping engine
  useEffect(() => {
    let mounted = true;
    const check = () => opencodeApi.health()
      .then((r) => { if (mounted) setEngineOnline(Boolean(r.healthy)); })
      .catch(() => { if (mounted) setEngineOnline(false); });
    check();
    const t = setInterval(check, 15000);
    return () => { mounted = false; clearInterval(t); };
  }, []);

  // Load templates
  useEffect(() => {
    mvpApi.listTemplates().then((l) => { if (l?.length > 0) setTemplates(l); }).catch(() => undefined);
  }, []);

  // Poll active builds
  useEffect(() => {
    const active = builds.filter((b) => ['queued', 'pending', 'building'].includes(b.status)).map((b) => b.build_id);
    if (!active.length) return;
    const t = setInterval(async () => {
      for (const id of active) {
        try {
          const fresh = await mvpApi.getStatus(id);
          setBuilds((p) => p.map((b) => (b.build_id === id ? fresh : b)));
        } catch { /* ignore */ }
      }
    }, 3000);
    return () => clearInterval(t);
  }, [builds]);

  const handleCreateWs = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setCreatingWs(true);
    try {
      const ws = await workspaceApi.create({ name: newWsName });
      setWorkspaces((p) => [...p, ws]);
      setSelectedWorkspace(ws.id);
      setNewWsName('');
    } catch {
      const mock: Workspace = { id: `ws-${Date.now()}`, org_id: 'demo', name: newWsName, created_at: new Date().toISOString() };
      setWorkspaces((p) => [...p, mock]);
      setSelectedWorkspace(mock.id);
      setNewWsName('');
    } finally { setCreatingWs(false); }
  };

  const handleDeleteSol = async (id: string) => {
    try { await solutionApi.delete(id); } catch { /* ignore */ }
    setSolutions((p) => p.filter((s) => s.id !== id));
  };

  const handleQuickBuild = async (tpl: MVPTemplate) => {
    setBuildingSlug(tpl.slug);
    setActionErr(null);
    try {
      const build = await mvpApi.quickBuild({ template: tpl.slug, app_name: tpl.app_name });
      setBuilds((p) => [build, ...p]);
    } catch (err) {
      setActionErr(err instanceof Error ? err.message : 'Build failed.');
    } finally { setBuildingSlug(null); }
  };

  const handleDownload = async (build: MVPBuild) => {
    try { await mvpApi.downloadBuild(build.build_id, `mvp_build${build.build_number}.zip`); }
    catch (err) { setActionErr(err instanceof Error ? err.message : 'Download failed.'); }
  };

  const handleDestroy = async (build: MVPBuild) => {
    if (!window.confirm(`Destroy build #${build.build_number}?`)) return;
    try { await mvpApi.destroy(build.build_id); setBuilds((p) => p.filter((b) => b.build_id !== build.build_id)); }
    catch (err) { setActionErr(err instanceof Error ? err.message : 'Destroy failed.'); }
  };

  const handleDeployed = (result: MVPDeployResult | string) => {
    const repoUrl = typeof result === 'string' ? result : result.repo_url;
    const renderUrl = typeof result === 'string' ? null : (result.frontend_url || result.render_service_url);
    setBuilds((p) => p.map((b) =>
      b.status === 'complete' && b.build_id === deployTarget?.build_id
        ? { ...b, repo_url: repoUrl, render_service_url: renderUrl, frontend_url: renderUrl }
        : b
    ));
  };

  return (
    <div className="space-y-8 animate-fade-up">

      {/* Page header */}
      <div>
        <h1 className="text-lg font-semibold text-white">Dashboard</h1>
        <p className="text-sm text-[#666] mt-0.5">Build and manage your architecture blueprints and apps.</p>
      </div>

      {/* Engine status bar */}
      {engineOnline !== null && (
        <div className={`flex items-center gap-2.5 px-4 py-2.5 rounded-lg border text-[13px] ${engineOnline
            ? 'bg-[#22c55e0a] border-[#22c55e20] text-[#4ade80]'
            : 'bg-[#f59e0b0a] border-[#f59e0b20] text-[#fbbf24]'
          }`}>
          <Circle className={`w-2 h-2 fill-current ${engineOnline ? 'animate-pulse-dot' : ''}`} />
          {engineOnline
            ? 'AI build engine is online — custom and premade app builds are ready.'
            : 'AI build engine is offline. Blueprint generation still works; app builds may be delayed.'}
        </div>
      )}

      {/* Stat row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Solutions', value: solutions.length, icon: Layers },
          { label: 'Workspaces', value: workspaces.length, icon: FolderKanban },
          { label: 'Quick Builds', value: builds.length, icon: Rocket },
          { label: 'Engine', value: engineOnline === null ? '—' : engineOnline ? 'Online' : 'Offline', icon: Circle },
        ].map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="p-4 rounded-xl bg-[#111] border border-[#1a1a1a]">
              <div className="flex items-center gap-2 text-[#555] mb-2">
                <Icon className="w-3.5 h-3.5" />
                <span className="text-[11px] font-medium uppercase tracking-wider">{m.label}</span>
              </div>
              <p className="text-2xl font-semibold text-white">{m.value}</p>
            </div>
          );
        })}
      </div>

      {/* Two paths */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" id="premade">

        {/* Premade apps */}
        <div className="bg-[#111] border border-[#1a1a1a] rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <Zap className="w-4 h-4 text-[#6366f1]" />
                Premade Apps
              </h2>
              <p className="text-[12px] text-[#555] mt-0.5">One-click builds from verified templates.</p>
            </div>
            <button
              onClick={async () => {
                const refreshed: MVPBuild[] = [];
                for (const b of builds) {
                  try { refreshed.push(await mvpApi.getStatus(b.build_id)); }
                  catch { refreshed.push(b); }
                }
                if (refreshed.length > 0) setBuilds(refreshed);
              }}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-transparent hover:bg-[#161616] border border-[#242424] text-[12px] text-[#666] hover:text-[#a1a1a1] transition-colors"
            >
              <RefreshCw className="w-3 h-3" />
              Refresh
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {templates.map((tpl) => (
              <div key={tpl.slug} className="flex flex-col gap-3 p-3.5 rounded-lg bg-[#0a0a0a] border border-[#1a1a1a] hover:border-[#242424] transition-colors">
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-[12px] font-semibold text-white">{tpl.title}</span>
                  </div>
                  <span className="text-[11px] text-[#444]">{tpl.industry}</span>
                  <p className="text-[11px] text-[#555] mt-1.5 leading-relaxed">{tpl.description}</p>
                </div>
                <button
                  onClick={() => handleQuickBuild(tpl)}
                  disabled={buildingSlug !== null}
                  className="mt-auto flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-[12px] font-medium transition-colors disabled:opacity-40"
                >
                  {buildingSlug === tpl.slug ? (
                    <><Loader2 className="w-3 h-3 animate-spin" />Building…</>
                  ) : (
                    <><Rocket className="w-3 h-3" />Build</>
                  )}
                </button>
              </div>
            ))}
          </div>

          {actionErr && <p className="text-[12px] text-[#f87171] bg-[#ef444410] border border-[#ef444420] rounded-lg px-3 py-2">{actionErr}</p>}

          {builds.length > 0 && (
            <div className="space-y-3 pt-3 border-t border-[#1a1a1a]">
              <h3 className="text-[12px] font-semibold text-white">Your Builds</h3>
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

        {/* Custom builder */}
        <div className="bg-[#111] border border-[#1a1a1a] rounded-xl p-5 flex flex-col justify-between gap-6">
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Wrench className="w-4 h-4 text-[#6366f1]" />
              Custom App Builder
            </h2>
            <p className="text-[13px] text-[#666] leading-relaxed">
              Skip the templates. Chat with the AI developer — describe your idea, iterate on scaffolded FastAPI + Next.js workspace, and finalize a build.
            </p>
            <ul className="space-y-2">
              {[
                'Persistent conversational session per build',
                'Live editing of FastAPI + Next.js workspace',
                'Upload a spec or PRD for context',
                'Finalize, download, or deploy to GitHub',
              ].map((item) => (
                <li key={item} className="flex items-center gap-2 text-[12px] text-[#777]">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#6366f1] shrink-0" />
                  {item}
                </li>
              ))}
            </ul>
            <p className="text-[12px] text-[#555]">⏱ Custom apps take 2–5 min: AI code generation + fresh cloud deploy.</p>
          </div>
          <Link
            href="/chat"
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-[13px] font-medium transition-colors"
          >
            <Wrench className="w-4 h-4" />
            Open Custom Builder
            <ArrowUpRight className="w-4 h-4 ml-1" />
          </Link>
        </div>
      </div>

      {/* Solutions */}
      <div className="space-y-3" id="blueprints">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white">Solution Blueprints</h2>
            <p className="text-[12px] text-[#555] mt-0.5">Architecture specs, database schemas, and roadmaps</p>
          </div>
          <Link
            href="/chat"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-transparent hover:bg-[#111] border border-[#1a1a1a] text-[12px] text-[#666] hover:text-[#a1a1a1] transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Generate New
          </Link>
        </div>

        {solutions.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {solutions.map((sol) => (
              <div key={sol.id} className="p-4 rounded-xl bg-[#111] border border-[#1a1a1a] hover:border-[#242424] transition-colors flex flex-col justify-between gap-4">
                <div>
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <span className="badge badge-green">{sol.status.toUpperCase()}</span>
                    <button
                      onClick={() => handleDeleteSol(sol.id)}
                      className="text-[#444] hover:text-[#f87171] transition-colors p-0.5"
                      title="Delete solution"
                    ><Trash2 className="w-3.5 h-3.5" /></button>
                  </div>
                  <h3 className="text-sm font-semibold text-white">{sol.title}</h3>
                  <p className="text-[12px] text-[#555] mt-1.5 leading-relaxed line-clamp-2">
                    {sol.description || 'Enterprise solution blueprint with architecture, schemas, and roadmap.'}
                  </p>
                </div>
                <div className="flex items-center justify-between pt-3 border-t border-[#1a1a1a]">
                  <div className="flex items-center gap-1.5 text-[11px] text-[#444]">
                    <Clock className="w-3 h-3" />
                    {new Date(sol.created_at).toLocaleDateString()}
                  </div>
                  <Link
                    href={`/solution/${sol.id}`}
                    className="flex items-center gap-1 text-[12px] font-medium text-[#6366f1] hover:text-[#818cf8] transition-colors"
                  >
                    View Blueprints <ArrowUpRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-14 text-center rounded-xl bg-[#111] border border-dashed border-[#1a1a1a]">
            <Layers className="w-8 h-8 text-[#333] mx-auto mb-3" />
            <p className="text-sm font-medium text-[#555]">No solutions yet</p>
            <p className="text-[12px] text-[#444] mt-1 mb-4">Build a premade app or start a custom session.</p>
            <Link
              href="/chat"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-[13px] font-medium transition-colors"
            >
              Start Building
            </Link>
          </div>
        )}
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 pb-6">
        {/* Workspaces */}
        <div className="p-5 rounded-xl bg-[#111] border border-[#1a1a1a] space-y-3" id="workspaces">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <FolderKanban className="w-4 h-4 text-[#6366f1]" /> Workspaces
          </h2>
          <p className="text-[12px] text-[#555]">Organize solutions by product line or client.</p>

          <form onSubmit={handleCreateWs} className="flex gap-2">
            <input
              type="text"
              value={newWsName}
              onChange={(e) => setNewWsName(e.target.value)}
              placeholder="New workspace name…"
              className="flex-1 px-3 py-2 rounded-lg bg-[#0a0a0a] border border-[#1a1a1a] text-[13px] text-white placeholder:text-[#444] focus:outline-none focus:border-[#3a3a3a] transition-colors"
            />
            <button
              type="submit"
              disabled={creatingWs || !newWsName.trim()}
              className="px-3 py-2 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-[13px] font-medium disabled:opacity-40 transition-colors"
            >
              Add
            </button>
          </form>

          <div className="space-y-1.5">
            {workspaces.map((ws) => (
              <div
                key={ws.id}
                onClick={() => setSelectedWorkspace(ws.id)}
                className={`px-3 py-2.5 rounded-lg text-[13px] cursor-pointer border transition-colors ${selectedWorkspace === ws.id
                    ? 'bg-[#6366f10a] border-[#6366f130] text-white'
                    : 'bg-transparent border-[#1a1a1a] text-[#666] hover:text-[#a1a1a1] hover:border-[#242424]'
                  }`}
              >
                <p className="font-medium">{ws.name}</p>
                {ws.description && <p className="text-[11px] text-[#444] mt-0.5">{ws.description}</p>}
              </div>
            ))}
          </div>
        </div>

        {/* Industry templates */}
        <div className="lg:col-span-2 p-5 rounded-xl bg-[#111] border border-[#1a1a1a] space-y-3" id="templates">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Compass className="w-4 h-4 text-[#6366f1]" /> Blueprints by Industry
          </h2>
          <p className="text-[12px] text-[#555]">Pre-seeded vertical prompts to kick off a custom architecture session.</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {INDUSTRY_PROMPTS.map((t) => (
              <Link
                key={t.title}
                href={`/chat?prompt=${encodeURIComponent(t.prompt)}`}
                className="p-3.5 rounded-lg bg-[#0a0a0a] border border-[#1a1a1a] hover:border-[#242424] transition-colors group"
              >
                <p className="text-[13px] font-semibold text-white group-hover:text-[#818cf8] transition-colors">{t.title}</p>
                <p className="text-[11px] text-[#555] mt-1 leading-relaxed">{t.desc}</p>
              </Link>
            ))}
          </div>
        </div>
      </div>

      {deployTarget && <DeployModal build={deployTarget} onClose={() => setDeployTarget(null)} onDeployed={handleDeployed} />}
      {configureTarget && <ConfigureModal build={configureTarget} onClose={() => setConfigureTarget(null)} onConfigured={() => undefined} />}
    </div>
  );
}