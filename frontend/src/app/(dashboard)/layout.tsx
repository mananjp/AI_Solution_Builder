'use client';

import React from 'react';
import { usePathname } from 'next/navigation';
import Sidebar from '@/components/Sidebar';
import Navbar from '@/components/Navbar';

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
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <Sidebar />
      <div className="flex min-h-screen flex-col lg:pl-[64px]">
        <Navbar />
        <main
          className={
            fullBleed
              ? 'flex-1 w-full min-w-0 px-2 py-3 sm:px-3 lg:px-4'
              : 'flex-1 p-6 lg:p-8 max-w-[1280px] w-full mx-auto'
          }
        >
          {children}
        </main>
      </div>
    </div>
  );
}
