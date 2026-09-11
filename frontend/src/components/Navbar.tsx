'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Sparkles, Database, Plus } from 'lucide-react';
import { authApi, workspaceApi } from '@/lib/api';
import { User, Workspace } from '@/types';

export default function Navbar() {
  const [user, setUser] = useState<User | null>(null);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const u = await authApi.me();
        setUser(u);
        const ws = await workspaceApi.list();
        if (ws.length > 0) {
          setActiveWorkspace(ws[0]);
        }
      } catch {
        // Fallback demo user if not yet authenticated
        setUser({
          id: 'demo-user',
          email: 'architect@enterprise.io',
          full_name: 'Lead Architect',
          role: 'admin',
          org_id: 'demo-org',
          created_at: '2025-01-01T00:00:00Z',
        });
        setActiveWorkspace({
          id: 'default',
          org_id: 'demo-org',
          name: 'Primary Workspace',
          created_at: '2025-01-01T00:00:00Z',
        });
      }
    }
    loadData();
  }, []);

  return (
    <header className="h-16 border-b border-white/5 bg-[#0b0f19]/80 backdrop-blur-xl sticky top-0 z-30 px-6 flex items-center justify-between ml-64">
      {/* Workspace Switcher */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-white/5 text-sm">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-slate-400 text-xs">Workspace:</span>
          <span className="text-slate-200 font-medium text-xs">
            {activeWorkspace?.name || 'Default Workspace'}
          </span>
        </div>

        {/* Database & LLM status pills */}
        <div className="hidden lg:flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.03] border border-white/5 text-[11px] text-slate-400">
            <Database className="w-3.5 h-3.5 text-sky-400" />
            <span>PostgreSQL (Docker)</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white/[0.03] border border-white/5 text-[11px] text-slate-400">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span>Groq OSS 120B</span>
          </div>
        </div>
      </div>

      {/* Action Buttons & User Profile */}
      <div className="flex items-center gap-4">
        <Link
          href="/chat"
          className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white shadow-md shadow-indigo-500/20 transition-all hover:scale-105"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Blueprint</span>
        </Link>

        <div className="h-5 w-[1px] bg-white/10" />

        {/* User Pill */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-xs font-bold text-white shadow-inner">
            {user?.full_name ? user.full_name.charAt(0) : 'U'}
          </div>
          <div className="hidden md:block text-left">
            <p className="text-xs font-medium text-slate-200 leading-none">
              {user?.full_name || 'Architect'}
            </p>
            <p className="text-[10px] text-slate-500 mt-1 leading-none">
              {user?.email || 'architect@enterprise.io'}
            </p>
          </div>
        </div>
      </div>
    </header>
  );
}
