'use client';

import React from 'react';
import { Button } from "@/components/ui/button";

export interface OpenQuestion {
  id: string;
  question: string;
  category: string;
  why_it_matters: string;
  suggested_answers?: string[];
}

export interface MissingRequirement {
  id: string;
  kind: string;
  text: string;
  status: string;
  priority: string;
  evidence?: Array<{ source: string; excerpt: string }>;
}

interface WhatYouMissedPanelProps {
  missingRequirements: MissingRequirement[];
  openQuestions: OpenQuestion[];
  onAnswerQuestion?: (questionId: string, answer: string) => void;
}

export function WhatYouMissedPanel({
  missingRequirements,
  openQuestions,
  onAnswerQuestion,
}: WhatYouMissedPanelProps) {
  if (!missingRequirements.length && !openQuestions.length) return null;

  return (
    <div className="rounded-md border border-[var(--sutra-strong)]/30 bg-[var(--bg-2)] p-5 space-y-4 my-4 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="text-xl">🔍</span>
          <div>
            <h3 className="text-sm font-serif font-bold text-[var(--sutra-ink)]">
              What You Missed — Architecture &amp; Compliance Gaps
            </h3>
            <p className="text-xs text-[var(--text-2)] font-light">
              Our AI gap analyzer flagged essential NFRs, regulatory standards, and open questions.
            </p>
          </div>
        </div>
        <span className="text-xs font-mono px-2.5 py-0.5 rounded-sm bg-[var(--sutra-strong)]/15 text-[var(--sutra-strong)] border border-[var(--sutra-strong)]/30 font-semibold">
          {missingRequirements.length + openQuestions.length} Items Flagged
        </span>
      </div>

      {/* Prioritized Open Questions */}
      {openQuestions.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs uppercase tracking-wider font-semibold text-[var(--sutra-strong)]">
            Critical Clarifications (with Business Impact)
          </h4>
          <div className="space-y-2.5">
            {openQuestions.map((q) => (
              <div
                key={q.id}
                className="p-3.5 rounded-sm bg-[var(--bg-3)] border border-[var(--border)] text-xs space-y-1.5 shadow-2xs"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium text-[var(--sutra-ink)]">{q.question}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-sm bg-[var(--sutra-strong)]/15 text-[var(--sutra-strong)] uppercase font-mono border border-[var(--sutra-strong)]/20 font-semibold whitespace-nowrap">
                    {q.category}
                  </span>
                </div>
                <div className="text-[var(--text-2)] flex items-start gap-1 font-light">
                  <span className="text-[var(--sutra-strong)] font-semibold text-[11px]">Why it matters:</span>
                  <span>{q.why_it_matters}</span>
                </div>

                {q.suggested_answers && q.suggested_answers.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {q.suggested_answers.map((ans, idx) => (
                      <Button variant="secondary" size="icon-sm"
                        key={idx}
                        onClick={() => onAnswerQuestion?.(q.id, ans)}
                        className="bg-[var(--bg-2)] hover:bg-[var(--bg)] text-[var(--text)] border border-[var(--border)] text-[11px] transition-colors"
                      >
                        {ans}
                      </Button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Missing Requirements / Compliance */}
      {missingRequirements.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-xs uppercase tracking-wider font-semibold text-[var(--sutra-strong)]">
            Missing Regulatory &amp; Non-Functional Requirements
          </h4>
          <div className="grid sm:grid-cols-2 gap-2">
            {missingRequirements.map((req) => (
              <div
                key={req.id}
                className="p-3 rounded-sm bg-[var(--bg-3)] border border-[var(--border)] text-xs flex flex-col justify-between"
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className="font-mono text-[10px] uppercase text-[var(--sutra-strong)] font-semibold">
                    [{req.kind}]
                  </span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-sm bg-[var(--bg-2)] text-[var(--text-2)] border border-[var(--border)] font-mono">
                    Priority: {req.priority}
                  </span>
                </div>
                <p className="text-[var(--sutra-ink)] font-light leading-relaxed">{req.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
