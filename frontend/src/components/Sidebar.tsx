'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { 
  LayoutDashboard, 
  Sparkles, 
  Layers, 
  CreditCard, 
  Settings, 
  LogOut
} from 'lucide-react';
import { authApi } from '@/lib/api';

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const navItems = [
    { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
    { name: 'AI Architect Chat', href: '/chat', icon: Sparkles, badge: 'Agentic' },
    { name: 'Architecture Library', href: '/dashboard#blueprints', icon: Layers },
    { name: 'Billing & Credits', href: '/billing', icon: CreditCard },
    { name: 'Admin Governance', href: '/admin', icon: Settings, badge: 'Gov' },
  ];

  const handleLogout = () => {
    authApi.logout();
    router.push('/login');
  };

  return (
    <aside className="w-64 h-screen bg-[#0b0f19] border-r border-white/5 flex flex-col justify-between p-4 fixed left-0 top-0 z-40">
      <div>
        {/* Brand Header */}
        <Link href="/dashboard" className="flex items-center gap-3 px-2 py-3 mb-6 group">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/30 group-hover:scale-105 transition-transform">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-bold text-white text-base tracking-tight leading-tight">AI Solution</h1>
            <span className="text-xs text-indigo-400 font-medium tracking-wide uppercase">Builder OS</span>
          </div>
        </Link>

        {/* Navigation List */}
        <nav className="space-y-1.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href));
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-indigo-600/15 text-indigo-400 border border-indigo-500/30 shadow-inner'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-400' : 'text-slate-500'}`} />
                  <span>{item.name}</span>
                </div>
                {item.badge && (
                  <span className="px-2 py-0.5 text-[10px] uppercase tracking-wider rounded-full bg-indigo-500/20 text-indigo-300 font-semibold border border-indigo-500/30">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer / Account / Credits */}
      <div className="space-y-3 pt-4 border-t border-white/5">
        <div className="p-3 rounded-xl bg-gradient-to-br from-indigo-950/40 to-slate-900/60 border border-indigo-500/20">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="text-slate-400">Monthly AI Credits</span>
            <span className="text-indigo-300 font-semibold">8,500 / 10,000</span>
          </div>
          <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-indigo-500 to-cyan-400 rounded-full" style={{ width: '85%' }} />
          </div>
          <p className="text-[11px] text-slate-500 mt-2 flex items-center justify-between">
            <span>Enterprise Engine</span>
            <span className="text-emerald-400 font-medium">Groq 120B</span>
          </p>
        </div>

        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2 text-sm text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
}
