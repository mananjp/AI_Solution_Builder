'use client';

import React from 'react';
import { Hammer, Edit3, AlertTriangle, CheckCircle, Sparkles } from 'lucide-react';
import MarkdownRenderer from '@/components/MarkdownRenderer';

interface PlanReviewCardProps {
  plainPlan: string;
  message?: string;
  changes?: string[];
  warnings?: string[];
  onApprove: () => void;
  onRefine: () => void;
  disabled?: boolean;
}

export function PlanReviewCard({
  plainPlan,
  message,
  changes,
  warnings,
  onApprove,
  onRefine,
  disabled = false,
}: PlanReviewCardProps) {
  return (
    <div className="my-6 rounded-md border-2 border-[var(--sutra-muted-gold)] bg-[var(--bg)] p-5 sm:p-6 shadow-md transition-all animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 pb-4 border-b border-[var(--border)] mb-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 flex items-center justify-center rounded-full bg-[var(--sutra-gold-glow,#fef3c7)] border border-[var(--sutra-muted-gold)] text-[var(--sutra-charcoal)] shrink-0">
            <Sparkles className="w-4 h-4 text-[var(--sutra-muted-gold)]" />
          </div>
          <div>
            <h3 className="text-base font-serif font-bold text-[var(--sutra-charcoal)]">
              {message || "Here's what I'm going to build for you"}
            </h3>
            <p className="text-[11px] text-[var(--text-2)]">
              Review the plan below. When you're ready, click build or let me know what to adjust.
            </p>
          </div>
        </div>
      </div>

      {/* Changes list if present */}
      {changes && changes.length > 0 && (
        <div className="mb-4 p-3.5 rounded-sm bg-emerald-500/10 border border-emerald-500/20 text-xs">
          <p className="font-semibold text-emerald-800 dark:text-emerald-300 flex items-center gap-1.5 mb-1.5">
            <CheckCircle className="w-4 h-4" />
            Changes made in this version:
          </p>
          <ul className="list-disc list-inside space-y-1 text-emerald-950 dark:text-emerald-200">
            {changes.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings if present */}
      {warnings && warnings.length > 0 && (
        <div className="mb-4 p-3.5 rounded-sm bg-amber-500/10 border border-amber-500/30 text-xs">
          <p className="font-semibold text-amber-800 dark:text-amber-300 flex items-center gap-1.5 mb-1.5">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            Important notes:
          </p>
          <ul className="list-disc list-inside space-y-1 text-amber-950 dark:text-amber-200">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Plain Plan Content */}
      <div className="text-[13px] text-[var(--sutra-charcoal)] leading-relaxed py-2 bg-[var(--bg-2)] rounded-sm p-4 border border-[var(--border)] overflow-x-auto max-h-[420px] overflow-y-auto">
        <MarkdownRenderer content={plainPlan} />
      </div>

      {/* Actions */}
      <div className="mt-5 pt-4 border-t border-[var(--border)] flex flex-wrap items-center justify-end gap-3">
        <button
          type="button"
          disabled={disabled}
          onClick={onRefine}
          className="flex items-center gap-2 px-4 py-2.5 rounded-sm border border-[var(--border)] bg-[var(--bg)] hover:bg-[var(--bg-2)] text-[var(--sutra-charcoal)] text-xs font-semibold uppercase tracking-wider transition-colors disabled:opacity-50"
        >
          <Edit3 className="w-3.5 h-3.5 text-[var(--text-2)]" />
          <span>I want to change something</span>
        </button>

        <button
          type="button"
          disabled={disabled}
          onClick={onApprove}
          className="flex items-center gap-2 px-5 py-2.5 rounded-sm bg-[var(--sutra-charcoal)] hover:bg-black text-[var(--sutra-warm-ivory)] text-xs font-bold uppercase tracking-wider transition-all disabled:opacity-50 shadow-md hover:shadow-lg"
        >
          <Hammer className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
          <span>Looks good — Build it!</span>
        </button>
      </div>
    </div>
  );
}
