'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  Sparkles,
  Layers,
  CreditCard,
  Settings,
  LogOut,
  Rocket,
  Wrench,
  ChevronLeft,
} from 'lucide-react';
import { authApi, billingApi } from '@/lib/api';
import { BillingUsage, User } from '@/types';

const navItems = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Custom Builder', href: '/chat', icon: Wrench, badge: 'AI' },
  { name: 'BluePrints', href: '/dashboard#blueprints', icon: Layers },
  { name: 'Billing', href: '/billing', icon: CreditCard },
  { name: 'Deploy Keys', href: '/settings', icon: Rocket },
  { name: 'Admin', href: '/admin', icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    billingApi.getUsage().then(setUsage).catch(() => undefined);
    authApi.me().then(setCurrentUser).catch(() => undefined);
  }, [pathname]);

  const handleLogout = () => {
    authApi.logout();
    router.push('/login');
  };

  const isUnlimited = !usage?.current_balance;
  const creditPct = isUnlimited
    ? 100
    : Math.max(4, Math.min(100, Math.round(((usage?.current_balance ?? 0) / (usage?.monthly_limit ?? 10000)) * 100)));

  return (
    <aside
      className={`hidden lg:flex h-screen bg-[#0a0a0a] border-r border-[#1a1a1a] flex-col fixed left-0 top-0 z-40 transition-all duration-200 ${collapsed ? 'w-[56px] px-2 py-4' : 'w-[240px] px-3 py-4'
        }`}
    >
      {/* Top */}
      <div className="flex-1 flex flex-col min-h-0">
        {/* Brand row */}
        <div className={`flex items-center mb-6 ${collapsed ? 'justify-center' : 'justify-between px-1'}`}>
          {!collapsed && (
            <Link href="/dashboard" className="flex items-center gap-2 group">
              <div className="w-7 h-7 rounded-md bg-[#6366f1] flex items-center justify-center text-white shrink-0">
                <Sparkles className="w-3.5 h-3.5" />
              </div>
              <span className="text-sm font-semibold text-white tracking-tight">AI Builder</span>
            </Link>
          )}
          {collapsed && (
            <Link href="/dashboard">
              <div className="w-7 h-7 rounded-md bg-[#6366f1] flex items-center justify-center text-white">
                <Sparkles className="w-3.5 h-3.5" />
              </div>
            </Link>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={`w-6 h-6 rounded-md flex items-center justify-center text-[#555] hover:text-white hover:bg-[#1a1a1a] transition-colors ${collapsed ? 'mt-1' : ''}`}
            aria-label={collapsed ? 'Expand' : 'Collapse'}
          >
            <ChevronLeft className={`w-3.5 h-3.5 transition-transform ${collapsed ? 'rotate-180' : ''}`} />
          </button>
        </div>

        {/* Nav */}
        <nav className="space-y-0.5 flex-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              pathname === item.href ||
              (item.href !== '/dashboard' && pathname.startsWith(item.href.split('#')[0]));

            return (
              <Link
                key={item.name}
                href={item.href}
                title={collapsed ? item.name : undefined}
                className={`flex items-center gap-2.5 rounded-md text-[13px] transition-colors ${collapsed ? 'px-1.5 py-2 justify-center' : 'px-2.5 py-2'
                  } ${isActive
                    ? 'bg-[#161616] text-white'
                    : 'text-[#666] hover:text-[#a1a1a1] hover:bg-[#111]'
                  }`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-[#6366f1]' : ''}`} />
                {!collapsed && (
                  <>
                    <span className="flex-1 truncate">{item.name}</span>
                    {'badge' in item && item.badge && (
                      <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-[#6366f11a] text-[#818cf8] border border-[#6366f122]">
                        {item.badge}
                      </span>
                    )}
                  </>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Bottom */}
      <div className={`space-y-3 pt-3 border-t border-[#1a1a1a] ${collapsed ? 'px-0' : ''}`}>
        {/* Credit bar */}
        {!collapsed && (
          <div className="px-1">
            <div className="flex items-center justify-between text-[11px] mb-1.5">
              <span className="text-[#555]">Credits</span>
              <span className="text-[#a1a1a1] font-medium">
                {isUnlimited ? 'Unlimited' : `${usage?.current_balance?.toLocaleString()} left`}
              </span>
            </div>
            <div className="w-full h-1 bg-[#1a1a1a] rounded-full overflow-hidden">
              <div
                className="h-full bg-[#6366f1] rounded-full transition-all duration-500"
                style={{ width: `${creditPct}%` }}
              />
            </div>
          </div>
        )}

        {/* User */}
        <div className={`flex items-center gap-2.5 px-1 ${collapsed ? 'justify-center' : ''}`}>
          <div className="w-7 h-7 rounded-full bg-[#1c1c1c] border border-[#2e2e2e] flex items-center justify-center text-xs font-semibold text-white shrink-0">
            {currentUser?.full_name ? currentUser.full_name.charAt(0).toUpperCase() : 'A'}
          </div>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-white truncate leading-none">
                {currentUser?.full_name || 'Guest User'}
              </p>
              <p className="text-[11px] text-[#555] truncate mt-0.5">
                {currentUser?.email || 'demo mode'}
              </p>
            </div>
          )}
        </div>

        {/* Logout */}
        <button
          onClick={handleLogout}
          title={collapsed ? 'Sign out' : undefined}
          className={`w-full flex items-center gap-2 text-[13px] text-[#555] hover:text-[#f87171] hover:bg-[#ef444410] rounded-md transition-colors ${collapsed ? 'justify-center px-1.5 py-2' : 'px-2.5 py-2'
            }`}
        >
          <LogOut className="w-4 h-4 shrink-0" />
          {!collapsed && <span>Sign out</span>}
        </button>
      </div>
    </aside>
  );
}
