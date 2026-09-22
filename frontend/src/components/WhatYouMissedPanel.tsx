'use client';

import React from 'react';

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
    <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-5 space-y-4 my-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">🔍</span>
          <div>
            <h3 className="text-sm font-semibold text-amber-300">
              What You Missed — Architecture & Compliance Gaps
            </h3>
            <p className="text-xs text-amber-200/70">
              Our AI gap analyzer flagged essential NFRs, regulatory standards, and open questions.
            </p>
          </div>
        </div>
        <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-amber-900/60 text-amber-300 border border-amber-700/50">
          {missingRequirements.length + openQuestions.length} Items Flagged
        </span>
      </div>

      {/* Prioritized Open Questions */}
      {openQuestions.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-xs uppercase tracking-wider font-semibold text-amber-400/90">
            Critical Clarifications (with Business Impact)
          </h4>
          <div className="space-y-2.5">
            {openQuestions.map((q) => (
              <div
                key={q.id}
                className="p-3 rounded-lg bg-slate-900/80 border border-amber-500/20 text-xs space-y-1.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="font-medium text-slate-200">{q.question}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 uppercase font-mono">
                    {q.category}
                  </span>
                </div>
                <div className="text-slate-400 flex items-start gap-1">
                  <span className="text-amber-400 font-semibold text-[11px]">Why it matters:</span>
                  <span>{q.why_it_matters}</span>
                </div>

                {q.suggested_answers && q.suggested_answers.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {q.suggested_answers.map((ans, idx) => (
                      <button
                        key={idx}
                        onClick={() => onAnswerQuestion?.(q.id, ans)}
                        className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 text-[11px] transition-colors"
                      >
                        {ans}
                      </button>
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
          <h4 className="text-xs uppercase tracking-wider font-semibold text-amber-400/90">
            Missing Regulatory & Non-Functional Requirements
          </h4>
          <div className="grid sm:grid-cols-2 gap-2">
            {missingRequirements.map((req) => (
              <div
                key={req.id}
                className="p-2.5 rounded bg-slate-900/60 border border-slate-800 text-xs flex flex-col justify-between"
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="font-mono text-[10px] uppercase text-amber-400">
                    [{req.kind}]
                  </span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-800 text-slate-300">
                    Priority: {req.priority}
                  </span>
                </div>
                <p className="text-slate-300">{req.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
