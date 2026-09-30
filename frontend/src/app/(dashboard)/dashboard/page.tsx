'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import {
  Layers, FolderKanban, Clock, ArrowUpRight, Trash2, AlertCircle,
  Rocket, Zap, Loader2, RefreshCw, Circle, MessageSquare,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AnnouncementBanner } from '@/components/lab/announcement-banner';
import { RelativeTime } from '@/components/lab/relative-time';
import { ToastStack } from '@/components/lab/toast-stack';

/** Mirrors the lab's internal `Toast` shape, which it does not export. */
type Toast = { id: number; title: string; description: string };
import { workspaceApi, solutionApi, mvpApi, opencodeApi, billingApi } from '@/lib/api';
import { Solution, Workspace, MVPBuild, MVPTemplate, MVPDeployResult } from '@/types';
import { errorMessage } from '@/lib/errors';
import { BuildCard, ConfigureModal, DeployModal } from '@/components/mvp/BuildCard';
import { useI18n } from '@/components/I18nProvider';
import { useAuthSession } from '@/components/auth/AuthProvider';

const FALLBACK_TEMPLATES: MVPTemplate[] = [
  { slug: 'todo', title: 'Todo List', description: 'Simple CRUD app with items, tags, and completion states.', app_name: 'todo-app', industry: 'Productivity' },
  { slug: 'calculator', title: 'Calculator', description: 'Interactive calculator with a persistent history ledger.', app_name: 'calculator', industry: 'Utilities' },
  { slug: 'portfolio', title: 'Portfolio Site', description: 'Public portfolio with project showcases and a contact form.', app_name: 'portfolio', industry: 'Web' },
];


