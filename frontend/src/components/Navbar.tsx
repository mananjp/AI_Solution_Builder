'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { FolderKanban, LogOut, PanelLeft, Plus, Settings } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { CommandPalette, type Command } from '@/components/lab/command-palette';
import {
  DropdownMenu as LabDropdownMenu,
  type DropdownItem,
} from '@/components/lab/dropdown-menu';
import { workspaceApi } from '@/lib/api';
import type { Workspace } from '@/types';
import { useI18n } from '@/components/I18nProvider';
import { LanguageSelector } from '@/components/LanguageSelector';
import { ThemeToggleButton } from '@/components/ThemeToggle';
import { MobileNav } from '@/components/MobileNav';
import { useShell } from '@/components/ShellContext';
import { useNavItems } from '@/components/nav-items';
import { useAuthSession } from '@/components/auth/AuthProvider';
import { UserAvatar } from '@/components/UserAvatar';
import { Badge } from '@/components/ui/badge';
import { logError } from '@/lib/logger';

export default function Navbar() {
  const { t } = useI18n();
  const { railExpanded, setRailExpanded } = useShell();
  const navItems = useNavItems();
  // The user comes from the single app-level session rather than a per-component
  // /auth/me call. Previously each component fetched independently, and on
  // failure this one fabricated `role: 'admin'` for a "Guest User", which made
  // an anonymous visitor look authenticated in the UI while the API rejected
  // every request.
  const { user, avatarUrl, isLoading, logout } = useAuthSession();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);

  useEffect(() => {
    // Wait for the session: fetching before the token provider is registered
    // would 401 and leave the workspace permanently unset.
    if (!user) return;
    let cancelled = false;
    void (async () => {
      try {
        const ws = await workspaceApi.list();
        if (!cancelled && ws.length > 0) {
          setWorkspaces(ws);
          setActiveWorkspace(ws[0]);
        }
      } catch (err) {
        logError('failed to load workspaces', err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  // Initials are handled inside UserAvatar now, which also takes the Auth0
  // picture when the connection supplies one.

  // The active workspace is already shown on the trigger, so it is not repeated
  // as a row. Selecting it again is a no-op rather than a state change.
  const workspaceItems = workspaces.filter((ws) => ws.id !== activeWorkspace?.id);

  // The navbar's own search is a command palette rather than a dead text input.
  // It lists every destination plus the two actions that create work, so the
  // hint on the trigger is a real shortcut instead of decoration.
  const commands = useMemo<Command[]>(
    () => [
      ...navItems.map((item) => ({
        id: `nav:${item.key}`,
        label: item.label,
        group: 'Go to',
        icon: <item.icon className="size-4" aria-hidden />,
      })),
      {
        id: 'action:new-solution',
        label: t('common.newSolution'),
        group: 'Create',
        icon: <Plus className="size-4" aria-hidden />,
      },
      {
        id: 'action:settings',
        label: t('side.deployKeys'),
        group: 'Create',
        icon: <Settings className="size-4" aria-hidden />,
      },
    ],
    [navItems, t],
  );

  const onRun = (command: Command) => {
    if (command.id.startsWith('nav:')) {
      const item = navItems.find((candidate) => `nav:${candidate.key}` === command.id);
      if (item) window.location.assign(item.href);
      return;
    }
    window.location.assign(
      command.id === 'action:new-solution' ? '/chat?new=true' : '/settings',
    );
  };

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b bg-background px-4 sm:px-6">
      {/* Below md the rail is hidden and the drawer takes over, so this opens
          navigation. Above md there is no drawer, and this same position widens
          the docked rail instead. Two controls, each scoped to the breakpoint
          where its job exists, so the desktop rail is never stuck collapsed. */}
      <MobileNav />

      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={railExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
        aria-expanded={railExpanded}
        onClick={() => setRailExpanded(!railExpanded)}
        className="hidden text-muted md:inline-flex"
      >
        <PanelLeft />
      </Button>

      <div className="relative hidden w-full max-w-72 md:block">
        <CommandPalette
          commands={commands}
          onRun={onRun}
          placeholder={t('common.searchPlaceholder')}
        />
      </div>

      {/* The lab dropdown renders its own trigger, so it carries the workspace
          label itself rather than being wrapped in a button. */}
      <div className="hidden sm:block">
        <LabDropdownMenu
          label={activeWorkspace?.name ?? t('common.primary')}
          items={[
            ...(activeWorkspace
              ? ([{ label: activeWorkspace.name, shortcut: 'Active' }] satisfies DropdownItem[])
              : [{ label: 'No workspace yet', icon: <FolderKanban className="size-4" /> }]),
            { type: 'separator' },
            ...workspaceItems.map<DropdownItem>((ws) => ({
              label: ws.name,
              icon: <FolderKanban className="size-4" />,
            })),
          ] satisfies DropdownItem[]}
          onSelect={(label: string) => {
            const match = workspaces.find((ws) => ws.name === label);
            if (match) setActiveWorkspace(match);
          }}
        />
      </div>

      <div className="ml-auto flex items-center gap-2">
        <LanguageSelector />

        {/* Colour scheme. Sits with the other global controls because it is one:
           every token in globals.css is a light-dark() pair resolving against
           this single decision, not a per-page setting. */}
        <ThemeToggleButton />

        {/* There is no notification source behind a bell in this app yet, so the
            button was removed rather than left as a control that does nothing.
            When an endpoint lands, the lab's `NotificationBell` already renders
            the list, the unread marker and click-away handling. */}

        <Button asChild size="sm" className="hidden uppercase tracking-widest sm:inline-flex">
          <Link href="/chat?new=true">
            <Plus />
            {t('common.newSolution')}
          </Link>
        </Button>

        <Separator orientation="vertical" className="mx-1 hidden h-6 sm:block" />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            {/* Not `ghost`: that is transparent until hover, which left the
                account control reading as a loose avatar floating in the header.
                The plain `--border` hairline is too faint to delineate a control
                on `--surface` in light mode, so this uses the stronger one. */}
            <Button
              variant="outline"
              size="sm"
              className="gap-2 border-[var(--border-2)] bg-surface px-2 hover:bg-[var(--bg-2)]"
              aria-label={user?.full_name ?? user?.email ?? 'Account menu'}
            >
              {isLoading ? (
                <Skeleton className="size-7 rounded-full" />
              ) : (
                <UserAvatar
                  name={user?.full_name}
                  email={user?.email}
                  src={avatarUrl}
                  size={28}
                />
              )}
              <span className="hidden max-w-40 truncate md:inline">
                {user?.full_name ?? user?.email ?? ''}
              </span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-72">
            {/* The identity, not just a name and role. */}
            <DropdownMenuLabel className="flex items-center gap-3 py-3">
              <UserAvatar
                name={user?.full_name}
                email={user?.email}
                src={avatarUrl}
                size={40}
              />
              <span className="flex min-w-0 flex-col gap-0.5">
                <span className="truncate font-semibold">
                  {user?.full_name ?? user?.email ?? 'Signed in'}
                </span>
                {user?.email && user?.full_name && (
                  <span className="truncate text-[11px] font-normal text-muted">
                    {user.email}
                  </span>
                )}
                <span className="flex flex-wrap items-center gap-1.5 text-[10px] font-normal uppercase tracking-wider">
                  {user?.role && (
                    <Badge variant="secondary" className="text-[9px]">
                      {user.role}
                    </Badge>
                  )}
                  {user?.email_verified === false && (
                    <span className="text-[var(--amber)]">unverified email</span>
                  )}
                  {user?.is_anonymous && (
                    <span className="text-[var(--muted)]">anonymous</span>
                  )}
                </span>
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {user?.org_id && (
              <>
                <DropdownMenuItem asChild>
                  <Link href="/settings" className="flex-col items-start gap-0">
                    <span>Organisation</span>
                    <span className="font-mono text-[10px] text-muted">
                      {user.org_id}
                    </span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
              </>
            )}
            <DropdownMenuItem asChild>
              <Link href="/settings">{t('side.deployKeys')}</Link>
            </DropdownMenuItem>
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              onSelect={() => {
                void logout();
              }}
            >
              <LogOut className="size-4" aria-hidden />
              {t('side.signOut')}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
