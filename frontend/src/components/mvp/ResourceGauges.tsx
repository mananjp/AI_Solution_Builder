'use client';

import { useEffect, useMemo, useState } from 'react';

import { systemApi } from '@/lib/api';
import type { SystemResources } from '@/types';
import { StatCounter, type Stat } from '@/components/lab/stat-counter';

// Two minutes of five-second samples. Enough for the sparkline to read as a
// trend rather than noise, short enough that the first paint is not a spinner.
const WINDOW = 24;

const fmtBytes = (bytes?: number | null): string => {
  if (!bytes) return '—';
  const gb = bytes / 1073741824;
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bytes / 1048576).toFixed(0)} MB`;
};

const PERCENT = new Intl.NumberFormat('en-US', {
  style: 'percent',
  maximumFractionDigits: 0,
});

/**
 * Trend as a fraction of the earlier mean, so a card can say "+12%" without
 * inventing a comparison period the app does not actually track. The first
 * window has nothing to compare against and reports no change.
 */
function trend(series: number[]): number {
  if (series.length < 4) return 0;
  const half = Math.floor(series.length / 2);
  const earlier = series.slice(0, half);
  const later = series.slice(half);
  const mean = (values: number[]) => values.reduce((a, b) => a + b, 0) / values.length;
  const before = mean(earlier);
  if (before === 0) return 0;
  return (mean(later) - before) / before;
}

/**
 * Build-host resource usage as three counting stat cards.
 *
 * The figures are real samples taken on the 5s poll, not decoration: each card
 * counts up to the latest reading, and the sparkline behind it is the actual
 * recent window. Nothing is shown until the first sample lands, because a
 * gauge that renders before it has been measured is a guess.
 */
export function ResourceGauges({
  engineOnline,
  className = '',
}: {
  engineOnline: boolean;
  className?: string;
}) {
  const [res, setRes] = useState<SystemResources | null>(null);
  const [cpu, setCpu] = useState<number[]>([]);
  const [disk, setDisk] = useState<number[]>([]);
  const [mem, setMem] = useState<number[]>([]);

  useEffect(() => {
    // Derived from `engineOnline` at render rather than reset here: clearing
    // state inside the effect is the cascading-render case the lint rule flags,
    // and the early return below already stops collection.
    if (!engineOnline) return;
    let cancelled = false;
    const push = (series: number[], next: number) =>
      [...series, next].slice(-WINDOW);

    const poll = async () => {
      try {
        const r = await systemApi.resources();
        if (cancelled) return;
        setRes(r);
        // Narrowed to locals first: a property read is not narrowed inside the
        // updater closure, so reading it there would still be `number | null`.
        const { cpu_percent: cpu, disk_percent: disk, memory: mem } = r;
        // API percentages are 0–100. Intl's percent formatter expects 0–1.
        if (cpu != null) setCpu((s) => push(s, cpu / 100));
        if (disk != null) setDisk((s) => push(s, disk / 100));
        const used = mem?.percent;
        if (used != null) setMem((s) => push(s, used / 100));
      } catch {
        if (cancelled) return;
        setRes(null);
      }
    };
    void poll();
    const timer = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [engineOnline]);

  const stats = useMemo<Stat[]>(() => {
    const latest = (series: number[]) => series[series.length - 1];
    const out: Stat[] = [];
    if (cpu.length) {
      out.push({
        label: 'CPU',
        value: latest(cpu),
        format: PERCENT,
        // CPU climbing is the thing worth noticing, so up is the alarming side.
        trend: trend(cpu),
        goodWhen: 'down',
        series: cpu,
      });
    }
    if (disk.length) {
      out.push({
        label: 'Disk',
        value: latest(disk),
        format: PERCENT,
        trend: trend(disk),
        goodWhen: 'down',
        series: disk,
      });
    }
    if (mem.length) {
      out.push({
        label: 'Memory',
        value: latest(mem),
        format: PERCENT,
        trend: trend(mem),
        goodWhen: 'down',
        series: mem,
      });
    }
    return out;
  }, [cpu, disk, mem]);

  // Offline hides the cards outright, so the last samples are never shown as
  // though they were current.
  if (!engineOnline || !res || res.cpu_percent == null) {
    return (
      <div className={`flex items-center gap-3 ${className}`}>
        <span className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)]">
          Resources unavailable
        </span>
      </div>
    );
  }

  return (
    <div className={className}>
      <StatCounter stats={stats} />
      {res.memory && (
        <p className="mt-3 text-[9px] font-mono text-[var(--text-3)]">
          {fmtBytes(res.memory.used_mb * 1048576)} / {fmtBytes(res.memory.total_mb * 1048576)} in
          use · sampled every 5s, last {cpu.length} reading{cpu.length === 1 ? '' : 's'}
        </p>
      )}
    </div>
  );
}
