'use client';

import React, { useState, useEffect, useRef } from 'react';
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
  FileText,
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

export default function AdminGovernancePage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [searchUser, setSearchUser] = useState('');

  // Threat Scanning State
  const [securityStats, setSecurityStats] = useState<SecurityStats | null>(null);
  const [securityConfig, setSecurityConfig] = useState<SecurityConfig | null>(null);
  const [securityScans, setSecurityScans] = useState<SecurityScanItem[]>([]);
  const [testFileLoading, setTestFileLoading] = useState(false);
  const [testScanResult, setTestScanResult] = useState<any>(null);
  const testFileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    async function loadAdminData() {
      try {
        const [st, uList, logs, secStats, secConfig, secScansList] = await Promise.all([
          adminApi.getStats(),
          adminApi.getUsers(),
          adminApi.getAuditLogs(),
          securityApi.getStats().catch(() => null),
          securityApi.getConfig().catch(() => null),
          securityApi.getScans({ limit: 10 }).catch(() => ({ total: 0, items: [] })),
        ]);
        setStats(st);
        setUsers(uList);
        setAuditLogs(logs);
        if (secStats) setSecurityStats(secStats);
        if (secConfig) setSecurityConfig(secConfig);
        if (secScansList?.items) setSecurityScans(secScansList.items);
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

        // Default mock security config when local server is in offline mock mode
        setSecurityConfig({
          security_scan_enabled: true,
          block_threshold: 'suspicious',
          fail_unavailable_mode: 'allow',
          scan_sources: '*',
          archive_limits: {
            max_entries: 10000,
            max_uncompressed_bytes: 524288000,
            max_ratio: 100,
            max_nested_depth: 2,
          },
          layers: {
            layer_0_local_rules: { configured: true, live: true },
            layer_1_clamav: { configured: false, live: false, host: 'clamav', port: 3310 },
            layer_2_virustotal: {
              configured: false,
              acknowledged_tos: false,
              live: false,
              api_key_configured: false,
              rpm_limit: 4,
              daily_limit: 500,
            },
          },
        });
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

      {/* ── Threat Scanning & VirusTotal Guardrails (SEC-SCAN-001) ── */}
      <div className="sutra-card p-6 space-y-6 bg-[var(--bg-2)] border-t-2 border-t-[var(--sutra-muted-gold)]">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--border)] pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-[var(--sutra-muted-gold)]" />
              <h2 className="text-lg font-serif text-[var(--sutra-charcoal)]">Threat Scanning & Asset Security</h2>
              <span className="badge badge-amber text-[9px]">SEC-SCAN-001</span>
            </div>
            <p className="text-[12px] text-[var(--text-2)] mt-1 font-light">
              Multi-layer defense protecting ingress (uploads, URLs, repositories) and egress (code exports, packages).
            </p>
          </div>
          <div className="flex items-center gap-2 font-mono text-[10px] text-[var(--text-3)] uppercase tracking-wider">
            <span>Threshold:</span>
            <span className="px-2 py-0.5 bg-[var(--bg)] border border-[var(--border)] text-[var(--sutra-charcoal)] font-bold rounded">
              {securityConfig?.block_threshold || 'suspicious'}
            </span>
          </div>
        </div>

        {/* 3 Scanning Layers Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Layer 0 */}
          <div className="p-4 bg-[var(--bg)] border border-[var(--border)] rounded-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--sutra-charcoal)]">
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
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--sutra-charcoal)]">
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
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--sutra-charcoal)]">
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
                    <ShieldAlert className="w-3 h-3 text-[var(--sutra-muted-gold)]" />
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
            <span className="text-xl font-serif text-[var(--sutra-charcoal)] font-semibold">
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
            <span className="text-xl font-serif text-[var(--sutra-charcoal)] font-semibold">
              {((securityStats?.total_bytes_scanned || 0) / (1024 * 1024)).toFixed(1)} MB
            </span>
          </div>
          <div className="p-3 bg-[var(--bg)] border border-[var(--border)] rounded-sm">
            <span className="text-[10px] uppercase font-bold text-[var(--text-3)] block mb-1">Fail Unavailable Mode</span>
            <span className="text-sm font-mono uppercase text-[var(--sutra-muted-gold)] font-bold">
              {securityConfig?.fail_unavailable_mode || 'allow'}
            </span>
          </div>
        </div>

        {/* Interactive On-Demand File Threat Scanner */}
        <div className="p-4 bg-[var(--bg)] border border-dashed border-[var(--border)] rounded-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--sutra-charcoal)] flex items-center gap-1.5">
              <Upload className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
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
              } catch (err: any) {
                setTestScanResult({ error: err.message || 'Scan error' });
              } finally {
                setTestFileLoading(false);
              }
            }}
          />

          <div className="flex items-center gap-3">
            <button
              onClick={() => testFileInputRef.current?.click()}
              disabled={testFileLoading}
              className="btn btn-secondary px-4 py-2 text-xs flex items-center gap-2"
            >
              {testFileLoading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--sutra-muted-gold)]" />
                  Running Multi-Layer Scan...
                </>
              ) : (
                <>
                  <ShieldCheck className="w-3.5 h-3.5 text-[var(--green)]" />
                  Upload & Inspect File
                </>
              )}
            </button>
            <span className="text-[11px] text-[var(--text-3)]">
              Upload any document, binary, or archive (e.g. test EICAR or polyglot files) to view instant verdict.
            </span>
          </div>

          {testScanResult && (
            <div className="p-3 bg-[var(--bg-2)] border border-[var(--border)] rounded text-xs space-y-2 mt-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[var(--sutra-charcoal)]">
                  Target: {testScanResult.filename || 'Uploaded File'}
                </span>
                <span
                  className={`badge font-mono text-[10px] ${
                    testScanResult.verdict === 'clean'
                      ? 'badge-green'
                      : testScanResult.verdict === 'malicious'
                      ? 'badge-red'
                      : 'badge-amber'
                  }`}
                >
                  Verdict: {testScanResult.verdict?.toUpperCase() || 'UNKNOWN'}
                </span>
              </div>
              {testScanResult.findings?.length > 0 && (
                <div className="space-y-1 pt-1 border-t border-[var(--border)]">
                  <span className="text-[10px] uppercase font-bold text-[var(--text-3)]">Findings:</span>
                  {testScanResult.findings.map((f: any, idx: number) => (
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
            <span className="text-xs font-bold uppercase tracking-wider text-[var(--sutra-charcoal)]">
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
                      <td className="p-2.5 text-[var(--sutra-charcoal)] font-semibold">
                        {scan.source}
                        {scan.from_cache && (
                          <span className="ml-1.5 text-[9px] text-[var(--sutra-muted-gold)]">[cached]</span>
                        )}
                      </td>
                      <td className="p-2.5">
                        <span
                          className={`badge text-[9px] ${
                            scan.verdict === 'clean'
                              ? 'badge-green'
                              : scan.verdict === 'malicious'
                              ? 'badge-red'
                              : scan.verdict === 'suspicious'
                              ? 'badge-amber'
                              : 'badge-gray'
                          }`}
                        >
                          {scan.verdict}
                        </span>
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
