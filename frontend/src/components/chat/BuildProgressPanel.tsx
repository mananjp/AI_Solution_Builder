'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Activity, CheckCircle2, Circle, Clock, Loader2, Terminal, Zap } from 'lucide-react';
import clsx from 'clsx';
import { Skeleton } from '@/components/chat/Skeleton';
import {
  TOTAL_MILESTONES,
  useProgressStalled,
  useSmoothProgress,
  type BuildProgress,
  type ChatState,
} from '@/hooks/useChatSession';
import type { TranslationKey } from '@/lib/i18n/dictionaries';

const MILESTONE_LABELS: TranslationKey[] = [
  'buildMilestones.domainArchitecture',
  'buildMilestones.databaseSchema',
  'buildMilestones.fullStackScaffold',
  'buildMilestones.domainModels',
  'buildMilestones.codebaseVerification',
  'buildMilestones.productionPackage',
];

/** Phases that map to milestone 3 (the UI scaffold also covers the AI design pass). */
const SCAFFOLD_PHASES = new Set(['scaffolding', 'designing']);

function useElapsed(startedAt: number | null, active: boolean) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!active || !startedAt) return;
    const update = () => setSeconds(Math.round((Date.now() - startedAt) / 1000));
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [startedAt, active]);
  return active ? seconds : 0;
}

function LiveLog({ logs }: { logs: string[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'nearest' });
  }, [logs.length]);

  if (logs.length === 0) return null;
  return (
    <div className="bg-[var(--bg)] border border-[var(--border)] p-3">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)] mb-2">
        <Terminal className="w-3 h-3" />
        <span>Live build log</span>
      </div>
      <div className="max-h-40 overflow-y-auto space-y-1 font-mono text-[10px] text-[var(--text-2)] bg-[var(--bg-2)] p-2 rounded-sm border border-[var(--border)]">
        {logs.map((log, i) => (
          <div key={i} className="break-words leading-tight text-[var(--sutra-muted-gold)]">
            {log}
          </div>
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}

/**
 * Live build dashboard.
 *
 * The bar is smoothed toward the last percentage actually reported by the
 * pipeline (never past it) so long LLM-bound stretches don't look frozen, while
 * the milestone checklist only ticks on real `build_progress` phase events.
 */
export function BuildProgressPanel({
  state,
  t,
}: {
  state: ChatState;
  t: (key: TranslationKey) => string;
}) {
  const progress: BuildProgress | null = state.progress;
  const active = state.streaming && Boolean(progress);
  const elapsed = useElapsed(progress?.startedAt ?? null, active);
  const shown = useSmoothProgress(progress?.target ?? 0, active);
  const done = progress?.phase === 'completed' || (progress?.target ?? 0) >= 100;
  const stalled = useProgressStalled(progress?.target ?? 0, active && !done);
  const scaffoldPhase = progress ? SCAFFOLD_PHASES.has(progress.phase) : false;

  if (!active) return null;

  const steps = progress?.steps ?? [];
  const activeIndex = steps.findIndex((s) => s.status === 'active');

  return (
    <div className="space-y-4 animate-fade-in" role="status" aria-live="polite">
      {/* Status + bar */}
      <div className="p-3 bg-[var(--bg)] border border-[var(--sutra-muted-gold)] shadow-sm">
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)] min-w-0">
            <Activity className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] animate-pulse shrink-0" />
            <span className="truncate">{done ? 'Build complete' : 'Building application'}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="flex items-center gap-1 text-[10px] font-mono text-[var(--text-3)]">
              <Clock className="w-3 h-3" />
              {elapsed}s
            </span>
            <span className="text-[11px] font-mono font-bold text-[var(--sutra-muted-gold)] tabular-nums">
              {Math.round(shown)}%
            </span>
          </div>
        </div>

        <div className="w-full h-1.5 bg-[var(--bg-2)] rounded-full overflow-hidden border border-[var(--border)] relative">
          <div
            className="h-full bg-gradient-to-r from-[var(--sutra-muted-gold)] to-[var(--green)] transition-[width] duration-150 ease-out"
            style={{ width: `${Math.max(2, shown)}%` }}
          />
          {stalled && (
            <div
              className="progress-indeterminate absolute inset-y-0 left-0 w-1/4 opacity-80"
              aria-hidden="true"
            />
          )}
        </div>

        <p className="text-[11px] text-[var(--text-2)] font-light mt-2 break-words min-h-[2.5em]">
          {progress?.message}
          {stalled && (
            <span className="text-[var(--text-3)]">
              {' '}
              · still working, awaiting next milestone…
            </span>
          )}
        </p>
      </div>

      {/* Milestones */}
      <div className="bg-[var(--bg)] border border-[var(--border)] p-3">
        <div className="flex items-center justify-between text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)] mb-2.5">
          <span>Execution milestones</span>
          <span className="font-mono">
            {Math.min((activeIndex === -1 ? TOTAL_MILESTONES : activeIndex) + (done ? 1 : 0), TOTAL_MILESTONES)}/
            {TOTAL_MILESTONES}
          </span>
        </div>
        <ol className="space-y-2">
          {MILESTONE_LABELS.map((key, i) => {
            const status = done ? 'completed' : (steps[i]?.status ?? (i === 0 ? 'active' : 'pending'));
            const waiting = !done && i === (activeIndex === -1 ? 0 : activeIndex + 1) && scaffoldPhase && i === 3;
            return (
              <li
                key={key}
                className={clsx(
                  'flex items-center gap-2.5 text-[11px] transition-opacity',
                  status === 'pending' ? 'opacity-60' : 'opacity-100'
                )}
              >
                {status === 'completed' ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-[var(--green)] shrink-0" />
                ) : status === 'active' ? (
                  <Loader2 className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] animate-spin shrink-0" />
                ) : waiting ? (
                  <Zap className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] shrink-0 animate-pulse" />
                ) : (
                  <Circle className="w-3.5 h-3.5 text-[var(--text-3)]/40 shrink-0" />
                )}
                <span
                  className={clsx(
                    'truncate',
                    status === 'completed'
                      ? 'text-[var(--text-2)]'
                      : status === 'active' || waiting
                        ? 'text-[var(--sutra-charcoal)] font-bold'
                        : 'text-[var(--text-3)] font-light'
                  )}
                  title={t(key)}
                >
                  {t(key)}
                </span>
              </li>
            );
          })}
        </ol>
      </div>

      <LiveLog logs={progress?.logs ?? []} />
    </div>
  );
}

/** Shown while the orchestrator is composing its reply (no build requested yet). */
export function ThinkingPanel({ message }: { message: string }) {
  return (
    <div className="p-3 bg-[var(--bg)] border border-[var(--border)] shadow-sm animate-fade-in" role="status">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">
        <Loader2 className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] animate-spin" />
        <span>Thinking</span>
      </div>
      <div className="mt-2.5 space-y-2">
        <Skeleton className="h-2.5 w-full" />
        <Skeleton className="h-2.5 w-4/5" />
      </div>
      <p className="text-[11px] text-[var(--text-2)] font-light mt-2 break-words">{message}</p>
    </div>
  );
}
