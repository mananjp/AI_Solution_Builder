'use client';

import React, { useState, useEffect } from 'react';
import { ShieldCheck, Users, Buildings, Stack, Clock, MagnifyingGlass, Cpu } from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/utils';
import { adminApi } from '@/lib/api';
import { AdminStats, AdminUser, AuditLogEntry } from '@/types';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';

export default function AdminGovernancePage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [searchUser, setSearchUser] = useState('');

  useEffect(() => {
    async function loadAdminData() {
      try {
        const [st, uList, logs] = await Promise.all([
          adminApi.getStats(),
          adminApi.getUsers(),
          adminApi.getAuditLogs(),
        ]);
        setStats(st);
        setUsers(uList);
        setAuditLogs(logs);
      } catch {
        // Admin data unavailable
      }
    }

    loadAdminData();
  }, []);

  const filteredUsers = users.filter(
    (u) =>
      u.email.toLowerCase().includes(searchUser.toLowerCase()) ||
      (u.full_name && u.full_name.toLowerCase().includes(searchUser.toLowerCase())),
  );

  return (
    <div className="p-6 lg:p-8 gap-8 max-w-6xl mx-auto flex flex-col">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/20 text-primary">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <CardTitle>Enterprise Governance & Admin</CardTitle>
                  <Badge variant="outline" className="border-green-500/30 text-green-500">
                    Superadmin Active
                  </Badge>
                </div>
                <CardDescription>
                  Platform telemetry, tenant organizations, user roles, and security audit logs.
                </CardDescription>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Badge variant="secondary" className="gap-1.5 font-mono">
                <Cpu className="h-3.5 w-3.5 text-primary" />
                {stats?.active_llm_model || 'Groq 120B'}
              </Badge>
              <Badge variant="secondary" className="gap-1.5 font-mono text-green-500">
                {stats?.system_status || 'SLO 99.98%'}
              </Badge>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">Total Users</CardDescription>
            <Users className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{stats?.total_users || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">Tenant Organizations</CardDescription>
            <Buildings className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{stats?.total_organizations || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">Synthesized Solutions</CardDescription>
            <Stack className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{stats?.total_solutions || 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardDescription className="text-sm font-medium">Credits Consumed</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-primary">
              {(stats?.total_ai_credits_consumed || 0).toLocaleString()}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* User Directory */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <CardTitle className="text-base">Registered Users & Organizations</CardTitle>
              <CardDescription>Manage permissions and view organizational hierarchy</CardDescription>
            </div>
            <div className="relative w-64">
              <MagnifyingGlass className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={searchUser}
                onChange={(e) => setSearchUser(e.target.value)}
                placeholder="Search user or email..."
                className="pl-9"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Organization</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Registered</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredUsers.map((u) => (
                <TableRow key={u.id}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Avatar className="h-8 w-8">
                        <AvatarFallback className="text-xs">
                          {u.full_name
                            ?.split(' ')
                            .map((n) => n[0])
                            .join('')
                            .slice(0, 2)
                            .toUpperCase() || '??'}
                        </AvatarFallback>
                      </Avatar>
                      <div>
                        <div className="font-semibold text-foreground">{u.full_name || 'Architect'}</div>
                        <div className="text-xs text-muted-foreground">{u.email}</div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{u.org_name || 'Enterprise'}</TableCell>
                  <TableCell>
                    <Badge variant={u.role === 'admin' ? 'default' : 'secondary'}>
                      {u.role}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Audit Log Trail */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Platform Mutation & Security Audit Trail</CardTitle>
            </div>
            <span className="text-xs text-muted-foreground font-mono">Retention: 365 Days</span>
          </div>
          <CardDescription>Immutable audit logging for compliance and governance</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Timestamp</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Credit Impact</TableHead>
                <TableHead className="text-right">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {auditLogs.map((log) => (
                <TableRow key={log.id}>
                  <TableCell className="text-xs text-muted-foreground font-mono">
                    {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '-'}
                  </TableCell>
                  <TableCell className="font-semibold text-primary font-mono text-xs">{log.action}</TableCell>
                  <TableCell className="text-muted-foreground text-xs">{log.description}</TableCell>
                  <TableCell>
                    <span className={log.amount < 0 ? 'text-red-500' : 'text-green-500'}>
                      {log.amount} pts
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge variant="outline" className="border-green-500/30 text-green-500">
                      {log.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
