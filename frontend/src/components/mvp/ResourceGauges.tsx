'use client';

import React, { useEffect, useState } from 'react';
import { Activity, Cpu, HardDrive } from 'lucide-react';
import { systemApi } from '@/lib/api';
import { SystemResources } from '@/types';

const fmtBytes = (bytes?: number | null): string => {
  if (!bytes) return '—';
  const gb = bytes / 1073741824;
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / 1048576).toFixed(0)} MB`;
};

function Bar({
  value,
  tone,
}: {
  value?: number | null;
  tone: 'amber' | 'green' | 'red';
}) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  const color =
    tone === 'green' ? 'var(--green)' : tone === 'red' ? 'var(--red)' : 'var(--sutra-muted-gold)';
  return (
    <div className="w-full h-1.5 bg-[var(--bg)] rounded-full overflow-hidden border border-[var(--border)]">
      <div
        className="h-full transition-all duration-700"
        style={{ width: `${Math.max(3, v)}%`, background: color }}
      />
    </div>
  );
}

export function ResourceGauges({
  engineOnline,
  className = '',
}: {
  engineOnline: boolean;
  className?: string;
}) {
  const [res, setRes] = useState<SystemResources | null>(null);

  useEffect(() => {
    if (!engineOnline) {
      const timer = setTimeout(() => setRes(null), 0);
      return () => clearTimeout(timer);
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const r = await systemApi.resources();
        if (!cancelled) setRes(r);
      } catch {
        if (!cancelled) setRes(null);
      }
    };
    poll();
    const timer = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [engineOnline]);

  if (!engineOnline || !res || res.cpu_percent == null) {
    return (
      <div className={`flex items-center gap-3 ${className}`}>
        <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)]">
          <Activity className="w-3 h-3" />
          <span>Resources unavailable</span>
        </span>
      </div>
    );
  }

  const cpu = res.cpu_percent;
  const disk = res.disk_percent;
  const mem = res.memory;

  return (
    <div className={`grid grid-cols-3 gap-3 ${className}`}>
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1 text-[9px] uppercase tracking-widest font-bold text-[var(--text-3)]">
            <Cpu className="w-3 h-3" />
            CPU
          </span>
          <span className="font-mono text-[10px] font-bold text-[var(--sutra-charcoal)]">
            {Math.round(cpu)}%
          </span>
        </div>
        <Bar value={cpu} tone={cpu > 85 ? 'red' : 'amber'} />
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1 text-[9px] uppercase tracking-widest font-bold text-[var(--text-3)]">
            <HardDrive className="w-3 h-3" />
            Disk
          </span>
          <span className="font-mono text-[10px] font-bold text-[var(--sutra-charcoal)]">
            {disk != null ? `${Math.round(disk)}%` : '—'}
          </span>
        </div>
        <Bar value={disk} tone={disk != null && disk > 85 ? 'red' : 'amber'} />
      </div>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1 text-[9px] uppercase tracking-widest font-bold text-[var(--text-3)]">
            <Activity className="w-3 h-3" />
            Mem
          </span>
          <span className="font-mono text-[10px] font-bold text-[var(--sutra-charcoal)]">
            {mem ? `${Math.round(mem.percent)}%` : '—'}
          </span>
        </div>
        <Bar value={mem?.percent} tone={mem && mem.percent > 85 ? 'red' : 'green'} />
      </div>

      {mem && (
        <p className="col-span-3 text-[9px] font-mono text-[var(--text-3)]">
          {fmtBytes(mem.used_mb * 1048576)} / {fmtBytes(mem.total_mb * 1048576)} in use · sample
          every 5s
        </p>
      )}
    </div>
  );
}