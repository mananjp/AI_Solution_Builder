'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { 
  Sparkles, 
  Plus, 
  Layers, 
  FolderKanban, 
  Clock, 
  ArrowUpRight, 
  Trash2, 
  Cpu, 
  Compass
} from 'lucide-react';
import { workspaceApi, solutionApi } from '@/lib/api';
import { Solution, Workspace } from '@/types';

export default function DashboardPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('');

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
          // If no workspaces, create a default one
          try {
            const defaultWs = await workspaceApi.create({
              name: 'Primary Enterprise Systems',
              description: 'Flagship product architecture and engineering specs',
            });
            setWorkspaces([defaultWs]);
            setSelectedWorkspace(defaultWs.id);
          } catch {
            // Demo fallback
            setWorkspaces([
              { id: 'ws-demo-1', org_id: 'org-1', name: 'Primary Enterprise Systems', description: 'Core product architecture', created_at: new Date().toISOString() }
            ]);
            setSelectedWorkspace('ws-demo-1');
          }
        }
      } catch {
        // Provide mock state so UI works gracefully even without live backend connection
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
      } finally {
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

  return (
    <div className="space-y-8">
      {/* Top Banner */}
      <div className="relative p-8 rounded-3xl bg-gradient-to-r from-indigo-950/60 via-slate-900/80 to-purple-950/40 border border-white/5 overflow-hidden shadow-2xl">
        <div className="relative z-10 max-w-2xl space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>Autonomous Multi-Agent Studio</span>
          </div>
          <h2 className="text-3xl font-extrabold text-white tracking-tight">
            Design, Architect & Synthesize Full Solutions
          </h2>
          <p className="text-sm text-slate-300 leading-relaxed">
            Collaborate with an autonomous swarm of AI specialists. Upload PRDs or simply describe your business idea to generate production-grade HLD, LLD, Database schemas, and implementation roadmaps.
          </p>
          <div className="pt-2 flex flex-wrap items-center gap-3">
            <Link
              href="/chat"
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white font-semibold text-xs shadow-lg shadow-indigo-500/25 transition-all hover:scale-105"
            >
              <Sparkles className="w-4 h-4" />
              <span>Launch AI Architect</span>
            </Link>
            <a
              href="#templates"
              className="px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-200 text-xs font-semibold transition-colors"
            >
              Browse Vertical Templates
            </a>
          </div>
        </div>

        {/* Ambient background decoration */}
        <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-gradient-to-l from-indigo-500/10 to-transparent pointer-events-none" />
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
            <p className="text-xs text-slate-400 font-medium">Autonomous Swarm</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">6 Active</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Cpu className="w-5 h-5" />
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-slate-900/40 border border-white/5 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-400 font-medium">AI Credits</p>
            <p className="text-2xl font-bold text-indigo-400 mt-1">8,500</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
            <Sparkles className="w-5 h-5" />
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
              Start an interactive session with the AI Architect to build your first system blueprint.
            </p>
            <Link
              href="/chat"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 hover:bg-indigo-500 transition-all"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Create First Solution</span>
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
            <span>Pre-Seeded Vertical Templates</span>
          </h4>
          <p className="text-xs text-slate-400">Click any template to bootstrap an architecture session instantly.</p>

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
    </div>
  );
}
