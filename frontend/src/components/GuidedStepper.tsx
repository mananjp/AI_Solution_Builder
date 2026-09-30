'use client';

import React from 'react';
import { ProgressStepper } from '@/components/lab/progress-stepper';

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

/**
 * Stage rail across the top of a solution.
 *
 * Drawn with the lab's `ProgressStepper`, which fills its connector with one
 * spring shared by the fill and the head, so advancing a stage reads as the
 * line growing rather than a colour change landing after the fact.
 *
 * Completion is derived from `currentStage`: everything before the head is
 * done, everything after it is not. The previous hand-rolled version also took
 * a `completedStages` list, but it was only ever passed the stages that were
 * already implied by the current index, so the second source of truth could
 * disagree with the first rather than add anything.
 */
export function GuidedStepper({ currentStage }: { currentStage: StageKey }) {
  const currentIndex = Math.max(
    STAGES.findIndex((stage) => stage.key === currentStage),
    0,
  );

  return (
    <div className="w-full bg-[var(--bg-2)] border-b border-[var(--border)] px-6 py-3 shadow-2xs">
      <div className="max-w-6xl mx-auto">
        <ProgressStepper
          // Label and description on one line: the lab stepper renders a single
          // label per step, and the sub-label is the part that can be dropped
          // without losing the sequence.
          steps={STAGES.map((stage) => `${stage.label} · ${stage.description}`)}
          current={currentIndex}
          label="Solution stages"
        />
      </div>
    </div>
  );
}

export { STAGES };
