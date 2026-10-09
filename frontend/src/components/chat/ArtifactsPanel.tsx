'use client';

import React from 'react';
import { CheckCircle2, Layers, Play, Rocket } from 'lucide-react';
import clsx from 'clsx';
import { BuildCard } from '@/components/mvp/BuildCard';
import { ArtifactsSkeleton, Skeleton } from '@/components/chat/Skeleton';
import { BuildProgressPanel, ThinkingPanel } from '@/components/chat/BuildProgressPanel';
import type { ChatState } from '@/hooks/useChatSession';
import type { MVPBuild, MVPDeployResult } from '@/types';
import type { TranslationKey } from '@/lib/i18n/dictionaries';

function EmptyArtifacts({
  title,
  hint,
  onTriggerBuild,
  disabled,
}: {
  title: string;
  hint: string;
  onTriggerBuild?: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center space-y-4 py-8 px-4">
      <div className="w-14 h-14 rounded-full bg-[var(--sutra-muted-gold)]/15 border border-[var(--sutra-muted-gold)]/30 flex items-center justify-center text-[var(--sutra-muted-gold)] shadow-sm">
        <Rocket className="w-6 h-6" />
      </div>
      <div>
        <p className="text-[12px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">{title}</p>
        <p className="text-[11px] text-[var(--text-2)] font-light max-w-[220px] mx-auto mt-2 leading-relaxed">
          {hint}
        </p>
      </div>
      {onTriggerBuild && (
        <button
          type="button"
          onClick={onTriggerBuild}
          disabled={disabled}
          className="mt-2 inline-flex items-center gap-2 px-5 py-2.5 bg-[var(--sutra-charcoal)] hover:bg-black text-[var(--sutra-warm-ivory)] rounded-sm text-[11px] uppercase tracking-widest font-bold shadow-md transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer disabled:opacity-50"
        >
          <Rocket className="w-3.5 h-3.5 text-amber-400" />
          <span>Build &amp; Deploy Now</span>
        </button>
      )}
    </div>
  );
}

export function ArtifactsPanel({
  state,
  t,
  buildOrchestratedLabel,
  viewArtifactsLabel,
  buildToggleHint,
  onDeploy,
  onConfigure,
  onDownload,
  onDestroy,
  onTriggerBuild,
}: {
  state: ChatState;
  t: (key: TranslationKey) => string;
  buildOrchestratedLabel: string;
  viewArtifactsLabel: string;
  buildToggleHint: string;
  onDeploy: (b: MVPBuild) => void;
  onConfigure: (b: MVPBuild) => void;
  onDownload: (b: MVPBuild) => void;
  onDestroy: (b: MVPBuild) => void;
  onTriggerBuild?: () => void;
}) {
  const showSkeleton = state.buildsStatus === 'loading' && state.builds.length === 0;
  const showProgress = state.streaming && Boolean(state.progress);
  const showThinking = state.streaming && !state.progress;
  const empty = !showSkeleton && !showProgress && !showThinking && state.builds.length === 0;

  return (
    <div className="flex flex-col h-full min-h-0 bg-[var(--bg-2)] border border-[var(--border)] rounded-sm overflow-hidden">
      <div className="p-3.5 border-b border-[var(--border)] flex items-center justify-between bg-[var(--bg)] shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Layers className="w-4 h-4 text-[var(--text-3)] shrink-0" />
          <h2 className="text-[11px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)] truncate">
            Build artifacts
          </h2>
          {state.builds.length > 0 && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-[var(--bg-2)] border border-[var(--border)] text-[var(--text-2)]">
              {state.builds.length}
            </span>
          )}
        </div>
        {state.solutionId && state.builds.length > 0 && (
          <a
            href={`/solution/${state.solutionId}`}
            className="text-[10px] font-medium text-[var(--sutra-muted-gold)] hover:underline shrink-0"
          >
            {viewArtifactsLabel} →
          </a>
        )}
      </div>

      <div className="flex-1 p-3.5 overflow-y-auto overflow-x-hidden min-h-0">
        {showSkeleton && <ArtifactsSkeleton />}

        {state.builds.length > 0 && (
          <div className="space-y-3 animate-fade-in min-w-0">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-bold text-[var(--green)] bg-[var(--bg)] border border-[var(--border)] p-2">
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
              <span>
                {state.builds.length} {buildOrchestratedLabel}
              </span>
            </div>
            {state.builds.map((b) => (
              <div key={b.build_id} className="min-w-0">
                <BuildCard
                  build={b}
                  isDeployed={Boolean(b.repo_url)}
                  onDeploy={() => onDeploy(b)}
                  onConfigure={() => onConfigure(b)}
                  onDownload={() => onDownload(b)}
                  onDestroy={() => onDestroy(b)}
                />
              </div>
            ))}
          </div>
        )}

        {(showProgress || showThinking) && (
          <div
            className={clsx(
              'animate-fade-in',
              state.builds.length > 0 && 'mt-4 border-t border-[var(--border)] pt-4'
            )}
          >
            {showProgress ? (
              <BuildProgressPanel state={state} t={t} />
            ) : (
              <ThinkingPanel message="Synthesizing architecture & specifications…" />
            )}
          </div>
        )}

        {empty && (
          <EmptyArtifacts
            title={t('chat.awaitingSynthesis')}
            hint={buildToggleHint}
            onTriggerBuild={onTriggerBuild}
            disabled={state.streaming}
          />
        )}

        {!showSkeleton && state.buildsStatus === 'loading' && state.builds.length > 0 && (
          <div className="mt-3 flex items-center gap-2 text-[10px] text-[var(--text-3)]">
            <Skeleton className="h-2.5 w-20" />
            <Skeleton className="h-2.5 w-12" />
          </div>
        )}
      </div>
    </div>
  );
}

export type DeployHandler = (result: MVPDeployResult | string) => void;
