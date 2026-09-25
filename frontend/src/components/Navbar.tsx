'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Search, Bell, Plus } from 'lucide-react';
import { authApi, workspaceApi } from '@/lib/api';
import { User, Workspace } from '@/types';
import { useI18n } from '@/components/I18nProvider';
import { LanguageSelector } from '@/components/LanguageSelector';

export default function Navbar() {
  const { t } = useI18n();
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
    <header className="h-[52px] border-b border-[var(--border)] bg-[var(--bg)] sticky top-0 z-30 flex items-center gap-4 px-6 lg:ml-[64px]">
      {/* Workspace pill */}
      <div className="hidden sm:flex items-center gap-3 text-[12px] shrink-0 uppercase tracking-widest text-[var(--text-2)] font-semibold">
        <span>{t('common.workspace')}</span>
        <span className="w-1 h-1 bg-[var(--border-2)] rounded-full"></span>
        <span className="text-[var(--text)]">{activeWorkspace?.name ?? t('common.primary')}</span>
      </div>

      {/* Search */}
      <div className="flex-1 max-w-[400px] mx-auto hidden md:block">
        <div className="relative group">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-3)] group-focus-within:text-[var(--sutra-muted-gold)] transition-colors" />
          <input
            placeholder={t('common.searchPlaceholder')}
            className="w-full pl-9 pr-3 py-1.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] text-[13px] text-[var(--text)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors shadow-sm"
          />
          <span className="absolute right-2 top-1/2 -translate-y-1/2 hidden lg:inline-flex px-1.5 py-0.5 rounded-sm border border-[var(--border)] bg-[var(--bg)] text-[10px] text-[var(--text-2)] font-mono">⌘K</span>
        </div>
      </div>

      {/* Right */}
      <div className="ml-auto flex items-center gap-3">
        <LanguageSelector />

        <button className="w-8 h-8 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] flex items-center justify-center text-[var(--text-2)] hover:text-[var(--text)] transition-colors shadow-sm">
          <Bell className="w-4 h-4" />
        </button>

        <Link
          href="/chat"
          className="btn btn-primary rounded-sm text-[11px] uppercase tracking-widest px-4 py-1.5 hidden sm:flex"
        >
          <Plus className="w-3.5 h-3.5" />
          {t('common.newSolution')}
        </Link>

        <div className="flex items-center gap-3 pl-3 border-l border-[var(--border)]">
          <div className="w-8 h-8 rounded-sm bg-[var(--sutra-charcoal)] flex items-center justify-center text-xs font-serif text-[var(--sutra-warm-ivory)] shadow-sm">
            {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'G'}
          </div>
          <span className="hidden md:block text-[12px] font-medium text-[var(--text)]">
            {user?.full_name ?? t('common.guest')}
          </span>
        </div>
      </div>
    </header>
  );
}
