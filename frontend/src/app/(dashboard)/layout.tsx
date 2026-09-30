'use client';

import type { ReactNode } from 'react';
import { usePathname } from 'next/navigation';

import { ShellProvider } from '@/components/ShellContext';
import Sidebar from '@/components/Sidebar';
import Navbar from '@/components/Navbar';
import { BYPASS_USER, isAuthBypassed } from '@/lib/auth-bypass';

// Routes that own the whole viewport (chat, sandbox, file tree) and must not be
// boxed into the centered reading column.
const FULL_BLEED_ROUTES = ['/chat', '/sandbox'];

function isFullBleed(pathname: string | null): boolean {
  if (!pathname) return false;
  return FULL_BLEED_ROUTES.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const fullBleed = isFullBleed(pathname);

  return (
    // A column, so the banner can sit above the shell.
    <div className="flex min-h-dvh w-full flex-col bg-background">
      {/* Unmissable while the bypass is on, so an unauthenticated build cannot be
          mistaken for a working one in a screenshot or a demo. */}
      {isAuthBypassed && (
        <div
          role="status"
          className="z-50 flex shrink-0 items-center justify-center gap-2 bg-[var(--amber)] px-4 py-1 text-[11px] font-bold uppercase tracking-widest text-[var(--background)]"
        >
          Auth bypassed — rendering as {BYPASS_USER.email}
        </div>
      )}

      {/* The row. The rail and the content column are siblings here and must
          stay that way: an earlier attempt put this wrapper in `flex-col`,
          which stacked them vertically so the content rendered underneath the
          rail at full width. */}
      <div className="flex min-h-0 flex-1">
        {/* No width here. The lab sidebar's `motion.nav` animates between 64px
            and 240px and this element is sized by it, so the content column
            reflows in step with the spring. Pinning the aside to a fixed
            `w-16`/`w-60` made it snap to the final width on the same frame as
            the click while the rail was still moving. Below md the rail is
            replaced by the navbar's drawer. */}
        <aside className="sticky top-0 hidden h-dvh shrink-0 overflow-hidden md:block">
          <Sidebar />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <Navbar />
          <main
            className={
              fullBleed
                ? 'flex-1 w-full min-w-0 px-2 py-3 sm:px-3 lg:px-4'
                : 'flex-1 w-full max-w-[1280px] mx-auto p-6 lg:p-8'
            }
          >
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <ShellProvider>
      <Shell>{children}</Shell>
    </ShellProvider>
  );
}
