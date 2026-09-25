'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  Layers,
  CreditCard,
  Settings,
  LogOut,
  Rocket,
  Wrench,
} from 'lucide-react';
import { authApi } from '@/lib/api';
import { User } from '@/types';
import { useI18n } from '@/components/I18nProvider';

type NavItem = {
  name: string;
  key: 'dashboard' | 'customBuilder' | 'solutions' | 'billing' | 'deployKeys' | 'admin';
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
};

const navItems: NavItem[] = [
  { name: 'Dashboard', key: 'dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Custom Builder', key: 'customBuilder', href: '/chat', icon: Wrench, badge: 'AI' },
  { name: 'Solutions', key: 'solutions', href: '/dashboard#blueprints', icon: Layers },
  { name: 'Billing', key: 'billing', href: '/billing', icon: CreditCard },
  { name: 'Deploy Keys', key: 'deployKeys', href: '/settings', icon: Rocket },
  { name: 'Admin', key: 'admin', href: '/admin', icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useI18n();
  const [currentUser, setCurrentUser] = useState<User | null>(null);

  useEffect(() => {
    authApi.me().then(setCurrentUser).catch(() => undefined);
  }, [pathname]);

  const handleLogout = () => {
    authApi.logout();
    router.push('/login');
  };

  return (
    <aside className="hidden lg:flex h-screen bg-[var(--bg-2)] border-r border-[var(--border)] flex-col fixed left-0 top-0 z-40 w-[64px] py-6">
      {/* Top */}
      <div className="flex-1 flex flex-col min-h-0">
        {/* Brand row */}
        <div className="flex mb-8 flex-col items-center gap-4 w-full">
          <Link href="/dashboard" className="group w-full flex justify-center relative group/logo">
            <div className="flex items-center justify-center shrink-0 pt-1">
              <span className="text-[var(--sutra-muted-gold)] font-sanskrit font-bold text-3xl leading-none drop-shadow-sm">सूत्र</span>
            </div>
            {/* Tooltip */}
            <div className="absolute left-[110%] ml-2 px-2 py-1 bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)] text-[10px] uppercase tracking-widest font-bold rounded-sm opacity-0 pointer-events-none group-hover/logo:opacity-100 transition-opacity whitespace-nowrap z-50 shadow-sm border border-[var(--border)]">
              SUTRA OS
            </div>
          </Link>
        </div>

        {/* Nav */}
        <nav className="space-y-2 flex-1 w-full px-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              pathname === item.href ||
              (item.href !== '/dashboard' && pathname.startsWith(item.href.split('#')[0]));

            return (
              <div key={item.key} className="relative group/nav flex items-center justify-center w-full">
                <Link
                  href={item.href}
                  className={`flex items-center justify-center w-10 h-10 rounded-sm transition-all duration-200 ${
                    isActive
                      ? 'bg-[var(--sutra-soft-cream)] text-[var(--sutra-charcoal)]'
                      : 'text-[var(--text-2)] hover:text-[var(--text)] hover:bg-[var(--bg)]'
                  }`}
                >
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-[var(--sutra-muted-gold)]' : ''}`} />
                </Link>
                {/* Tooltip */}
                <div className="absolute left-[110%] ml-2 px-2 py-1 bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)] text-[10px] uppercase tracking-widest font-bold rounded-sm opacity-0 pointer-events-none group-hover/nav:opacity-100 transition-opacity whitespace-nowrap z-50 shadow-sm border border-[var(--border)]">
                  {t(`side.${item.key}` as const)} {item.badge && <span className="ml-1 text-[var(--sutra-muted-gold)]">({item.badge})</span>}
                </div>
              </div>
            );
          })}
        </nav>
      </div>

      {/* Bottom */}
      <div className="space-y-4 pt-6 border-t border-[var(--border)] flex flex-col items-center">
        {/* User */}
        <div className="relative group/user flex items-center justify-center w-full">
          <div className="w-8 h-8 bg-[var(--sutra-charcoal)] flex items-center justify-center text-xs font-serif text-[var(--sutra-warm-ivory)] shrink-0 cursor-help">
            {currentUser?.full_name ? currentUser.full_name.charAt(0).toUpperCase() : 'G'}
          </div>
          {/* Tooltip */}
          <div className="absolute left-[110%] ml-2 px-2 py-1 bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)] text-[10px] uppercase tracking-widest font-bold rounded-sm opacity-0 pointer-events-none group-hover/user:opacity-100 transition-opacity whitespace-nowrap z-50 shadow-sm border border-[var(--border)]">
            {currentUser?.full_name || t('side.guestUser')}
          </div>
        </div>

        {/* Logout */}
        <div className="w-full px-2 flex justify-center">
          <div className="relative group/logout flex items-center justify-center w-full">
            <button
              onClick={handleLogout}
              className="flex items-center justify-center w-10 h-10 rounded-sm text-[var(--text-2)] hover:text-[#C53B3B] hover:bg-[#C53B3B10] transition-colors"
            >
              <LogOut className="w-4 h-4 shrink-0" />
            </button>
            {/* Tooltip */}
            <div className="absolute left-[110%] ml-2 px-2 py-1 bg-[#C53B3B] text-[var(--sutra-warm-ivory)] text-[10px] uppercase tracking-widest font-bold rounded-sm opacity-0 pointer-events-none group-hover/logout:opacity-100 transition-opacity whitespace-nowrap z-50 shadow-sm border border-[var(--border)]">
              {t('side.signOut')}
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
