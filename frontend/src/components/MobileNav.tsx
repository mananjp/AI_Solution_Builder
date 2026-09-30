'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Menu } from 'lucide-react';
import { useShell } from '@/components/ShellContext';
import { useNavItems } from '@/components/nav-items';

/**
 * Mobile navigation drawer.
 *
 * Below `md` the docked rail is hidden and this drawer takes over, listing the
 * same destinations from the same `useNavItems` source, so the two cannot drift.
 * The trigger is exported so the navbar can own the single toggle affordance.
 */
export function MobileNav({ trigger }: { trigger?: React.ReactNode }) {
  const pathname = usePathname();
  const items = useNavItems();
  const { navOpen, setNavOpen } = useShell();

  return (
    <Sheet open={navOpen} onOpenChange={setNavOpen}>
      {trigger ?? (
        <SheetTrigger asChild>
          <Button variant="outline" size="icon-sm" aria-label="Open navigation" className="md:hidden">
            <Menu />
          </Button>
        </SheetTrigger>
      )}
      <SheetContent side="left" className="flex flex-col gap-0 p-0">
        <SheetHeader className="border-b border-border px-4 py-4">
          <SheetTitle className="font-sanskrit text-xl text-foreground">सूत्र</SheetTitle>
        </SheetHeader>
        <nav className="flex flex-col gap-1 p-3" aria-label="Main">
          {items.map((item) => (
            <Link
              key={item.key}
              href={item.href}
              // Any navigation closes the drawer, so the next screen does not
              // open with the previous one still layered over it.
              onClick={() => setNavOpen(false)}
              aria-current={pathname === item.href.split('#')[0] ? 'page' : undefined}
              className={`flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors ${
                item.active
                  ? 'bg-surface text-foreground'
                  : 'text-muted hover:bg-surface hover:text-foreground'
              }`}
            >
              <item.icon className="size-5 shrink-0" aria-hidden />
              <span className="truncate">{item.label}</span>
              {item.badge && (
                <span className="ml-auto text-[10px] font-bold uppercase tracking-widest text-foreground">
                  {item.badge}
                </span>
              )}
            </Link>
          ))}
        </nav>
      </SheetContent>
    </Sheet>
  );
}
