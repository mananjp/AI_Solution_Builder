'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import Navbar from '@/components/Navbar';
import { MobileBottomNav } from '@/components/MobileNav';

// Routes that own the whole viewport (chat, sandbox, file tree) and must not be
// boxed into the centered 1280px reading column.
const FULL_BLEED_ROUTES = ['/chat', '/sandbox'];

function isFullBleed(pathname: string | null): boolean {
  if (!pathname) return false;
  return FULL_BLEED_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const fullBleed = isFullBleed(pathname);

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)] flex flex-col">
      <Sidebar />
      <div className="flex min-h-screen flex-col lg:pl-[64px] flex-1">
        <Navbar />
        <main
          className={`flex-1 w-full mx-auto ${
            fullBleed
              ? 'p-2 sm:p-4 lg:p-6 max-w-[1500px] flex flex-col pb-20 lg:pb-6'
              : 'p-4 sm:p-6 lg:p-8 max-w-[1280px] pb-24 lg:pb-8'
          }`}
        >
          {children}
        </main>
      </div>
      <MobileBottomNav />
    </div>
  );
}
