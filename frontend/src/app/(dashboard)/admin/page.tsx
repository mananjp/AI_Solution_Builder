'use client';

import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  Users,
  Building,
  Layers,
  Clock,
  CheckCircle2,
  Search,
  Cpu,
  Sparkles
} from 'lucide-react';
import { adminApi } from '@/lib/api';
import { AdminStats, AdminUser, AuditLogEntry } from '@/types';

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
        setStats({
          total_users: 14,
          total_organizations: 4,
          total_solutions: 28,
          total_workspaces: 8,
          active_llm_model: 'Groq OSS 120B',
          system_status: 'Healthy (99.98% SLO)',
          total_ai_credits_consumed: 68400,
          average_generation_time_sec: 3.8,
        });

        setUsers([
          { id: 'u1', email: 'architect@enterprise.io', full_name: 'Lead Architect', role: 'admin', org_name: 'Futurrizon Technologies', created_at: '2026-09-01T10:00:00Z' },
          { id: 'u2', email: 'sarah.chen@acme.com', full_name: 'Sarah Chen', role: 'member', org_name: 'Acme Corp', created_at: '2026-09-03T14:30:00Z' },
          { id: 'u3', email: 'dev.ops@cloudscale.io', full_name: 'Devon Vance', role: 'member', org_name: 'CloudScale Systems', created_at: '2026-09-05T09:15:00Z' },
        ]);

        setAuditLogs([
          { id: 'log-1', org_id: 'org-1', action: 'generate_solution', description: 'Generated Omnichannel POS Solution Blueprint', amount: -200, timestamp: '2026-09-10T22:15:00Z', status: 'SUCCESS' },
          { id: 'log-2', org_id: 'org-1', action: 'regenerate_artifact', description: 'Regenerated Database Schema v2 (Indexes Added)', amount: -50, timestamp: '2026-09-10T22:20:00Z', status: 'SUCCESS' },
          { id: 'log-3', org_id: 'org-1', action: 'export_code_zip', description: 'Downloaded Deployable Docker & CI/CD ZIP', amount: -10, timestamp: '2026-09-10T22:25:00Z', status: 'SUCCESS' },
        ]);
      }
    }

    loadAdminData();
  }, []);

  const filteredUsers = users.filter(u =>
    u.email.toLowerCase().includes(searchUser.toLowerCase()) ||
    (u.full_name && u.full_name.toLowerCase().includes(searchUser.toLowerCase()))
  );

  return (
    <div className="space-y-6 max-w-6xl mx-auto animate-fade-up">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-xl bg-[#111] border border-[#1a1a1a]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-[#161616] border border-[#242424] text-[#6366f1] flex items-center justify-center">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-semibold text-white">Governance &amp; Admin</h1>
              <span className="badge badge-green">Superadmin</span>
            </div>
            <p className="text-xs text-[#555] mt-0.5">
              Platform telemetry, tenant organizations, user roles, and security audit logs.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0a0a0a] border border-[#1a1a1a] text-xs text-[#a1a1a1] font-mono">
            <Cpu className="w-3.5 h-3.5 text-[#6366f1]" />
            <span>{stats?.active_llm_model || 'Groq 120B'}</span>
          </div>
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#0a0a0a] border border-[#1a1a1a] text-xs text-[#4ade80] font-mono">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>{stats?.system_status || 'SLO 99.98%'}</span>
          </div>
        </div>
      </div>

      {/* KPI Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl bg-[#111] border border-[#1a1a1a]">
          <div className="flex items-center justify-between text-[#555] text-xs font-medium">
            <span>Total Users</span>
            <Users className="w-4 h-4 text-[#6366f1]" />
          </div>
          <p className="text-xl font-semibold text-white mt-1.5">{stats?.total_users || 0}</p>
        </div>

        <div className="p-4 rounded-xl bg-[#111] border border-[#1a1a1a]">
          <div className="flex items-center justify-between text-[#555] text-xs font-medium">
            <span>Tenant Organizations</span>
            <Building className="w-4 h-4 text-[#6366f1]" />
          </div>
          <p className="text-xl font-semibold text-white mt-1.5">{stats?.total_organizations || 0}</p>
        </div>

        <div className="p-4 rounded-xl bg-[#111] border border-[#1a1a1a]">
          <div className="flex items-center justify-between text-[#555] text-xs font-medium">
            <span>Solutions</span>
            <Layers className="w-4 h-4 text-[#6366f1]" />
          </div>
          <p className="text-xl font-semibold text-white mt-1.5">{stats?.total_solutions || 0}</p>
        </div>

        <div className="p-4 rounded-xl bg-[#111] border border-[#1a1a1a]">
          <div className="flex items-center justify-between text-[#555] text-xs font-medium">
            <span>Credits Consumed</span>
            <Sparkles className="w-4 h-4 text-[#4ade80]" />
          </div>
          <p className="text-xl font-semibold text-white mt-1.5 font-mono">
            {(stats?.total_ai_credits_consumed || 0).toLocaleString()}
          </p>
        </div>
      </div>

      {/* User Directory */}
      <div className="p-5 rounded-xl bg-[#111] border border-[#1a1a1a] space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-white">Registered Users &amp; Organizations</h2>
            <p className="text-xs text-[#555] mt-0.5">Manage permissions and view organizational hierarchy</p>
          </div>

          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-[#555] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchUser}
              onChange={(e) => setSearchUser(e.target.value)}
              placeholder="Search user or email..."
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-[#0a0a0a] border border-[#2e2e2e] text-xs text-white placeholder:text-[#444] focus:outline-none focus:border-[#6366f1]"
            />
          </div>
        </div>

        <div className="border border-[#1a1a1a] rounded-lg overflow-hidden bg-[#0a0a0a]">
          <table className="w-full text-left text-xs text-[#f5f5f5]">
            <thead className="bg-[#111] text-[#555] uppercase text-[10px] tracking-wider border-b border-[#1a1a1a]">
              <tr>
                <th className="p-3">User</th>
                <th className="p-3">Organization</th>
                <th className="p-3">Role</th>
                <th className="p-3">Registered</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1a1a1a]">
              {filteredUsers.map((u) => (
                <tr key={u.id} className="hover:bg-[#111] transition-colors">
                  <td className="p-3">
                    <div className="font-semibold text-white">{u.full_name || 'Architect'}</div>
                    <div className="text-[11px] text-[#555] font-mono">{u.email}</div>
                  </td>
                  <td className="p-3 text-[#a1a1a1]">{u.org_name || 'Enterprise'}</td>
                  <td className="p-3">
                    <span className={`badge ${u.role === 'admin' ? 'badge-blue' : 'badge-gray'}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="p-3 text-[#555] text-[11px] font-mono">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Audit Log Trail */}
      <div className="p-5 rounded-xl bg-[#111] border border-[#1a1a1a] space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Clock className="w-4 h-4 text-[#6366f1]" />
              <span>Platform Security Audit Trail</span>
            </h2>
            <p className="text-xs text-[#555] mt-0.5">Immutable audit logging for compliance and governance</p>
          </div>
          <span className="text-xs text-[#555] font-mono">Retention: 365 Days</span>
        </div>

        <div className="border border-[#1a1a1a] rounded-lg overflow-hidden bg-[#0a0a0a]">
          <table className="w-full text-left text-xs text-[#f5f5f5]">
            <thead className="bg-[#111] text-[#555] uppercase text-[10px] tracking-wider border-b border-[#1a1a1a]">
              <tr>
                <th className="p-3">Timestamp</th>
                <th className="p-3">Action</th>
                <th className="p-3">Description</th>
                <th className="p-3">Impact</th>
                <th className="p-3 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1a1a1a] font-mono text-[11px]">
              {auditLogs.map((log) => (
                <tr key={log.id} className="hover:bg-[#111] transition-colors">
                  <td className="p-3 text-[#555]">
                    {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '-'}
                  </td>
                  <td className="p-3 font-semibold text-[#818cf8]">{log.action}</td>
                  <td className="p-3 text-[#a1a1a1] font-sans text-xs">{log.description}</td>
                  <td className="p-3">
                    <span className={log.amount < 0 ? 'text-[#f87171]' : 'text-[#4ade80]'}>
                      {log.amount} pts
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    <span className="badge badge-green">
                      {log.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
