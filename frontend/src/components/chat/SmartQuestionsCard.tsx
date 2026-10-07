'use client';

import React, { useState } from 'react';
import { HelpCircle, Send, CheckCircle2 } from 'lucide-react';
import clsx from 'clsx';
import type { ConversationalQuestion } from '@/types';

interface SmartQuestionsCardProps {
  questions: ConversationalQuestion[];
  onSubmit: (answers: Record<string, string>) => void;
  disabled?: boolean;
}

export function SmartQuestionsCard({ questions, onSubmit, disabled = false }: SmartQuestionsCardProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);

  const handleSelectOption = (questionId: string, value: string) => {
    if (disabled || submitted) return;
    setAnswers((prev) => ({
      ...prev,
      [questionId]: value,
    }));
  };

  const handleCustomInput = (questionId: string, value: string) => {
    if (disabled || submitted) return;
    setAnswers((prev) => ({
      ...prev,
      [questionId]: value,
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (disabled || submitted) return;
    setSubmitted(true);
    onSubmit(answers);
  };

  const answeredCount = Object.values(answers).filter((a) => a.trim().length > 0).length;

  return (
    <div className="my-6 rounded-md border border-[var(--sutra-muted-gold)] bg-[var(--bg)] p-5 shadow-sm transition-all animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-2.5 pb-3 border-b border-[var(--border)] mb-4">
        <div className="w-7 h-7 flex items-center justify-center rounded-full bg-[var(--sutra-gold-glow,#fef3c7)] border border-[var(--sutra-muted-gold)] text-[var(--sutra-charcoal)]">
          <HelpCircle className="w-4 h-4 text-[var(--sutra-muted-gold)]" />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-[var(--sutra-charcoal)]">
            Before we build this — a few quick details
          </h3>
          <p className="text-[11px] text-[var(--text-2)]">
            Answer the questions below so we build exactly what you need.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {questions.map((q, idx) => {
          const selectedAnswer = answers[q.id] || '';
          const hasOptionMatch = q.options?.some((o) => o.label === selectedAnswer);

          return (
            <div
              key={q.id || idx}
              className="rounded-sm border border-[var(--border)] bg-[var(--bg-2)] p-4 transition-colors"
            >
              <div className="mb-2">
                <span className="inline-block text-[10px] font-bold uppercase tracking-wider text-[var(--sutra-muted-gold)] mr-2">
                  Question {idx + 1} of {questions.length}
                </span>
                <p className="text-sm font-medium text-[var(--sutra-charcoal)] mt-0.5">
                  {q.question}
                </p>
                {q.why && (
                  <p className="text-[11px] text-[var(--text-3)] mt-1 italic">
                    Why this matters: {q.why}
                  </p>
                )}
              </div>

              {/* Tappable options */}
              {q.options && q.options.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {q.options.map((opt) => {
                    const isSelected = selectedAnswer === opt.label;
                    return (
                      <button
                        key={opt.label}
                        type="button"
                        disabled={disabled || submitted}
                        onClick={() => handleSelectOption(q.id, opt.label)}
                        className={clsx(
                          'flex flex-col items-start px-3 py-2 rounded-sm text-left text-xs transition-all border select-none',
                          isSelected
                            ? 'bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)] border-[var(--sutra-charcoal)] shadow-sm'
                            : 'bg-[var(--bg)] text-[var(--sutra-charcoal)] border-[var(--border)] hover:border-[var(--sutra-muted-gold)] hover:bg-[var(--bg-2)]'
                        )}
                      >
                        <span className="font-semibold">{opt.label}</span>
                        {opt.description && (
                          <span
                            className={clsx(
                              'text-[10px] mt-0.5',
                              isSelected ? 'text-[var(--text-3,#cbd5e1)]' : 'text-[var(--text-2)]'
                            )}
                          >
                            {opt.description}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Free-form text input */}
              {q.allow_custom !== false && (
                <div className="mt-3">
                  <input
                    type="text"
                    disabled={disabled || submitted}
                    value={hasOptionMatch ? '' : selectedAnswer}
                    onChange={(e) => handleCustomInput(q.id, e.target.value)}
                    placeholder={
                      q.options && q.options.length > 0
                        ? 'Or type your own answer here...'
                        : 'Type your answer here...'
                    }
                    className="w-full text-xs px-3 py-2 bg-[var(--bg)] border border-[var(--border)] rounded-sm text-[var(--sutra-charcoal)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors"
                  />
                </div>
              )}
            </div>
          );
        })}

        {/* Submit action */}
        <div className="flex items-center justify-between pt-2">
          <div className="text-[11px] text-[var(--text-2)]">
            {answeredCount === 0 ? (
              <span>You can select options, type answers, or leave any blank for smart defaults.</span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-[var(--green,#16a34a)] font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {answeredCount} of {questions.length} answered
              </span>
            )}
          </div>
          <button
            type="submit"
            disabled={disabled || submitted}
            className="flex items-center gap-2 px-4 py-2.5 rounded-sm bg-[var(--sutra-charcoal)] hover:bg-black text-[var(--sutra-warm-ivory)] text-xs font-bold uppercase tracking-wider transition-colors disabled:opacity-50 shadow-sm"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{submitted ? 'Submitted' : 'Continue'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
