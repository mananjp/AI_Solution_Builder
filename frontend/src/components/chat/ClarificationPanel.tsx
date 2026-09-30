'use client';

import React from 'react';
import { HelpCircle, Sparkles, X, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

export interface ClarificationOption {
  label: string;
  value: string;
  description?: string;
}

export interface ClarificationQuestion {
  id: string;
  field: string;
  question: string;
  rationale: string;
  options: ClarificationOption[];
}

interface ClarificationPanelProps {
  questions: ClarificationQuestion[];
  onSelectOption: (question: ClarificationQuestion, option: ClarificationOption) => void;
  onDismiss: () => void;
  loading?: boolean;
}

export function ClarificationPanel({
  questions,
  onSelectOption,
  onDismiss,
  loading = false,
}: ClarificationPanelProps) {
  if (!questions || questions.length === 0) return null;

  return (
    <div className="mb-3 rounded-xl border border-[var(--sutra-strong)]/30 bg-[var(--bg-2)] p-4 shadow-md animate-fade-in space-y-4">
      <div className="flex items-center justify-between border-b border-[var(--border)] pb-2.5">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--sutra-strong)]/10 text-[var(--sutra-strong)]">
            <HelpCircle className="h-4 w-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--sutra-ink)]">
              Proactive Requirement Alignment
            </h4>
            <p className="text-[11px] text-[var(--text-3)] font-light">
              Clarify key choices before code generation to avoid default CRUD placeholders
            </p>
          </div>
        </div>
        <button
          onClick={onDismiss}
          disabled={loading}
          className="text-[var(--text-3)] hover:text-[var(--sutra-ink)] p-1 rounded transition-colors"
          title="Dismiss suggestions"
          aria-label="Dismiss suggestions"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-4">
        {questions.map((q) => (
          <div key={q.id} className="space-y-2">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-xs font-semibold text-[var(--sutra-ink)]">
                {q.question}
              </span>
              <span className="text-[10px] text-[var(--text-3)] italic">
                {q.rationale}
              </span>
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {q.options.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => onSelectOption(q, opt)}
                  disabled={loading}
                  className="group flex flex-col items-start p-2.5 rounded-lg border border-[var(--border)] bg-[var(--bg)] hover:border-[var(--sutra-strong)] hover:shadow-sm transition-all text-left cursor-pointer"
                >
                  <div className="flex items-center justify-between w-full">
                    <span className="text-xs font-bold text-[var(--sutra-ink)] group-hover:text-[var(--sutra-strong)] transition-colors">
                      {opt.label}
                    </span>
                    <ChevronRight className="h-3.5 w-3.5 text-[var(--text-3)] group-hover:translate-x-0.5 transition-transform" />
                  </div>
                  {opt.description && (
                    <span className="text-[11px] text-[var(--text-3)] mt-1 line-clamp-2 font-light">
                      {opt.description}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between pt-1 text-[11px] text-[var(--text-3)]">
        <span className="flex items-center gap-1.5 font-medium">
          <Sparkles className="h-3.5 w-3.5 text-[var(--sutra-strong)]" />
          Click an option to automatically include it in your build prompt
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={onDismiss}
          className="h-7 text-xs text-[var(--text-2)] hover:text-[var(--sutra-ink)]"
        >
          Skip & Build with Defaults
        </Button>
      </div>
    </div>
  );
}
