'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Search, Bell, Plus } from 'lucide-react';
import { authApi, workspaceApi } from '@/lib/api';
import { User, Workspace } from '@/types';

export default function Navbar() {
  const [user, setUser] = useState<User | null>(null);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const u = await authApi.me();
        setUser(u);
        const ws = await workspaceApi.list();
        if (ws.length > 0) setActiveWorkspace(ws[0]);
      } catch {
        setUser({
          id: 'demo',
          email: 'demo@demo.com',
          full_name: 'Guest User',
          role: 'admin',
          org_id: 'demo-org',
          created_at: new Date().toISOString(),
        });
        setActiveWorkspace({
          id: 'default',
          org_id: 'demo-org',
          name: 'Primary Workspace',
          created_at: new Date().toISOString(),
        });
      }
    }
    load();
  }, []);

  return (
    <header className="h-[52px] border-b border-[#1a1a1a] bg-[#0a0a0a] sticky top-0 z-30 flex items-center gap-3 px-5 lg:ml-[240px]">
      {/* Workspace pill */}
      <div className="hidden sm:flex items-center gap-2 text-[13px] shrink-0">
        <span className="text-[#555]">Workspace</span>
        <span className="text-white font-medium">{activeWorkspace?.name ?? 'Primary'}</span>
      </div>

      {/* Search */}
      <div className="flex-1 max-w-[360px] mx-auto hidden md:block">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[#555]" />
          <input
            placeholder="Search blueprints..."
            className="w-full pl-8 pr-3 py-2 rounded-lg bg-[#111] border border-[#1a1a1a] text-[13px] text-[#a1a1a1] placeholder:text-[#444] focus:outline-none focus:border-[#2e2e2e] transition-colors"
          />
          <span className="absolute right-2 top-1/2 -translate-y-1/2 hidden lg:inline-flex px-1 py-0.5 rounded bg-[#1a1a1a] text-[10px] text-[#444]">⌘K</span>
        </div>
      </div>

      {/* Right */}
      <div className="ml-auto flex items-center gap-2">
        <button className="w-8 h-8 rounded-lg bg-[#111] border border-[#1a1a1a] hover:bg-[#161616] flex items-center justify-center text-[#555] hover:text-[#a1a1a1] transition-colors">
          <Bell className="w-3.5 h-3.5" />
        </button>

        <Link
          href="/chat"
          className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-[13px] font-medium transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          New Blueprint
        </Link>

        <div className="flex items-center gap-2 pl-1 border-l border-[#1a1a1a] ml-1">
          <div className="w-7 h-7 rounded-full bg-[#1c1c1c] border border-[#2e2e2e] flex items-center justify-center text-xs font-semibold text-white">
            {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'G'}
          </div>
          <span className="hidden md:block text-[13px] text-[#a1a1a1]">
            {user?.full_name ?? 'Guest'}
          </span>
        </div>
      </div>
    </header>
  );
}
