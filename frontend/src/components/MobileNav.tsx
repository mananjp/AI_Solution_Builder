'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  Layers,
  CreditCard,
  Settings,
  LogOut,
  Sparkles,
  Menu,
  X,
  Plus,
  Shield,
} from 'lucide-react';
import { authApi } from '@/lib/api';
import { User, Workspace } from '@/types';
import { useI18n } from '@/components/I18nProvider';

interface MobileNavProps {
  user: User | null;
  activeWorkspace: Workspace | null;
}

function isNavActive(pathname: string, currentHash: string, targetHref: string): boolean {
  if (targetHref === '/dashboard') {
    return (pathname === '/dashboard' || pathname === '/') && currentHash !== '#blueprints';
  }
  if (targetHref === '/dashboard#blueprints') {
    return pathname === '/dashboard' && currentHash === '#blueprints';
  }
  if (targetHref.includes('#')) {
    const [path, hash] = targetHref.split('#');
    return pathname === path && currentHash === `#${hash}`;
  }
  return pathname === targetHref || pathname.startsWith(`${targetHref}/`);
}

export function MobileNavDrawer({ user, activeWorkspace }: MobileNavProps) {
  const [isOpen, setIsOpen] = useState(false);
  const pathname = usePathname();
  const [currentHash, setCurrentHash] = useState('');
  const router = useRouter();
  const { t } = useI18n();

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setCurrentHash(window.location.hash);
      const onHashChange = () => setCurrentHash(window.location.hash);
      window.addEventListener('hashchange', onHashChange);
      return () => window.removeEventListener('hashchange', onHashChange);
    }
  }, [pathname]);

  const handleLogout = () => {
    authApi.logout();
    setIsOpen(false);
    router.push('/login');
  };

  const navItems = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'AI Build Architect', href: '/chat', icon: Sparkles, badge: 'AI' },
    { name: 'Solution Blueprints', href: '/dashboard#blueprints', icon: Layers },
    { name: 'Billing & Usage', href: '/billing', icon: CreditCard },
    { name: 'Deploy Keys & Mobile', href: '/settings', icon: Settings },
    { name: 'System Admin', href: '/admin', icon: Shield },
  ];

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="lg:hidden p-2 -ml-2 rounded-sm text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--bg-2)] transition-colors"
        aria-label="Toggle navigation menu"
      >
        {isOpen ? <X className="w-5 h-5 text-[var(--sutra-muted-gold)]" /> : <Menu className="w-5 h-5" />}
      </button>

      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-50 lg:hidden animate-fade-in"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* Drawer */}
      <aside
        className={`fixed top-0 left-0 bottom-0 w-[280px] bg-[var(--bg-2)] border-r border-[var(--border)] z-50 lg:hidden flex flex-col transform transition-transform duration-300 ease-in-out shadow-2xl ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="p-4 border-b border-[var(--border)] flex items-center justify-between">
          <Link
            href="/dashboard"
            onClick={() => setIsOpen(false)}
            className="flex items-center gap-2.5"
          >
            <span className="text-[var(--sutra-muted-gold)] font-sanskrit font-bold text-2xl leading-none">
              सूत्र
            </span>
            <div className="flex flex-col">
              <span className="font-serif font-bold text-sm tracking-wider text-[var(--sutra-charcoal)]">
                SUTRA OS
              </span>
              <span className="text-[10px] text-[var(--text-3)] font-mono">
                Autonomous Architecture
              </span>
            </div>
          </Link>
          <button
            onClick={() => setIsOpen(false)}
            className="p-1.5 rounded-sm hover:bg-[var(--bg)] text-[var(--text-2)] hover:text-[var(--text)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Workspace Pill on Mobile */}
        {activeWorkspace && (
          <div className="px-4 py-3 border-b border-[var(--border)] bg-[var(--bg)] flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider text-[var(--text-3)] font-semibold">
              Workspace
            </span>
            <span className="text-xs font-medium text-[var(--sutra-muted-gold)] font-mono">
              {activeWorkspace.name}
            </span>
          </div>
        )}

        {/* Navigation Links */}
        <nav className="flex-1 p-3 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = isNavActive(pathname, currentHash, item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setIsOpen(false)}
                className={`flex items-center justify-between px-3 py-2.5 rounded-sm text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-[var(--sutra-soft-cream)] text-[var(--sutra-charcoal)] font-semibold shadow-xs'
                    : 'text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--bg)]'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon
                    className={`w-4 h-4 ${
                      isActive ? 'text-[var(--sutra-muted-gold)]' : 'text-[var(--text-3)]'
                    }`}
                  />
                  <span>{item.name}</span>
                </div>
                {item.badge && (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[var(--sutra-muted-gold)]/15 text-[var(--sutra-muted-gold)] font-bold">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* New Solution Button */}
        <div className="p-3 border-t border-[var(--border)]">
          <Link
            href="/chat"
            onClick={() => setIsOpen(false)}
            className="btn btn-primary w-full justify-center py-2.5 text-xs font-semibold uppercase tracking-wider"
          >
            <Plus className="w-4 h-4" />
            <span>New Architecture</span>
          </Link>
        </div>

        {/* Footer / User Profile */}
        <div className="p-3 border-t border-[var(--border)] bg-[var(--bg)] flex items-center justify-between">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-sm bg-[var(--sutra-charcoal)] flex items-center justify-center text-xs font-serif text-[var(--sutra-warm-ivory)] shrink-0 shadow-sm">
              {user?.full_name ? user.full_name.charAt(0).toUpperCase() : 'G'}
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-medium text-[var(--text)] truncate">
                {user?.full_name ?? 'Guest User'}
              </span>
              <span className="text-[10px] text-[var(--text-3)] truncate">
                {user?.email ?? 'demo@demo.com'}
              </span>
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="p-2 rounded-sm text-[var(--text-3)] hover:text-red-500 hover:bg-red-500/10 transition-colors"
            title="Log Out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </aside>
    </>
  );
}

export function MobileBottomNav() {
  const pathname = usePathname();
  const [currentHash, setCurrentHash] = useState('');

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setCurrentHash(window.location.hash);
      const onHashChange = () => setCurrentHash(window.location.hash);
      window.addEventListener('hashchange', onHashChange);
      return () => window.removeEventListener('hashchange', onHashChange);
    }
  }, [pathname]);

  const bottomItems = [
    { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { label: 'AI Build', href: '/chat', icon: Sparkles },
    { label: 'Solutions', href: '/dashboard#blueprints', icon: Layers },
    { label: 'Settings', href: '/settings', icon: Settings },
  ];

  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-40 bg-[var(--bg-2)]/95 backdrop-blur-md border-t border-[var(--border)] flex items-center justify-around px-2 py-2 shadow-[0_-4px_16px_rgba(0,0,0,0.06)] pb-[max(0.5rem,env(safe-area-inset-bottom))]">
      {bottomItems.map((item) => {
        const Icon = item.icon;
        const isActive = isNavActive(pathname, currentHash, item.href);

        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex flex-col items-center justify-center flex-1 py-1 transition-all relative ${
              isActive
                ? 'text-[var(--sutra-muted-gold)] font-semibold'
                : 'text-[var(--text-3)] hover:text-[var(--text-2)]'
            }`}
          >
            <div className="relative">
              <Icon
                className={`w-5 h-5 transition-transform duration-200 ${
                  isActive
                    ? 'text-[var(--sutra-muted-gold)] scale-110 drop-shadow-xs'
                    : 'text-[var(--text-3)]'
                }`}
              />
            </div>
            <span
              className={`text-[10px] tracking-tight mt-1 transition-colors ${
                isActive
                  ? 'text-[var(--sutra-charcoal)] dark:text-[var(--sutra-warm-ivory)] font-bold'
                  : 'text-[var(--text-3)]'
              }`}
            >
              {item.label}
            </span>
            {isActive && (
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--sutra-muted-gold)] mt-0.5 animate-fade-in" />
            )}
          </Link>
        );
      })}
    </nav>
  );
}
