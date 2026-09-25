'use client';

import React from 'react';

export type StageKey = 'input' | 'clarify' | 'blueprint' | 'approve' | 'build' | 'deploy' | 'live';

interface Step {
  key: StageKey;
  label: string;
  description: string;
}

const STAGES: Step[] = [
  { key: 'input', label: '1. Input', description: 'Idea & Docs' },
  { key: 'clarify', label: '2. Clarify', description: 'Gap & NFRs' },
  { key: 'blueprint', label: '3. Blueprint', description: 'HLD, ER & Spec' },
  { key: 'approve', label: '4. Approve', description: 'Sign-off Gate' },
  { key: 'build', label: '5. Build', description: 'Code Synthesis' },
  { key: 'deploy', label: '6. Deploy', description: 'Multi-Tier Setup' },
  { key: 'live', label: '7. Live', description: 'Verified System' },
];

interface GuidedStepperProps {
  currentStage: StageKey;
  completedStages?: StageKey[];
  onStageClick?: (stage: StageKey) => void;
}

export function GuidedStepper({
  currentStage,
  completedStages = [],
  onStageClick,
}: GuidedStepperProps) {
  const currentIndex = STAGES.findIndex((s) => s.key === currentStage);

  return (
    <div className="w-full bg-[var(--bg-2)] border-b border-[var(--border)] px-6 py-3 shadow-2xs">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        {STAGES.map((step, idx) => {
          const isCurrent = step.key === currentStage;
          const isDone = completedStages.includes(step.key) || idx < currentIndex;

          return (
            <React.Fragment key={step.key}>
              <div
                onClick={() => onStageClick?.(step.key)}
                className={`flex items-center gap-2.5 cursor-pointer transition-all ${
                  isCurrent
                    ? 'text-[var(--sutra-charcoal)] font-semibold scale-105'
                    : isDone
                    ? 'text-emerald-700 font-medium'
                    : 'text-[var(--text-3)] hover:text-[var(--text-2)]'
                }`}
              >
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-mono transition-colors ${
                    isCurrent
                      ? 'bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)] shadow-sm ring-2 ring-[var(--sutra-muted-gold)]/50'
                      : isDone
                      ? 'bg-emerald-600 text-white'
                      : 'bg-[var(--bg-3)] text-[var(--text-3)] border border-[var(--border)]'
                  }`}
                >
                  {isDone ? '✓' : idx + 1}
                </div>
                <div className="hidden sm:block text-left">
                  <div className="text-xs font-semibold leading-tight">{step.label}</div>
                  <div className="text-[10px] text-[var(--text-3)] font-light">{step.description}</div>
                </div>
              </div>

              {idx < STAGES.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-3 transition-colors ${
                    idx < currentIndex ? 'bg-emerald-600/70' : 'bg-[var(--border)]'
                  }`}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
