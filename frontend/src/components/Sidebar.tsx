'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  House,
  ChatsCircle,
  Books,
  CreditCard,
  Rocket,
  Gear,
  SignOut,
} from '@phosphor-icons/react/dist/ssr';
import { authApi } from '@/lib/api';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarSeparator,
  SidebarHeader,
} from '@/components/ui/sidebar';

const navItems = [
  { name: 'Dashboard', href: '/dashboard', icon: House },
  { name: 'Architect', href: '/chat', icon: ChatsCircle },
  { name: 'Library', href: '/dashboard', icon: Books },
  { name: 'Billing', href: '/billing', icon: CreditCard },
  { name: 'Deploy', href: '/settings', icon: Rocket },
  { name: 'Admin', href: '/admin', icon: Gear },
];

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
    authApi.logout();
    router.push('/login');
  };

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg">
              <div className="flex size-8 items-center justify-center shrink-0 rounded-lg bg-primary text-primary-foreground">
                <span className="font-bold text-xs">AS</span>
              </div>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">AI Solution</span>
                <span className="truncate text-xs text-muted-foreground">Builder</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive =
                  item.href === '/dashboard'
                    ? pathname === '/dashboard'
                    : pathname.startsWith(item.href);
                return (
                  <SidebarMenuItem key={item.name}>
                    <SidebarMenuButton
                      render={<Link href={item.href} />}
                      isActive={isActive}
                      tooltip={item.name}
                    >
                      <Icon weight="light" />
                      <span>{item.name}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarSeparator />
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              render={<button onClick={handleLogout} />}
              tooltip="Sign out"
            >
              <SignOut weight="light" />
              <span>Sign out</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
