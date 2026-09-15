'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Plus } from '@phosphor-icons/react/dist/ssr';
import { authApi, workspaceApi } from '@/lib/api';
import { User, Workspace } from '@/types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { SidebarTrigger } from '@/components/ui/sidebar';

export default function Navbar() {
  const [user, setUser] = useState<User | null>(null);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const u = await authApi.me();
        setUser(u);
        const ws = await workspaceApi.list();
        if (ws.length > 0) setActiveWorkspace(ws[0]);
      } catch {
        // User data unavailable
      }
    }
    loadData();
  }, []);

  return (
    <header className="h-11 border-b border-border bg-background/90 backdrop-blur-xl sticky top-0 z-30 px-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <SidebarTrigger className="-ml-1" />
        <Separator orientation="vertical" className="h-4" />
        <Badge variant="secondary" className="font-mono text-[10px] px-2 py-0.5">
          {activeWorkspace?.name || 'Default'}
        </Badge>
      </div>

      <div className="flex items-center gap-3">
        <Button render={<Link href="/chat" />} nativeButton={false} size="sm" className="text-[11px] font-medium px-3 h-7">
            <Plus className="size-3 mr-1" weight="bold" />
            New
        </Button>

        <Separator orientation="vertical" className="h-4" />

        <div className="flex items-center gap-2">
          <Avatar className="size-6">
            <AvatarFallback className="text-[10px] font-semibold bg-primary/15 text-primary border border-primary/20">
              {user?.full_name?.charAt(0) || 'U'}
            </AvatarFallback>
          </Avatar>
          <span className="hidden md:block text-[11px] text-muted-foreground">
            {user?.full_name || 'Architect'}
          </span>
        </div>
      </div>
    </header>
  );
}
