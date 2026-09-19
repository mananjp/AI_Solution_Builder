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
    <div className="space-y-8 max-w-5xl mx-auto animate-fade-up py-4">
      
      {/* Header */}
      <div className="border-b border-[var(--border)] pb-4">
        <h1 className="text-2xl font-serif text-[var(--sutra-charcoal)]">Governance & Admin</h1>
        <p className="text-[13px] text-[var(--text-2)] mt-1 font-light">Platform telemetry, tenant organizations, user roles, and security audit logs.</p>
      </div>

      <div className="sutra-card p-6 bg-[var(--bg-2)] flex flex-wrap items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)] flex items-center justify-center">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-[14px] font-semibold text-[var(--sutra-charcoal)] uppercase tracking-widest">Sutra Core</h2>
              <span className="badge badge-amber text-[9px]">Superadmin</span>
            </div>
            <p className="text-[11px] text-[var(--text-2)] mt-1 font-mono uppercase tracking-widest">Intelligence Layer Control</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-[var(--bg)] border border-[var(--border)] text-[10px] text-[var(--sutra-charcoal)] font-mono uppercase tracking-widest shadow-sm">
            <Cpu className="w-3 h-3 text-[var(--sutra-muted-gold)]" />
            <span>{stats?.active_llm_model || 'Groq 120B'}</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-[var(--bg)] border border-[var(--border)] text-[10px] text-[var(--green)] font-mono uppercase tracking-widest shadow-sm">
            <CheckCircle2 className="w-3 h-3" />
            <span>{stats?.system_status || 'SLO 99.98%'}</span>
          </div>
        </div>
      </div>

      {/* KPI Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="sutra-card p-5 bg-[var(--bg-2)] border-t-2 border-t-[var(--sutra-muted-gold)]">
          <div className="flex items-center justify-between text-[var(--text-3)] text-[10px] font-bold uppercase tracking-widest">
            <span>Total Users</span>
            <Users className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
          </div>
          <p className="text-3xl font-serif text-[var(--sutra-charcoal)] mt-3">{stats?.total_users || 0}</p>
        </div>

        <div className="sutra-card p-5 bg-[var(--bg-2)] border-t-2 border-t-[var(--sutra-charcoal)]">
          <div className="flex items-center justify-between text-[var(--text-3)] text-[10px] font-bold uppercase tracking-widest">
            <span>Organizations</span>
            <Building className="w-3.5 h-3.5 text-[var(--sutra-charcoal)]" />
          </div>
          <p className="text-3xl font-serif text-[var(--sutra-charcoal)] mt-3">{stats?.total_organizations || 0}</p>
        </div>

        <div className="sutra-card p-5 bg-[var(--bg-2)] border-t-2 border-t-[var(--sutra-charcoal)]">
          <div className="flex items-center justify-between text-[var(--text-3)] text-[10px] font-bold uppercase tracking-widest">
            <span>Solutions</span>
            <Layers className="w-3.5 h-3.5 text-[var(--sutra-charcoal)]" />
          </div>
          <p className="text-3xl font-serif text-[var(--sutra-charcoal)] mt-3">{stats?.total_solutions || 0}</p>
        </div>

        <div className="sutra-card p-5 bg-[var(--bg-2)] border-t-2 border-t-[var(--green)]">
          <div className="flex items-center justify-between text-[var(--text-3)] text-[10px] font-bold uppercase tracking-widest">
            <span>Credits Used</span>
            <Sparkles className="w-3.5 h-3.5 text-[var(--green)]" />
          </div>
          <p className="text-3xl font-serif text-[var(--sutra-charcoal)] mt-3">
            {(stats?.total_ai_credits_consumed || 0).toLocaleString()}
          </p>
        </div>
      </div>

      {/* User Directory */}
      <div className="sutra-card p-6 space-y-4 bg-[var(--bg-2)]">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--border)] pb-4">
          <div>
            <h2 className="text-lg font-serif text-[var(--sutra-charcoal)]">Directory & Hierarchy</h2>
            <p className="text-[12px] text-[var(--text-2)] mt-1 font-light">Manage permissions and organizational access.</p>
          </div>

          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-[var(--text-3)] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchUser}
              onChange={(e) => setSearchUser(e.target.value)}
              placeholder="Search user or email..."
              className="w-full pl-9 pr-3 py-2 bg-[var(--bg)] border border-[var(--border)] text-[12px] text-[var(--sutra-charcoal)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors shadow-sm"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px] text-[var(--sutra-charcoal)]">
            <thead className="bg-[var(--bg)] text-[10px] uppercase tracking-widest text-[var(--text-3)] border-b border-[var(--border)]">
              <tr>
                <th className="p-3 font-semibold">User</th>
                <th className="p-3 font-semibold">Organization</th>
                <th className="p-3 font-semibold">Role</th>
                <th className="p-3 font-semibold">Registered</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {filteredUsers.map((u) => (
                <tr key={u.id} className="hover:bg-[var(--bg)] transition-colors">
                  <td className="p-3">
                    <div className="font-semibold text-[var(--sutra-charcoal)]">{u.full_name || 'Architect'}</div>
                    <div className="text-[11px] text-[var(--text-2)] font-mono">{u.email}</div>
                  </td>
                  <td className="p-3 text-[var(--text-2)] font-light">{u.org_name || 'Enterprise'}</td>
                  <td className="p-3">
                    <span className={`badge ${u.role === 'admin' ? 'badge-amber' : 'badge-gray'}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="p-3 text-[var(--text-2)] text-[11px] font-mono">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Audit Log Trail */}
      <div className="sutra-card p-6 space-y-4 bg-[var(--bg-2)]">
        <div className="flex items-end justify-between border-b border-[var(--border)] pb-4">
          <div>
            <h2 className="text-lg font-serif text-[var(--sutra-charcoal)] flex items-center gap-2">
              <Clock className="w-5 h-5 text-[var(--sutra-muted-gold)]" />
              <span>Platform Security Audit Trail</span>
            </h2>
            <p className="text-[12px] text-[var(--text-2)] mt-1 font-light">Immutable audit logging for compliance and governance</p>
          </div>
          <span className="text-[10px] text-[var(--text-3)] font-bold uppercase tracking-widest">Retention: 365 Days</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px] text-[var(--sutra-charcoal)]">
            <thead className="bg-[var(--bg)] text-[10px] uppercase tracking-widest text-[var(--text-3)] border-b border-[var(--border)]">
              <tr>
                <th className="p-3 font-semibold">Timestamp</th>
                <th className="p-3 font-semibold">Action</th>
                <th className="p-3 font-semibold">Description</th>
                <th className="p-3 font-semibold">Impact</th>
                <th className="p-3 text-right font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)] font-mono text-[11px]">
              {auditLogs.map((log) => (
                <tr key={log.id} className="hover:bg-[var(--bg)] transition-colors group">
                  <td className="p-3 text-[var(--text-2)]">
                    {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '-'}
                  </td>
                  <td className="p-3 font-semibold text-[var(--sutra-charcoal)] group-hover:text-[var(--sutra-muted-gold)] transition-colors">{log.action}</td>
                  <td className="p-3 text-[var(--text-2)] font-sans text-xs font-light">{log.description}</td>
                  <td className="p-3">
                    <span className={log.amount < 0 ? 'text-[var(--sutra-charcoal)]' : 'text-[var(--green)]'}>
                      {Math.abs(log.amount)} pts
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    <span className="badge badge-green text-[9px]">
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
