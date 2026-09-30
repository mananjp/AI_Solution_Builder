'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import {
  ShieldCheck,
  Users,
  Building,
  Layers,
  Clock,
  CheckCircle2,
  Search,
  Cpu,
  Sparkles,
  Shield,
  ShieldAlert,
  Activity,
  Upload,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import {
  adminApi,
  securityApi,
  SecurityConfig,
  SecurityStats,
  SecurityScanItem,
} from '@/lib/api';
import { AdminStats, AdminUser, AuditLogEntry } from '@/types';
import { errorMessage } from '@/lib/errors';
import { useAuthSession } from '@/components/auth/AuthProvider';
import { RelativeTime } from '@/components/lab/relative-time';
import { Pagination } from '@/components/lab/pagination';

import { Button } from '@/components/ui/button';

import { Badge } from '@/components/ui/badge';

export default function AdminGovernancePage() {
  const { user, isLoading: sessionLoading } = useAuthSession();

  // The role check is defence in depth, not the security boundary. The API
  // enforces the same roles server-side and returns 403 regardless of what this
  // renders, so bypassing the client guard buys nothing. Without it a
  // non-administrator who typed /admin landed on a page where every request
  // failed, which read as a broken app rather than a permission denial.
  const isElevated = user?.role === 'admin' || user?.role === 'superadmin' || user?.role === 'owner';

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [searchUser, setSearchUser] = useState('');
  const [userPage, setUserPage] = useState(1);

  // Threat scanning
  const [securityStats, setSecurityStats] = useState<SecurityStats | null>(null);
  const [securityConfig, setSecurityConfig] = useState<SecurityConfig | null>(null);
  const [securityScans, setSecurityScans] = useState<SecurityScanItem[]>([]);
  const [testFileLoading, setTestFileLoading] = useState(false);
  const [testScanResult, setTestScanResult] = useState<{
    error?: string;
    filename?: string;
    verdict?: string;
    findings?: Array<{ source?: string; verdict?: string; reason?: string }>;
    sha256?: string;
    duration_ms?: number;
    from_cache?: boolean;
  } | null>(null);

  const testFileInputRef = useRef<HTMLInputElement>(null);

  // Fetches the console data. Kept out of the effect body so the permission
  // guard below can gate when it runs, and so the cancellation flag is local to
  // one call rather than shared across re-runs.
  const loadAdminData = useCallback(async (isCancelled: () => boolean) => {
    // The previous error is cleared by whoever triggers a retry, not here. This
    // function is reached from an effect, and clearing state synchronously in
    // that path is a cascading render for no benefit.
    try {
      const [st, uList, logs, secStats, secConfig, secScansList] = await Promise.all([
        adminApi.getStats(),
        adminApi.getUsers(),
        adminApi.getAuditLogs(),
        securityApi.getStats().catch(() => null),
        securityApi.getConfig().catch(() => null),
        securityApi.getScans({ limit: 10 }).catch(() => null),
      ]);
      if (isCancelled()) return;
      setStats(st);
      setUsers(uList);
      setAuditLogs(logs);
      if (secStats) setSecurityStats(secStats);
      if (secConfig) setSecurityConfig(secConfig);
      if (secScansList?.items) setSecurityScans(secScansList.items);
    } catch (err) {
      if (isCancelled()) return;
      // Previously this synthesised a full admin dashboard on failure:
      // 14 users, 28 solutions, "Healthy (99.98% SLO)" and 68,400 credits
      // consumed. That is worse than an error screen — during a real outage an
      // operator would read a fabricated healthy system as a healthy system.
      // Clear the data and report the failure instead.
      setStats(null);
      setUsers([]);
      setAuditLogs([]);
      setSecurityScans([]);
      setLoadError(errorMessage(err));
    }
  }, []);

  // All hooks must run before any early return, so this sits above the
  // permission guards below.
  // Nothing may fetch until the role is known: firing on the first render would
  // send a burst of 403s before the session resolves. Declared after
  // `loadAdminData` because it is named in this dependency array.
  useEffect(() => {
    if (sessionLoading || !isElevated) return;
    let cancelled = false;
    // Fetching on mount is what an effect is for; the rule flags the setState
    // calls inside the loader, but they all follow the awaited request, so no
    // state is set synchronously in this render pass.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadAdminData(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [sessionLoading, isElevated, reloadToken, loadAdminData]);

  if (sessionLoading) {
    return (
      <div className="flex justify-center py-20" role="status" aria-label="Checking permissions">
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      </div>
    );
  }

  if (!isElevated) {
    return (
      <div className="mx-auto max-w-lg py-20 text-center">
        <ShieldAlert className="mx-auto mb-4 size-8 text-[var(--amber)]" aria-hidden />
        <h1 className="font-serif text-xl">Administrator access required</h1>
        <p className="mt-2 text-[13px] font-light leading-relaxed text-muted">
          This console is limited to administrators. If you believe you should have access,
          ask an organisation owner to change your role.
        </p>
        <Button asChild className="mt-6">
          <Link href="/dashboard">Back to dashboard</Link>
        </Button>
      </div>
    );
  }

  // Threat Scanning State
  const filteredUsers = users.filter(u =>
    u.email.toLowerCase().includes(searchUser.toLowerCase()) ||
    (u.full_name && u.full_name.toLowerCase().includes(searchUser.toLowerCase()))
  );

  // A tenant can have far more users than fit on one screen, so the directory
  // pages rather than rendering every row.
  const USERS_PER_PAGE = 10;
  const userPages = Math.max(1, Math.ceil(filteredUsers.length / USERS_PER_PAGE));
  const page = Math.min(userPage, userPages);
  const pagedUsers = filteredUsers.slice((page - 1) * USERS_PER_PAGE, page * USERS_PER_PAGE);

  return (
    <div className="space-y-8 max-w-5xl mx-auto animate-fade-up py-4">
      
      {/* Header */}
      <div className="border-b border-[var(--border)] pb-4">
        <h1 className="text-2xl font-serif text-[var(--sutra-ink)]">Governance & Admin</h1>
        <p className="text-[13px] text-[var(--text-2)] mt-1 font-light">Platform telemetry, tenant organizations, user roles, and security audit logs.</p>
      </div>

      <div className="sutra-card p-6 bg-[var(--bg-2)] flex flex-wrap items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-[var(--sutra-ink)] text-[var(--sutra-canvas)] flex items-center justify-center">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-[14px] font-semibold text-[var(--sutra-ink)] uppercase tracking-widest">Sutra Core</h2>
              <Badge variant="warning" className="text-[9px]">Superadmin</Badge>
            </div>
            <p className="text-[11px] text-[var(--text-2)] mt-1 font-mono uppercase tracking-widest">Intelligence Layer Control</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-[var(--bg)] border border-[var(--border)] text-[10px] text-[var(--sutra-ink)] font-mono uppercase tracking-widest shadow-sm">
            <Cpu className="w-3 h-3 text-[var(--sutra-strong)]" />
            {/* No placeholder here: a hardcoded model name reads as a live
                reading when the request actually failed. */}
            <span>{stats?.active_llm_model ?? (loadError ? 'unavailable' : '—')}</span>
          </div>
          <div
            className={`flex items-center gap-2 px-3 py-1.5 bg-[var(--bg)] border text-[10px] font-mono uppercase tracking-widest shadow-sm ${
              loadError
                ? 'border-[var(--red-edge)] text-[var(--red)]'
                : 'border-[var(--border)] text-[var(--green)]'
            }`}
          >
            {loadError ? (
              <AlertTriangle className="w-3 h-3" />
            ) : (
              <CheckCircle2 className="w-3 h-3" />
            )}
            {/* Previously fell back to a literal "SLO 99.98%", which asserted a
                healthy status bar during a total backend outage. */}
            <span>{stats?.system_status ?? (loadError ? 'unreachable' : '—')}</span>
          </div>
        </div>
      </div>

      {loadError && (
        <div
          role="alert"
          className="rounded border border-[var(--red-edge)] bg-[var(--red-wash)] px-4 py-3 text-sm text-[var(--red)]"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">Could not load admin data</p>
              <p className="mt-0.5 font-mono text-xs opacity-90">{loadError}</p>
              <p className="mt-1 text-xs opacity-80">
                The figures, users and audit log below are empty because nothing could be
                read from the server. They are not zero-valued measurements.
              </p>
            </div>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="mt-3"
            onClick={() => {
              setLoadError(null);
              setReloadToken((n) => n + 1);
            }}
          >
            Retry
          </Button>
        </div>
      )}

      {/* KPI Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="sutra-card p-5 bg-[var(--bg-2)] border-t-2 border-t-[var(--sutra-strong)]">
          <div className="flex items-center justify-between text-[var(--text-3)] text-[10px] font-bold uppercase tracking-widest">
            <span>Total Users</span>
            <Users className="w-3.5 h-3.5 text-[var(--sutra-strong)]" />
          </div>
          <p className="text-3xl font-serif text-[var(--sutra-ink)] mt-3">{stats?.total_users || 0}</p>
        </div>

        <div className="sutra-card p-5 bg-[var(--bg-2)] border-t-2 border-t-[var(--sutra-ink)]">
          <div className="flex items-center justify-between text-[var(--text-3)] text-[10px] font-bold uppercase tracking-widest">
            <span>Organizations</span>
            <Building className="w-3.5 h-3.5 text-[var(--sutra-ink)]" />
          </div>
          <p className="text-3xl font-serif text-[var(--sutra-ink)] mt-3">{stats?.total_organizations || 0}</p>
        </div>

        <div className="sutra-card p-5 bg-[var(--bg-2)] border-t-2 border-t-[var(--sutra-ink)]">
          <div className="flex items-center justify-between text-[var(--text-3)] text-[10px] font-bold uppercase tracking-widest">
            <span>Solutions</span>
            <Layers className="w-3.5 h-3.5 text-[var(--sutra-ink)]" />
          </div>
          <p className="text-3xl font-serif text-[var(--sutra-ink)] mt-3">{stats?.total_solutions || 0}</p>
        </div>

        <div className="sutra-card p-5 bg-[var(--bg-2)] border-t-2 border-t-[var(--green)]">
          <div className="flex items-center justify-between text-[var(--text-3)] text-[10px] font-bold uppercase tracking-widest">
            <span>Credits Used</span>
            <Sparkles className="w-3.5 h-3.5 text-[var(--green)]" />
          </div>
          <p className="text-3xl font-serif text-[var(--sutra-ink)] mt-3">
            {(stats?.total_ai_credits_consumed || 0).toLocaleString()}
          </p>
        </div>
      </div>

      {/* User Directory */}
      <div className="sutra-card p-6 space-y-4 bg-[var(--bg-2)]">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--border)] pb-4">
          <div>
            <h2 className="text-lg font-serif text-[var(--sutra-ink)]">Directory & Hierarchy</h2>
            <p className="text-[12px] text-[var(--text-2)] mt-1 font-light">Manage permissions and organizational access.</p>
          </div>

          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-[var(--text-3)] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchUser}
              onChange={(e) => {
                setSearchUser(e.target.value);
                // Return to the first page as the query changes. This used to be
                // an effect, which meant the directory briefly rendered page 4 of
                // the previous results before correcting itself — and a search
                // that matched nothing on page 4 looked like it found nothing.
                setUserPage(1);
              }}
              aria-label="Search users by name or email"
              placeholder="Search user or email..."
              className="w-full pl-9 pr-3 py-2 bg-[var(--bg)] border border-[var(--border)] text-[12px] text-[var(--sutra-ink)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-strong)] transition-colors shadow-sm"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px] text-[var(--sutra-ink)]">
            <thead className="bg-[var(--bg)] text-[10px] uppercase tracking-widest text-[var(--text-3)] border-b border-[var(--border)]">
              <tr>
                <th className="p-3 font-semibold">User</th>
                <th className="p-3 font-semibold">Organization</th>
                <th className="p-3 font-semibold">Role</th>
                <th className="p-3 font-semibold">Registered</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {pagedUsers.map((u) => (
                <tr key={u.id} className="hover:bg-[var(--bg)] transition-colors">
                  <td className="p-3">
                    <div className="font-semibold text-[var(--sutra-ink)]">{u.full_name || 'Architect'}</div>
                    <div className="text-[11px] text-[var(--text-2)] font-mono">{u.email}</div>
                  </td>
                  <td className="p-3 text-[var(--text-2)] font-light">{u.org_name || 'Enterprise'}</td>
                  <td className="p-3">
        <Badge variant={u.role === 'admin' ? 'warning' : 'neutral'}>
                        {u.role}
                      </Badge>

                  </td>
                  <td className="p-3 text-[var(--text-2)] text-[11px] font-mono">
                    <RelativeTime date={u.created_at} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {userPages > 1 && (
          <div className="flex justify-end border-t border-[var(--border)] pt-3">
            <Pagination
              page={page}
              total={userPages}
              onPageChange={setUserPage}
              label="User directory pages"
            />
          </div>
        )}
      </div>

      {/* Audit Log Trail */}
      <div className="sutra-card p-6 space-y-4 bg-[var(--bg-2)]">
        <div className="flex items-end justify-between border-b border-[var(--border)] pb-4">
          <div>
            <h2 className="text-lg font-serif text-[var(--sutra-ink)] flex items-center gap-2">
              <Clock className="w-5 h-5 text-[var(--sutra-strong)]" />
              <span>Platform Security Audit Trail</span>
            </h2>
            <p className="text-[12px] text-[var(--text-2)] mt-1 font-light">Immutable audit logging for compliance and governance</p>
          </div>
          <span className="text-[10px] text-[var(--text-3)] font-bold uppercase tracking-widest">Retention: 365 Days</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px] text-[var(--sutra-ink)]">
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
                    <RelativeTime date={log.timestamp} />
                  </td>
                  <td className="p-3 font-semibold text-[var(--sutra-ink)] group-hover:text-[var(--sutra-strong)] transition-colors">{log.action}</td>
                  <td className="p-3 text-[var(--text-2)] font-sans text-xs font-light">{log.description}</td>
                  <td className="p-3">
                    <span className={log.amount < 0 ? 'text-[var(--sutra-ink)]' : 'text-[var(--green)]'}>
                      {Math.abs(log.amount)} pts
                    </span>
                  </td>
                  <td className="p-3 text-right">
                    <Badge variant="success" className="text-[9px]">
                      {log.status}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Threat Scanning & VirusTotal Guardrails (SEC-SCAN-001) ── */}
      <div className="sutra-card p-6 space-y-6 bg-[var(--bg-2)] border-t-2 border-t-[var(--sutra-strong)]">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--border)] pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-[var(--sutra-strong)]" />
              <h2 className="text-lg font-serif text-[var(--sutra-ink)]">Threat Scanning & Asset Security</h2>
              <Badge variant="warning" className="text-[9px]">SEC-SCAN-001</Badge>
            </div>
            <p className="text-[12px] text-[var(--text-2)] mt-1 font-light">
              Multi-layer defense protecting ingress (uploads, URLs, repositories) and egress (code exports, packages).
            </p>
          </div>
          <div className="flex items-center gap-2 font-mono text-[10px] text-[var(--text-3)] uppercase tracking-wider">
            <span>Threshold:</span>
            <span className="px-2 py-0.5 bg-[var(--bg)] border border-[var(--border)] text-[var(--sutra-ink)] font-bold rounded">
              {securityConfig?.block_threshold || 'suspicious'}
            </span>
          </div>
        </div>

        {/* 3 Scanning Layers Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Layer 0 */}
          <div className="p-4 bg-[var(--bg)] border border-[var(--border)] rounded-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--sutra-ink)]">
                Layer 0: Local Rules
              </span>
              <span className="flex items-center gap-1 text-[10px] font-mono font-semibold text-[var(--green)]">
                <CheckCircle2 className="w-3 h-3" />
                Active
              </span>
            </div>
            <p className="text-[11px] text-[var(--text-2)] leading-relaxed">
              Sub-millisecond offline inspection. Validates binary magic (PE/ELF/Mach-O), detects polyglots, OOXML macros, and enforces archive safety.
            </p>
            <div className="text-[10px] font-mono text-[var(--text-3)] pt-1 border-t border-[var(--border)] flex justify-between">
              <span>Latency: &lt; 1ms</span>
              <span>Always On</span>
            </div>
          </div>

          {/* Layer 1 */}
          <div className="p-4 bg-[var(--bg)] border border-[var(--border)] rounded-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--sutra-ink)]">
                Layer 1: ClamAV Daemon
              </span>
              <span
                className={`flex items-center gap-1 text-[10px] font-mono font-semibold ${
                  securityConfig?.layers?.layer_1_clamav?.live ? 'text-[var(--green)]' : 'text-[var(--text-3)]'
                }`}
              >
                {securityConfig?.layers?.layer_1_clamav?.live ? (
                  <>
                    <CheckCircle2 className="w-3 h-3" />
                    Online
                  </>
                ) : (
                  <>
                    <Activity className="w-3 h-3" />
                    {securityConfig?.layers?.layer_1_clamav?.configured ? 'Offline' : 'Optional / Standby'}
                  </>
                )}
              </span>
            </div>
            <p className="text-[11px] text-[var(--text-2)] leading-relaxed">
              Raw TCP zINSTREAM protocol. Unlimited streaming file scan without external Python dependencies.
            </p>
            <div className="text-[10px] font-mono text-[var(--text-3)] pt-1 border-t border-[var(--border)] flex justify-between">
              <span>Port: {securityConfig?.layers?.layer_1_clamav?.port || 3310}</span>
              <span>Host: {securityConfig?.layers?.layer_1_clamav?.host || 'clamav'}</span>
            </div>
          </div>

          {/* Layer 2 */}
          <div className="p-4 bg-[var(--bg)] border border-[var(--border)] rounded-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--sutra-ink)]">
                Layer 2: VirusTotal v3
              </span>
              <span
                className={`flex items-center gap-1 text-[10px] font-mono font-semibold ${
                  securityConfig?.layers?.layer_2_virustotal?.live ? 'text-[var(--green)]' : 'text-[var(--text-3)]'
                }`}
              >
                {securityConfig?.layers?.layer_2_virustotal?.live ? (
                  <>
                    <CheckCircle2 className="w-3 h-3" />
                    Live (Token Bucket)
                  </>
                ) : (
                  <>
                    <ShieldAlert className="w-3 h-3 text-[var(--sutra-strong)]" />
                    Gated (Non-commercial ToS)
                  </>
                )}
              </span>
            </div>
            <p className="text-[11px] text-[var(--text-2)] leading-relaxed">
              70+ vendor cloud intelligence. Gated behind VIRUSTOTAL_ACK_TOS. Rate-limited to 4 RPM and 500 Daily with Redis caching.
            </p>
            <div className="text-[10px] font-mono text-[var(--text-3)] pt-1 border-t border-[var(--border)] flex justify-between">
              <span>Quota: 4 RPM / 500 Day</span>
              <span>Key: {securityConfig?.layers?.layer_2_virustotal?.api_key_configured ? 'Configured' : 'Unset'}</span>
            </div>
          </div>
        </div>

        {/* Security Telemetry Counters */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
          <div className="p-3 bg-[var(--bg)] border border-[var(--border)] rounded-sm">
            <span className="text-[10px] uppercase font-bold text-[var(--text-3)] block mb-1">Total Scans</span>
            <span className="text-xl font-serif text-[var(--sutra-ink)] font-semibold">
              {(securityStats?.total_scans || 0).toLocaleString()}
            </span>
          </div>
          <div className="p-3 bg-[var(--bg)] border border-[var(--border)] rounded-sm">
            <span className="text-[10px] uppercase font-bold text-[var(--text-3)] block mb-1">Cache Hit Rate</span>
            <span className="text-xl font-serif text-[var(--green)] font-semibold">
              {((securityStats?.cache_hit_rate || 0) * 100).toFixed(1)}%
            </span>
          </div>
          <div className="p-3 bg-[var(--bg)] border border-[var(--border)] rounded-sm">
            <span className="text-[10px] uppercase font-bold text-[var(--text-3)] block mb-1">Bytes Scanned</span>
            <span className="text-xl font-serif text-[var(--sutra-ink)] font-semibold">
              {((securityStats?.total_bytes_scanned || 0) / (1024 * 1024)).toFixed(1)} MB
            </span>
          </div>
          <div className="p-3 bg-[var(--bg)] border border-[var(--border)] rounded-sm">
            <span className="text-[10px] uppercase font-bold text-[var(--text-3)] block mb-1">Fail Unavailable Mode</span>
            <span className="text-sm font-mono uppercase text-[var(--sutra-strong)] font-bold">
              {securityConfig?.fail_unavailable_mode || 'allow'}
            </span>
          </div>
        </div>

        {/* Interactive On-Demand File Threat Scanner */}
        <div className="p-4 bg-[var(--bg)] border border-dashed border-[var(--border)] rounded-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--sutra-ink)] flex items-center gap-1.5">
              <Upload className="w-3.5 h-3.5 text-[var(--sutra-strong)]" />
              Admin On-Demand File Threat Inspector
            </span>
            <span className="text-[10px] text-[var(--text-3)] font-mono">Test scanner verdicts without mutating data</span>
          </div>

          <input
            ref={testFileInputRef}
            type="file"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              setTestFileLoading(true);
              setTestScanResult(null);
              try {
                const res = await securityApi.scanFile(file);
                setTestScanResult(res);
              } catch (err: unknown) {
                const message = err instanceof Error ? err.message : 'Scan error';
                setTestScanResult({ error: message });
              } finally {
                setTestFileLoading(false);
              }
            }}
          />

          <div className="flex items-center gap-3">
            <Button type="button" variant="secondary" size="sm"
              onClick={() => testFileInputRef.current?.click()}
              disabled={testFileLoading}
             
             className="text-xs flex items-center gap-2">
              {testFileLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--sutra-strong)]" />
                  Running Multi-Layer Scan...
                </>
              ) : (
                <>
                  <ShieldCheck className="w-3.5 h-3.5 text-[var(--green)]" />
                  Upload & Inspect File
                </>
              )}
            </Button>
            <span className="text-[11px] text-[var(--text-3)]">
              Upload any document, binary, or archive (e.g. test EICAR or polyglot files) to view instant verdict.
            </span>
          </div>

          {testScanResult && (
            <div className="p-3 bg-[var(--bg-2)] border border-[var(--border)] rounded text-xs space-y-2 mt-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[var(--sutra-ink)]">
                  Target: {testScanResult.filename || 'Uploaded File'}
                </span>
                <Badge
                  variant={
                    testScanResult.verdict === 'clean'
                      ? 'success'
                      : testScanResult.verdict === 'malicious'
                        ? 'destructive'
                        : 'warning'
                  }
                  className="font-mono text-[10px]"
                >
                  Verdict: {testScanResult.verdict?.toUpperCase() || 'UNKNOWN'}
                </Badge>
              </div>
              {Boolean(testScanResult.findings && testScanResult.findings.length > 0) && testScanResult.findings && (
                <div className="space-y-1 pt-1 border-t border-[var(--border)]">
                  <span className="text-[10px] uppercase font-bold text-[var(--text-3)]">Findings:</span>
                  {testScanResult.findings.map((f, idx: number) => (
                    <div key={idx} className="font-mono text-[11px] text-[var(--red)] flex items-center gap-2">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                      <span>[{f.source}] {f.reason} ({f.verdict})</span>
                    </div>
                  ))}
                </div>
              )}
              {testScanResult.sha256 && (
                <div className="text-[10px] font-mono text-[var(--text-3)] truncate">
                  SHA-256: {testScanResult.sha256} · Latency: {testScanResult.duration_ms}ms · Cached: {String(testScanResult.from_cache)}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Recent Threat Scan Records Table */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--sutra-ink)]">
              Recent Scan Activity Log
            </span>
            <span className="text-[10px] text-[var(--text-3)] font-mono">Last 10 events</span>
          </div>

          <div className="overflow-x-auto border border-[var(--border)] rounded-sm">
            <table className="w-full text-left text-[11px]">
              <thead className="bg-[var(--bg)] text-[9px] uppercase tracking-widest text-[var(--text-3)] border-b border-[var(--border)]">
                <tr>
                  <th className="p-2.5 font-semibold">Target / Source</th>
                  <th className="p-2.5 font-semibold">Verdict</th>
                  <th className="p-2.5 font-semibold">Findings / Reasons</th>
                  <th className="p-2.5 font-semibold">Latency</th>
                  <th className="p-2.5 text-right font-semibold">Source Type</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)] font-mono text-[10px]">
                {securityScans.length > 0 ? (
                  securityScans.map((scan) => (
                    <tr key={scan.id} className="hover:bg-[var(--bg)] transition-colors">
                      <td className="p-2.5 text-[var(--sutra-ink)] font-semibold">
                        {scan.source}
                        {scan.from_cache && (
                          <span className="ml-1.5 text-[9px] text-[var(--sutra-strong)]">[cached]</span>
                        )}
                      </td>
                      <td className="p-2.5">
                        <Badge
                          variant={
                            scan.verdict === 'clean'
                              ? 'success'
                              : scan.verdict === 'malicious'
                                ? 'destructive'
                                : scan.verdict === 'suspicious'
                                  ? 'warning'
                                  : 'neutral'
                          }
                          className="text-[9px]"
                        >
                          {scan.verdict}
                        </Badge>
                      </td>
                      <td className="p-2.5 text-[var(--text-2)] font-sans">
                        {scan.findings && scan.findings.length > 0
                          ? scan.findings.map((f) => f.reason).join(', ')
                          : 'None (Clean)'}
                      </td>
                      <td className="p-2.5 text-[var(--text-3)]">{scan.duration_ms}ms</td>
                      <td className="p-2.5 text-right text-[var(--text-3)] uppercase">{scan.target}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="p-4 text-center text-[var(--text-3)] font-sans">
                      No security violations detected. Threat scanning active across all ingestion hooks.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