export default function DashboardPage() {
  const { t } = useI18n();
  const { user } = useAuthSession();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState('');
  const [engineOnline, setEngineOnline] = useState<boolean | null>(null);
  const [engineModel, setEngineModel] = useState<string | null>(null);
  const [builds, setBuilds] = useState<MVPBuild[]>([]);
  const [templates, setTemplates] = useState<MVPTemplate[]>(FALLBACK_TEMPLATES);
  const [buildingSlug, setBuildingSlug] = useState<string | null>(null);
  const [deployTarget, setDeployTarget] = useState<MVPBuild | null>(null);
  const [configureTarget, setConfigureTarget] = useState<MVPBuild | null>(null);
  const [newWsName, setNewWsName] = useState('');
  const [creatingWs, setCreatingWs] = useState(false);
  const [engineOfflineDismissed, setEngineOfflineDismissed] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  // Real credit balance from the billing API. This was a hardcoded "1,450",
  // so the tile reported the same number to every account forever.
  const [credits, setCredits] = useState<number | null>(null);
  // Ids are handed out by a ref rather than a counter, so two failures landing
  // in the same tick cannot collide on the toast stack's key.
  const nextToastId = useRef(0);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const pushToast = useCallback((title: string, description: string) => {
    setToasts((prev) => [...prev, { id: nextToastId.current++, title, description }]);
  }, []);

  // Build ids still in flight. Derived rather than recomputed inside the polling
  // effect, so the interval only restarts when the set of active ids actually
  // changes instead of on every status write.
  const activeBuilds = useMemo(
    () =>
      builds
        .filter((b) => b.status === 'queued' || b.status === 'pending' || b.status === 'building')
        .map((b) => b.build_id),
    [builds]
  );

  // The banner stays dismissed until the sidecar drops again, so a transient
  // blip does not bring it back and a real recovery-then-outage does.
  const wasOnline = useRef<boolean | null>(null);
  useEffect(() => {
    if (engineOnline === null) return;
    if (wasOnline.current === false && engineOnline === false) {
      setEngineOfflineDismissed(false);
    }
    wasOnline.current = engineOnline;
  }, [engineOnline]);

  // Load workspaces + solutions
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    async function load() {
      setLoadError(null);
      try {
        const wsList = await workspaceApi.list();
        if (cancelled) return;
        if (wsList?.length > 0) {
          setWorkspaces(wsList);
          setSelectedWorkspace(wsList[0].id);
          const sols = await solutionApi.list(wsList[0].id);
          if (!cancelled) setSolutions(sols);
        } else {
          // A brand new account genuinely has no workspaces, so seeding one is
          // a real create call rather than a stand-in.
          const ws = await workspaceApi.create({
            name: 'Primary Workspace',
            description: 'Core architecture zone',
          });
          if (cancelled) return;
          setWorkspaces([ws]);
          setSelectedWorkspace(ws.id);
        }
      } catch (err) {
        if (cancelled) return;
        // Previously this synthesised a "Primary Workspace" plus two finished
        // solutions ("Omnichannel Retail POS", "HIPAA-Compliant Telehealth"),
        // both marked complete. Any 401/404/500 or an offline backend therefore
        // rendered as a populated, healthy account, and a user with real work
        // would be looking at invented titles. Report the failure instead.
        setWorkspaces([]);
        setSolutions([]);
        setLoadError(errorMessage(err));
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [user, reloadToken]);

  // Ping engine
  useEffect(() => {
    let mounted = true;
    const check = () => opencodeApi.health()
      .then((r) => {
        if (!mounted) return;
        setEngineOnline(r.sidecar_healthy);
        setEngineModel(r.model ?? null);
      })
      .catch(() => { if (mounted) setEngineOnline(false); });
    check();
    const t = setInterval(check, 15000);
    return () => { mounted = false; clearInterval(t); };
  }, []);

  // Load templates
  useEffect(() => {
    if (!user) return;
    mvpApi.listTemplates().then((l) => { if (l?.length > 0) setTemplates(l); }).catch(() => undefined);
  }, [user]);

  // Credit balance. A failure leaves the tile as an em dash rather than a
  // number, so an unreadable balance is never reported as a real one.
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    billingApi
      .getUsage()
      .then((u) => {
        if (!cancelled) setCredits(u.current_balance);
      })
      .catch(() => {
        if (!cancelled) setCredits(null);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  // Poll active builds
  useEffect(() => {
    if (!user || !activeBuilds.length) return;
    const t = setInterval(async () => {
      for (const id of activeBuilds) {
        try {
          const fresh = await mvpApi.getStatus(id);
          setBuilds((p) => p.map((b) => (b.build_id === id ? fresh : b)));
        } catch { /* keep last known status */ }
      }
    }, 3000);
    return () => clearInterval(t);
  }, [user, activeBuilds]);

  const handleCreateWs = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setCreatingWs(true);
    try {
      const ws = await workspaceApi.create({ name: newWsName });
      setWorkspaces((p) => [...p, ws]);
      setSelectedWorkspace(ws.id);
      setNewWsName('');
    } catch (err) {
      // This used to add a locally-invented workspace with a timestamp id, so a
      // failed create looked like it had worked and then vanished on reload.
      pushToast('Workspace not created', errorMessage(err));
    } finally { setCreatingWs(false); }
  };

  const handleDeleteSol = async (id: string) => {
    try {
      await solutionApi.delete(id);
      setSolutions((p) => p.filter((s) => s.id !== id));
    } catch (err) {
      // Removing the row regardless meant a failed delete looked successful and
      // the solution reappeared on the next load.
      pushToast('Delete failed', errorMessage(err));
    }
  };

    const handleQuickBuild = async (tpl: MVPTemplate) => {
      setBuildingSlug(tpl.slug);
      try {
        const build = await mvpApi.quickBuild({ template: tpl.slug, app_name: tpl.app_name });
        setBuilds((p) => [build, ...p]);
      } catch (err) {
        pushToast('Build failed', err instanceof Error ? err.message : `Could not start ${tpl.title}.`);
      } finally { setBuildingSlug(null); }
    };
  
    const handleDownload = async (build: MVPBuild) => {
      try { await mvpApi.downloadBuild(build.build_id, `mvp_build${build.build_number}.zip`); }
      catch (err) { pushToast('Download failed', err instanceof Error ? err.message : 'The artifact could not be downloaded.'); }
    };
  
    const handleDestroy = async (build: MVPBuild) => {
      if (!window.confirm(`Destroy build #${build.build_number}?`)) return;
      try { await mvpApi.destroy(build.build_id); setBuilds((p) => p.filter((b) => b.build_id !== build.build_id)); }
      catch (err) { pushToast('Destroy failed', err instanceof Error ? err.message : 'The build was not destroyed.'); }
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

      {/* Announced once the engine has actually answered, so a slow first poll
          never shows an alarming banner about something still loading. */}
      <AnnouncementBanner
        open={engineOnline === false && !engineOfflineDismissed}
        onDismiss={() => setEngineOfflineDismissed(true)}
        icon={<AlertCircle className="size-4" aria-hidden />}
        label="Engine status"
      >
        The generation sidecar is not responding. Builds and diagnoses will fail until it is
        back.
      </AnnouncementBanner>

      {/* A failed load is not an empty account. Without this the page looked
          identical to a brand new user, and the two require opposite actions. */}
      {loadError && (
        <div
          role="alert"
          className="flex flex-wrap items-start gap-3 rounded border border-[var(--red-edge)] bg-[var(--red-wash)] px-4 py-3 text-sm text-[var(--red)]"
        >
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">Could not load your workspaces</p>
            <p className="mt-0.5 font-mono text-xs opacity-90">{loadError}</p>
            <p className="mt-1 text-xs opacity-80">
              The counts and lists below are empty because nothing could be read, not
              because your account has no work in it.
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setReloadToken((n) => n + 1)}
          >
            <RefreshCw />
            Retry
          </Button>
        </div>
      )}

      {/* Page header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-serif text-[var(--sutra-ink)]">{t('dash.overview')}</h1>
          <p className="text-[13px] text-[var(--text-2)] mt-2 max-w-lg leading-relaxed font-light">
            {t('dash.overviewSub')}
          </p>
        </div>
        
        {engineOnline !== null && (
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-widest font-semibold text-[var(--text-3)]">{t('dash.engineStatus')}</span>
            {/* Read-only now. It used to run a full sidecar diagnostic and dump
                a per-check report with raw fix instructions — an operations
                tool, not something a user of the product needs in front of them.
                The offline banner above still reports a failure they can act on. */}
            <span
              className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-bold ${
                engineOnline
                  ? 'border-[var(--green-edge)] text-[var(--green)]'
                  : 'border-[var(--amber-edge)] text-[var(--amber)]'
              }`}
            >
              <Circle className={`size-2 fill-current ${engineOnline ? 'animate-pulse-dot' : ''}`} aria-hidden />
              {engineOnline ? (engineModel ? `${t('common.online')} · ${engineModel}` : t('common.online')) : t('common.offline')}
            </span>
          </div>
        )}
      </div>
      {/* Stat row */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {[
          { label: t('dash.totalSolutions'), value: solutions.length.toLocaleString(), icon: Layers },
          { label: t('dash.workspaces'), value: workspaces.length.toLocaleString(), icon: FolderKanban },
          // Labelled "active", so it counts only builds still in flight. It
          // previously showed every build the account had ever made.
          {
            label: t('dash.activeBuilds'),
            value: activeBuilds.toLocaleString(),
            icon: Rocket,
          },
          // null means the balance could not be read; an em dash is honest, a
          // number would not be.
          {
            label: t('dash.credits'),
            value: credits === null ? '—' : credits.toLocaleString(),
            icon: Zap,
          },
        ].map((m) => {
          const Icon = m.icon;
          return (
            <Card key={m.label} interactive className="flex h-[120px] flex-col justify-between p-6 group">
              <div className="flex items-center justify-between text-muted">
                <span className="text-[10px] font-bold uppercase tracking-widest transition-colors group-hover:text-foreground">{m.label}</span>
                <Icon className="size-4 opacity-50 transition-all group-hover:text-foreground group-hover:opacity-100" />
              </div>
              <p className="font-serif text-3xl">{m.value}</p>
            </Card>
          );
        })}
      </div>

      {/* Premade apps. This was one half of a two-column "Two paths" grid beside
          an AI Solution Builder pitch card; with that card removed there is a
          single section, so the grid wrapper went too. */}
      <Card interactive className="space-y-6 p-8">
          <div className="flex items-end justify-between border-b pb-4">
            <div>
              <h2 className="flex items-center gap-3 font-serif text-xl">
                <Zap className="size-5 text-muted" />
                {t('dash.templates')}
              </h2>
              <p className="mt-1 text-[12px] text-muted">{t('dash.templatesSub')}</p>
            </div>
            <Button
              variant="outline"
              size="icon-sm"
              aria-label="Refresh build status"
              onClick={async () => {
                const refreshed: MVPBuild[] = [];
                for (const b of builds) {
                  try { refreshed.push(await mvpApi.getStatus(b.build_id)); }
                  catch { refreshed.push(b); }
                }
                if (refreshed.length > 0) setBuilds(refreshed);
              }}
            >
              <RefreshCw />
            </Button>
          </div>

          <ScrollArea className="max-h-[300px] pr-2">
            <div className="grid grid-cols-1 gap-3 pr-3">
              {templates.map((tpl) => (
                <div key={tpl.slug} className="group flex flex-col justify-between gap-4 rounded-sm border bg-surface p-4 transition-colors hover:border-foreground sm:flex-row sm:items-center">
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <span className="text-[13px] font-semibold">{tpl.title}</span>
                      <Badge variant="secondary" className="bg-accent-dim text-[9px] font-bold uppercase tracking-widest text-foreground">
                        {tpl.industry}
                      </Badge>
                    </div>
                    <p className="truncate text-[11px] text-muted">{tpl.description}</p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="shrink-0"
                    onClick={() => handleQuickBuild(tpl)}
                    disabled={buildingSlug !== null}
                  >
                    {buildingSlug === tpl.slug ? (
                      <><Loader2 className="animate-spin" />Building</>
                    ) : (
                      <><Rocket />Build App</>
                    )}
                  </Button>
                </div>
              ))}
            </div>
          </ScrollArea>

          {builds.length > 0 && (
            <div className="space-y-4 border-t pt-4">
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted">Active Build Pipelines</h3>
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
        </Card>

      {/* Solutions */}
      <div className="space-y-6" id="blueprints">
        <div className="border-b pb-4">
          <h2 className="font-serif text-xl">Solution Blueprints</h2>
          <p className="mt-1 text-[12px] text-muted">Orchestrated architecture specs, database schemas, and roadmaps</p>
        </div>

        {solutions.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {solutions.map((sol) => (
              <Card key={sol.id} interactive className="group flex cursor-pointer flex-col justify-between gap-6 p-6">
                <div>
                  <div className="mb-4 flex items-start justify-between gap-3">
                    <Badge variant="secondary" className="bg-accent-dim text-foreground">{sol.status}</Badge>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={(e) => { e.preventDefault(); handleDeleteSol(sol.id); }}
                      aria-label="Delete solution"
                      className="text-muted hover:text-destructive"
                    >
                      <Trash2 />
                    </Button>
                  </div>
                  <h3 className="text-[15px] font-semibold leading-tight">{sol.title}</h3>
                  <p className="mt-2 line-clamp-2 text-[12px] leading-relaxed text-muted">
                    {sol.description || 'Enterprise solution blueprint with architecture, schemas, and roadmap.'}
                  </p>
                </div>
                <div className="flex items-center justify-between border-t pt-4">
                  <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted">
                    <Clock className="size-3" />
                    <RelativeTime date={sol.created_at} />
                  </div>
                  <div className="flex items-center gap-3">
                    <Button
                      asChild
                      variant="ghost"
                      size="sm"
                      className="text-[11px] font-medium text-muted hover:text-foreground"
                    >
                      <Link
                        href={`/chat?solution_id=${sol.id}&app_name=${encodeURIComponent(sol.title)}`}
                        title="Open chat in AI Architect"
                      >
                        <MessageSquare />
                        Chat
                      </Link>
                    </Button>
                    <Button
                      asChild
                      variant="ghost"
                      size="sm"
                      className="text-[11px] font-bold uppercase tracking-widest text-foreground hover:text-foreground"
                    >
                      <Link href={`/solution/${sol.id}`}>
                        View Specs <ArrowUpRight />
                      </Link>
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <Card className="border-dashed py-20 text-center">
            <Layers className="mx-auto mb-4 size-10 opacity-50 text-muted" />
            <p className="font-serif text-[15px]">No solutions generated</p>
            <p className="mx-auto mb-6 mt-2 max-w-sm text-[13px] font-light text-muted">Start a custom AI builder session to generate your first architecture blueprint.</p>
            <Button asChild>
              <Link href="/chat?new=true">Start Building</Link>
            </Button>
          </Card>
        )}
      </div>

        {/* Workspaces. This was a child of a three-column grid alongside the
            Domain Templates card; with that removed it is a full-width section,
            so the grid wrapper went with it. */}
        <div id="workspaces" className="pb-12">
          <Card interactive className="space-y-6 p-8">
          <div className="border-b pb-4">
            <h2 className="flex items-center gap-3 font-serif text-xl">
              <FolderKanban className="size-5 text-muted" /> Workspaces
            </h2>
            <p className="mt-1 text-[12px] text-muted">Organize solutions by product line.</p>
          </div>

          <form onSubmit={handleCreateWs} className="flex gap-2">
            <Input
              type="text"
              value={newWsName}
              onChange={(e) => setNewWsName(e.target.value)}
              placeholder="New workspace..."
              className="flex-1"
            />
            <Button
              type="submit"
              variant="outline"
              className="shrink-0"
              disabled={creatingWs || !newWsName.trim()}
            >
              Add
            </Button>
          </form>

          <ScrollArea className="max-h-[300px]">
            <div className="space-y-2 pr-3">
              {workspaces.map((ws) => (
                <Card
                  key={ws.id}
                  onClick={() => setSelectedWorkspace(ws.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setSelectedWorkspace(ws.id);
                    }
                  }}
                  aria-pressed={selectedWorkspace === ws.id}
                  className={`cursor-pointer p-4 transition-colors ${
                    selectedWorkspace === ws.id
                      ? 'border-foreground bg-background shadow-sm'
                      : 'bg-surface hover:border-muted-foreground'
                  }`}
                >
                  <p className="text-[13px] font-semibold">{ws.name}</p>
                  {ws.description && <p className="mt-1 text-[11px] text-muted">{ws.description}</p>}
                </Card>
              ))}
            </div>
          </ScrollArea>
          </Card>
        </div>

      {deployTarget && <DeployModal build={deployTarget} onClose={() => setDeployTarget(null)} onDeployed={handleDeployed} />}
      {configureTarget && <ConfigureModal build={configureTarget} onClose={() => setConfigureTarget(null)} onConfigured={() => undefined} />}

      {/* Transient action failures surface here instead of inside the panel that
          raised them, so a message raised while scrolled away is still seen. */}
      <ToastStack
        toasts={toasts}
        onDismiss={(id) => setToasts((prev) => prev.filter((toast) => toast.id !== id))}
      />
    </div>
  );
}
