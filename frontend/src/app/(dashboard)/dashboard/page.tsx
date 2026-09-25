'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Plus, Layers, FolderKanban, Clock, ArrowUpRight, Trash2,
  Compass, Rocket, Zap, Loader2, RefreshCw, Circle,
} from 'lucide-react';
import { workspaceApi, solutionApi, mvpApi, opencodeApi } from '@/lib/api';
import { Solution, Workspace, MVPBuild, MVPTemplate, MVPDeployResult } from '@/types';
import { BuildCard, ConfigureModal, DeployModal } from '@/components/mvp/BuildCard';
import { useI18n } from '@/components/I18nProvider';

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
  const { t } = useI18n();
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
    let mounted = true;
    async function load() {
      try {
        const wsList = await workspaceApi.list();
        if (!mounted) return;
        if (wsList?.length > 0) {
          setWorkspaces(wsList);
          setSelectedWorkspace(wsList[0].id);
          const sols = await solutionApi.list(wsList[0].id);
          if (mounted) setSolutions(sols);
        } else {
          const ws = await workspaceApi.create({ name: 'Primary Workspace', description: 'Core architecture zone' });
          if (!mounted) return;
          setWorkspaces([ws]);
          setSelectedWorkspace(ws.id);
        }
      } catch {
        if (!mounted) return;
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
    return () => { mounted = false; };
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
    <div className="space-y-10 animate-fade-up max-w-[1200px] mx-auto py-4">

      {/* Page header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif text-[var(--sutra-charcoal)]">{t('dash.overview')}</h1>
          <p className="text-[13px] text-[var(--text-2)] mt-2 max-w-lg leading-relaxed font-light">
            {t('dash.overviewSub')}
          </p>
        </div>
        
        {engineOnline !== null && (
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-widest font-semibold text-[var(--text-3)]">{t('dash.engineStatus')}</span>
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-sm border text-[11px] uppercase tracking-widest font-bold shadow-sm ${
                engineOnline
                  ? 'bg-[var(--bg-2)] border-[var(--border)] text-[var(--green)]'
                  : 'bg-[var(--bg-2)] border-[var(--border)] text-[var(--red)]'
              }`}>
              <Circle className={`w-2 h-2 fill-current ${engineOnline ? 'animate-pulse-dot' : ''}`} />
              {engineOnline ? t('common.online') : t('common.offline')}
            </div>
          </div>
        )}
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: t('dash.totalSolutions'), value: solutions.length, icon: Layers },
          { label: t('dash.workspaces'), value: workspaces.length, icon: FolderKanban },
          { label: t('dash.activeBuilds'), value: builds.length, icon: Rocket },
          { label: t('dash.credits'), value: '1,450', icon: Zap },
        ].map((m) => {
          const Icon = m.icon;
          return (
            <div key={m.label} className="sutra-card p-6 flex flex-col justify-between h-[120px] group hover:border-[var(--sutra-muted-gold)] transition-colors">
              <div className="flex items-center justify-between text-[var(--text-2)]">
                <span className="text-[10px] font-bold uppercase tracking-widest group-hover:text-[var(--sutra-charcoal)] transition-colors">{m.label}</span>
                <Icon className="w-4 h-4 opacity-50 group-hover:opacity-100 group-hover:text-[var(--sutra-muted-gold)] transition-all" />
              </div>
              <p className="text-3xl font-serif text-[var(--sutra-charcoal)]">{m.value}</p>
            </div>
          );
        })}
      </div>

      {/* Two paths */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" id="premade">

        {/* Custom builder */}
        <div className="sutra-card p-8 flex flex-col justify-between gap-8 bg-gradient-to-br from-[var(--bg)] to-[var(--bg-2)]">
          <div className="space-y-4">
            <h2 className="text-xl font-serif text-[var(--sutra-charcoal)] flex items-center gap-3 border-b border-[var(--border)] pb-4">
              <div className="w-8 h-8 flex items-center justify-center border border-[var(--sutra-muted-gold)] bg-[var(--bg-2)]">
                <span className="text-[var(--sutra-muted-gold)] font-serif italic text-lg leading-none">S</span>
              </div>
              {t('dash.aiSolutionBuilder')}
            </h2>
            <p className="text-[13px] text-[var(--text-2)] leading-relaxed">
              {t('dash.aiSolutionBuilderDesc')}
            </p>
            <ul className="space-y-3 pt-2">
              {[
                t('dash.featContextual'),
                t('dash.featArchitecture'),
                t('dash.featDocs'),
                t('dash.featScaffold'),
              ].map((item) => (
                <li key={item} className="flex items-center gap-3 text-[12px] font-medium text-[var(--sutra-charcoal)]">
                  <span className="w-1.5 h-1.5 bg-[var(--sutra-muted-gold)]" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <Link
            href="/chat"
            className="btn btn-primary flex justify-center w-full shadow-md hover:shadow-lg"
          >
            {t('dash.startNewBuild')}
            <ArrowUpRight className="w-4 h-4 ml-2 opacity-70" />
          </Link>
        </div>

        {/* Premade apps */}
        <div className="sutra-card p-8 space-y-6">
          <div className="flex items-end justify-between border-b border-[var(--border)] pb-4">
            <div>
              <h2 className="text-xl font-serif text-[var(--sutra-charcoal)] flex items-center gap-3">
                <Zap className="w-5 h-5 text-[var(--text-3)]" />
                {t('dash.templates')}
              </h2>
              <p className="text-[12px] text-[var(--text-2)] mt-1">{t('dash.templatesSub')}</p>
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
              className="btn btn-ghost border border-[var(--border)] bg-[var(--bg)]"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-1 gap-3 max-h-[300px] overflow-y-auto pr-2">
            {templates.map((tpl) => (
              <div key={tpl.slug} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] transition-colors group">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[13px] font-semibold text-[var(--sutra-charcoal)]">{tpl.title}</span>
                    <span className="text-[9px] uppercase tracking-widest font-bold text-[var(--sutra-muted-gold)] bg-[var(--accent-dim)] px-2 py-0.5 rounded-sm">{tpl.industry}</span>
                  </div>
                  <p className="text-[11px] text-[var(--text-2)] truncate">{tpl.description}</p>
                </div>
                <button
                  onClick={() => handleQuickBuild(tpl)}
                  disabled={buildingSlug !== null}
                  className="btn btn-secondary shrink-0"
                >
                  {buildingSlug === tpl.slug ? (
                    <><Loader2 className="w-3.5 h-3.5 animate-spin" />Building</>
                  ) : (
                    <><Rocket className="w-3.5 h-3.5" />Build App</>
                  )}
                </button>
              </div>
            ))}
          </div>

          {actionErr && <p className="text-[11px] font-semibold text-[var(--red)] bg-[var(--bg-2)] border border-[var(--red)] p-3 shadow-sm">{actionErr}</p>}

          {builds.length > 0 && (
            <div className="space-y-4 pt-4 border-t border-[var(--border)]">
              <h3 className="text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)]">Active Build Pipelines</h3>
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
      </div>

      {/* Solutions */}
      <div className="space-y-6" id="blueprints">
        <div className="flex items-end justify-between border-b border-[var(--border)] pb-4">
          <div>
            <h2 className="text-xl font-serif text-[var(--sutra-charcoal)]">Solution Blueprints</h2>
            <p className="text-[12px] text-[var(--text-2)] mt-1">Orchestrated architecture specs, database schemas, and roadmaps</p>
          </div>
          <Link
            href="/chat"
            className="btn btn-secondary bg-[var(--bg)] border border-[var(--border)]"
          >
            <Plus className="w-3.5 h-3.5" />
            New Solution
          </Link>
        </div>

        {solutions.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {solutions.map((sol) => (
              <div key={sol.id} className="sutra-card p-6 flex flex-col justify-between gap-6 hover:shadow-md transition-shadow group cursor-pointer border-[var(--border)] hover:border-[var(--sutra-muted-gold)]">
                <div>
                  <div className="flex items-start justify-between gap-3 mb-4">
                    <span className="badge badge-amber">{sol.status}</span>
                    <button
                      onClick={(e) => { e.preventDefault(); handleDeleteSol(sol.id); }}
                      className="text-[var(--text-3)] hover:text-[var(--red)] transition-colors p-1"
                      title="Delete solution"
                    ><Trash2 className="w-4 h-4" /></button>
                  </div>
                  <h3 className="text-[15px] font-semibold text-[var(--sutra-charcoal)] leading-tight">{sol.title}</h3>
                  <p className="text-[12px] text-[var(--text-2)] mt-2 leading-relaxed line-clamp-2">
                    {sol.description || 'Enterprise solution blueprint with architecture, schemas, and roadmap.'}
                  </p>
                </div>
                <div className="flex items-center justify-between pt-4 border-t border-[var(--border)]">
                  <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest font-semibold text-[var(--text-3)]">
                    <Clock className="w-3 h-3" />
                    {new Date(sol.created_at).toLocaleDateString()}
                  </div>
                  <Link
                    href={`/solution/${sol.id}`}
                    className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-widest text-[var(--sutra-muted-gold)] hover:text-[var(--sutra-deep-gold)] transition-colors"
                  >
                    View Specs <ArrowUpRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-20 text-center sutra-card bg-[var(--bg-2)] border-dashed">
            <Layers className="w-10 h-10 text-[var(--text-3)] mx-auto mb-4 opacity-50" />
            <p className="text-[15px] font-serif text-[var(--sutra-charcoal)]">No solutions generated</p>
            <p className="text-[13px] text-[var(--text-2)] mt-2 mb-6 font-light max-w-sm mx-auto">Start a custom AI builder session to generate your first architecture blueprint.</p>
            <Link
              href="/chat"
              className="btn btn-primary shadow-sm"
            >
              Start Building
            </Link>
          </div>
        )}
      </div>

      {/* Bottom row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 pb-12">
        
        {/* Industry templates */}
        <div className="lg:col-span-2 sutra-card p-8 space-y-6" id="templates">
          <div className="border-b border-[var(--border)] pb-4">
            <h2 className="text-xl font-serif text-[var(--sutra-charcoal)] flex items-center gap-3">
              <Compass className="w-5 h-5 text-[var(--text-3)]" /> Domain Templates
            </h2>
            <p className="text-[12px] text-[var(--text-2)] mt-1">Pre-seeded vertical prompts to kick off a custom architecture session.</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {INDUSTRY_PROMPTS.map((t) => (
              <Link
                key={t.title}
                href={`/chat?prompt=${encodeURIComponent(t.prompt)}`}
                className="p-5 bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] transition-colors group h-full flex flex-col"
              >
                <p className="text-[13px] font-semibold text-[var(--sutra-charcoal)] group-hover:text-[var(--sutra-muted-gold)] transition-colors mb-2">{t.title}</p>
                <p className="text-[11px] text-[var(--text-2)] leading-relaxed font-light mt-auto">{t.desc}</p>
              </Link>
            ))}
          </div>
        </div>

        {/* Workspaces */}
        <div className="sutra-card p-8 space-y-6" id="workspaces">
          <div className="border-b border-[var(--border)] pb-4">
            <h2 className="text-xl font-serif text-[var(--sutra-charcoal)] flex items-center gap-3">
              <FolderKanban className="w-5 h-5 text-[var(--text-3)]" /> Workspaces
            </h2>
            <p className="text-[12px] text-[var(--text-2)] mt-1">Organize solutions by product line.</p>
          </div>

          <form onSubmit={handleCreateWs} className="flex gap-2">
            <input
              type="text"
              value={newWsName}
              onChange={(e) => setNewWsName(e.target.value)}
              placeholder="New workspace..."
              className="flex-1 px-4 py-2 bg-[var(--bg-2)] border border-[var(--border)] text-[12px] text-[var(--text)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors"
            />
            <button
              type="submit"
              disabled={creatingWs || !newWsName.trim()}
              className="btn btn-secondary shrink-0"
            >
              Add
            </button>
          </form>

          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {workspaces.map((ws) => (
              <div
                key={ws.id}
                onClick={() => setSelectedWorkspace(ws.id)}
                className={`p-4 cursor-pointer border transition-colors ${
                  selectedWorkspace === ws.id
                    ? 'bg-[var(--bg)] border-[var(--sutra-muted-gold)] shadow-sm'
                    : 'bg-[var(--bg-2)] border-[var(--border)] hover:border-[var(--text-3)]'
                }`}
              >
                <p className="text-[13px] font-semibold text-[var(--sutra-charcoal)]">{ws.name}</p>
                {ws.description && <p className="text-[11px] text-[var(--text-2)] mt-1">{ws.description}</p>}
              </div>
            ))}
          </div>
        </div>
      </div>

      {deployTarget && <DeployModal build={deployTarget} onClose={() => setDeployTarget(null)} onDeployed={handleDeployed} />}
      {configureTarget && <ConfigureModal build={configureTarget} onClose={() => setConfigureTarget(null)} onConfigured={() => undefined} />}
    </div>
  );
}