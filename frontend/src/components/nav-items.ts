'use client';

import { useMemo } from 'react';
import { usePathname } from 'next/navigation';
import {
  CreditCard,
  GitFork,
  Layers,
  LayoutDashboard,
  Rocket,
  Settings,
  Wrench,
} from 'lucide-react';

import { useAuthSession } from '@/components/auth/AuthProvider';
import { useI18n } from '@/components/I18nProvider';

export type NavItem = {
  key: string;
  href: string;
  icon: typeof LayoutDashboard;
  /** Short uppercase marker shown beside the label on the expanded rail. */
  badge?: string;
  /** Restrict to these roles. Hidden rather than disabled, so the nav does not
   *  advertise a page that would only answer 403. */
  roles?: readonly string[];
};

export const NAV_ITEMS: NavItem[] = [
  { key: 'dashboard', href: '/dashboard', icon: LayoutDashboard },
  { key: 'customBuilder', href: '/chat', icon: Wrench, badge: 'AI' },
  { key: 'legacyModernizer', href: '/legacy-modernizer', icon: GitFork, badge: 'NEW' },
  { key: 'solutions', href: '/dashboard#blueprints', icon: Layers },
  { key: 'billing', href: '/billing', icon: CreditCard },
  { key: 'deployKeys', href: '/settings', icon: Rocket },
  {
    key: 'admin',
    href: '/admin',
    icon: Settings,
    roles: ['admin', 'owner', 'superadmin'],
  },
];

/** Roles that may see the admin surface. Mirrors backend security.py. */
export const ADMIN_ROLES: readonly string[] = ['admin', 'owner', 'superadmin'];

export type ResolvedNavItem = NavItem & { label: string; active: boolean };

/**
 * Single source of truth for the navigation, shared by the docked rail and the
 * mobile drawer so the two can never list different destinations or disagree
 * about which one is current.
 */
export function useNavItems(): ResolvedNavItem[] {
  const pathname = usePathname();
  const { t } = useI18n();
  const { user } = useAuthSession();

  return useMemo(() => {
    const isActive = (href: string) => {
      const [path] = href.split('#');
      return pathname === path || (path !== '/dashboard' && pathname.startsWith(path));
    };

    return NAV_ITEMS.filter((item) => !item.roles || (user && item.roles.includes(user.role))).map(
      (item) => ({
        ...item,
        label: t(`side.${item.key}` as never),
        active: isActive(item.href),
      }),
    );
  }, [pathname, t, user]);
}
