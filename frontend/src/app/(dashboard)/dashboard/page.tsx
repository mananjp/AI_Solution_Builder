'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Plus,
  ArrowUpRight,
  Trash,
  ArrowRight,
} from '@phosphor-icons/react/dist/ssr';
import { workspaceApi, solutionApi, billingApi } from '@/lib/api';
import { Solution, Workspace, BillingUsage } from '@/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

function DashboardSkeleton() {
  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <Skeleton className="h-7 w-36 mb-2" />
        <Skeleton className="h-4 w-64" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12">
        <div className="lg:col-span-7 flex flex-col gap-10">
          <section>
            <div className="flex items-center justify-between mb-4">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-6 w-20" />
            </div>
            <div className="flex flex-col gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="py-4 border-t border-border first:border-t-0">
                  <div className="flex items-center gap-3 mb-2">
                    <Skeleton className="h-4 w-16" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                  <Skeleton className="h-4 w-48 mb-1" />
                  <Skeleton className="h-3 w-64" />
                </div>
              ))}
            </div>
          </section>

          <section>
            <Skeleton className="h-4 w-24 mb-4" />
            <div className="flex gap-2 mb-4">
              <Skeleton className="h-9 flex-1" />
              <Skeleton className="h-9 w-12" />
            </div>
            <div className="flex flex-col gap-3">
              {[1, 2].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          </section>
        </div>

        <div className="lg:col-span-5 flex flex-col gap-10">
          <section>
            <Skeleton className="h-4 w-28 mb-2" />
            <Skeleton className="h-3 w-72 mb-5" />
            <div className="flex flex-col gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="py-4 border-t border-border first:border-t-0">
                  <Skeleton className="h-4 w-32 mb-1" />
                  <Skeleton className="h-3 w-64" />
                </div>
              ))}
            </div>
          </section>

          <section>
            <Skeleton className="h-4 w-16 mb-4" />
            <Skeleton className="h-1 w-full mb-3" />
            <div className="grid grid-cols-3 gap-3">
              {[1, 2, 3].map((i) => (
                <div key={i}>
                  <Skeleton className="h-5 w-8 mb-1" />
                  <Skeleton className="h-3 w-16" />
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('');
  const [newWsName, setNewWsName] = useState('');
  const [creatingWs, setCreatingWs] = useState(false);
  const [usage, setUsage] = useState<BillingUsage | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const wsList = await workspaceApi.list();
        if (wsList && wsList.length > 0) {
          setWorkspaces(wsList);
          setSelectedWorkspace(wsList[0].id);
          const solList = await solutionApi.list(wsList[0].id);
          setSolutions(solList.slice(0, 20));
        } else {
          try {
            const defaultWs = await workspaceApi.create({
              name: 'Primary Workspace',
              description: 'Core product architecture',
            });
            setWorkspaces([defaultWs]);
            setSelectedWorkspace(defaultWs.id);
          } catch {
            // Failed to create workspace silently
          }
        }
      } catch {
        // Error loading data - show empty state
      }

      try {
        const u = await billingApi.getUsage();
        setUsage(u);
      } catch {
        // Billing unavailable
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

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
      // Failed to create workspace
    } finally {
      setCreatingWs(false);
    }
  };

  const handleDeleteSolution = async (id: string) => {
    try {
      await solutionApi.delete(id);
      setSolutions(solutions.filter((s) => s.id !== id));
    } catch {
      setSolutions(solutions.filter((s) => s.id !== id));
    }
  };

  const templates = [
    {
      title: 'Retail & Commerce',
      prompt: 'Omnichannel retail system with inventory management, POS terminal support, and loyalty rewards.',
    },
    {
      title: 'Healthcare EHR',
      prompt: 'Telemedicine platform with HIPAA compliance, scheduling, WebRTC video, and electronic health records.',
    },
    {
      title: 'Logistics Dispatch',
      prompt: 'Freight dispatch system with automated route planning, live driver tracking, and digital proof of delivery.',
    },
    {
      title: 'B2B SaaS Platform',
      prompt: 'Multi-tenant B2B SaaS with organization billing, role-based access, and audit logs.',
    },
  ];

  if (loading) return <DashboardSkeleton />;

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-[clamp(1.5rem,3vw,2.2rem)] font-bold tracking-tight">
          Dashboard
        </h1>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Your architecture workspace. Solutions, templates, and credits.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12">
        {/* LEFT: Solutions + Workspace */}
        <div className="lg:col-span-7 flex flex-col gap-10">
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-[13px] font-semibold">Solutions</h2>
              <Button render={<Link href="/chat" />} nativeButton={false} variant="ghost" size="sm" className="text-primary hover:text-primary/80 hover:bg-primary/10 text-[11px] font-medium h-7 px-2">
                  <Plus className="w-3 h-3 mr-1" weight="bold" />
                  Generate
              </Button>
            </div>

            {solutions.length > 0 ? (
              <div className="flex flex-col">
                {solutions.map((sol) => (
                  <div
                    key={sol.id}
                    className="group py-4 border-t border-border first:border-t-0"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-3 mb-1">
                          <Badge
                            variant={sol.status === 'complete' ? 'default' : 'secondary'}
                            className={`font-mono text-[9px] tracking-wider uppercase px-1.5 py-0.5 ${
                              sol.status === 'complete'
                                ? 'bg-success/10 text-success border-success/20'
                                : 'bg-primary/10 text-primary border-primary/20'
                            }`}
                          >
                            {sol.status}
                          </Badge>
                          <span className="text-[10px] text-muted-foreground font-mono">
                            {new Date(sol.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        <Link
                          href={
                            sol.status === 'complete' ? `/solution/${sol.id}/mvp` : `/solution/${sol.id}`
                          }
                          className="text-[14px] font-semibold hover:text-primary transition-colors"
                        >
                          {sol.title}
                        </Link>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px]">
                          <span className="font-mono text-muted-foreground uppercase tracking-wider">
                            {sol.status === 'complete' ? 'Design ready' : sol.status}
                          </span>
                          {sol.status === 'complete' && (
                            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-amber-600 dark:text-amber-400">
                              MVP pending
                            </span>
                          )}
                        </div>
                        <p className="text-[12px] text-muted-foreground mt-0.5 line-clamp-1">
                          {sol.description || 'Architecture blueprint with schemas and roadmap.'}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0 pt-1">
                        <Link
                          href={
                            sol.status === 'complete' ? `/solution/${sol.id}/mvp` : `/solution/${sol.id}`
                          }
                          className="text-muted-foreground hover:text-primary transition-colors"
                          title="View"
                        >
                          <ArrowUpRight className="w-3.5 h-3.5" />
                        </Link>
                        <button
                          onClick={() => handleDeleteSolution(sol.id)}
                          className="text-muted-foreground hover:text-destructive transition-colors"
                          title="Delete"
                        >
                          <Trash className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <Card className="border-dashed border-border bg-transparent">
                <CardContent className="py-12 text-center">
                  <p className="text-[12px] text-muted-foreground mb-3">
                    No solutions yet. Start an architecture session to generate your first blueprint.
                  </p>
                  <Button render={<Link href="/chat" />} nativeButton={false} variant="ghost" size="sm" className="text-primary hover:text-primary/80 text-[12px] font-medium">
                      Create first solution
                      <ArrowRight className="w-3 h-3 ml-1.5" />
                  </Button>
                </CardContent>
              </Card>
            )}
          </section>

          <section>
            <h2 className="text-[13px] font-semibold mb-4">
              Workspaces
            </h2>

            <form onSubmit={handleCreateWorkspace} className="flex gap-2 mb-4">
              <Input
                type="text"
                value={newWsName}
                onChange={(e) => setNewWsName(e.target.value)}
                placeholder="New workspace name"
                className="bg-secondary border-border text-[12px] placeholder:text-muted-foreground/60 focus-visible:ring-primary/30"
              />
              <Button
                type="submit"
                disabled={creatingWs || !newWsName.trim()}
                size="sm"
                className="bg-primary text-primary-foreground hover:bg-primary/90 text-[11px] font-medium px-3"
              >
                Add
              </Button>
            </form>

            <div className="flex flex-col">
              {workspaces.map((ws) => (
                <button
                  key={ws.id}
                  onClick={() => setSelectedWorkspace(ws.id)}
                  className={`w-full text-left py-2.5 border-t border-border first:border-t-0 transition-colors ${
                    selectedWorkspace === ws.id
                      ? 'text-primary'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <span className="text-[13px] font-medium">{ws.name}</span>
                  {ws.description && (
                    <span className="text-[11px] text-muted-foreground ml-2">
                      {ws.description}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </section>
        </div>

        {/* RIGHT: Templates + Credits */}
        <div className="lg:col-span-5 flex flex-col gap-10">
          <section>
            <h2 className="text-[13px] font-semibold mb-4">
              Vertical templates
            </h2>
            <p className="text-[12px] text-muted-foreground mb-5">
              Pre-seeded industry patterns. Click to bootstrap an architecture session.
            </p>

            <div className="flex flex-col">
              {templates.map((t, i) => (
                <Link
                  key={i}
                  href={`/chat?prompt=${encodeURIComponent(t.prompt)}`}
                  className="group block py-4 border-t border-border first:border-t-0"
                >
                  <h3 className="text-[13px] font-semibold group-hover:text-primary transition-colors">
                    {t.title}
                  </h3>
                  <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                    {t.prompt}
                  </p>
                </Link>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-[13px] font-semibold mb-4">
              Credits
            </h2>
            <div className="flex flex-col gap-3">
              <div>
                <div className="flex items-center justify-between text-[11px] mb-1">
                  <span className="text-muted-foreground">Used this month</span>
                  <span className="font-mono text-muted-foreground">
                    {usage ? `${usage.credits_used.toLocaleString()} / ${usage.monthly_limit.toLocaleString()}` : '—'}
                  </span>
                </div>
                <div className="h-1 bg-secondary rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all"
                    style={{ width: usage ? `${Math.min(100, Math.round((usage.credits_used / usage.monthly_limit) * 100))}%` : '0%' }}
                  />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 pt-2">
                {[
                  { label: 'Generate', key: 'generate' as const },
                  { label: 'Regenerate', key: 'regenerate' as const },
                  { label: 'MVP build', key: 'mvp_build' as const },
                ].map((c) => (
                  <div key={c.label}>
                    <p className="font-mono text-[16px] font-bold text-primary">{usage?.credit_costs?.[c.key] ?? '—'}</p>
                    <p className="text-[10px] text-muted-foreground font-mono uppercase tracking-wider mt-0.5">
                      {c.label}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
