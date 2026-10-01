'use client';

import React from 'react';
import { Check } from 'lucide-react';
import { RecommendedModule } from '@/types';

interface RecommendationCardProps {
  module: RecommendedModule;
  selected: boolean;
  onToggle: () => void;
}

export default function RecommendationCard({ module, selected, onToggle }: RecommendationCardProps) {
  return (
    <div
      onClick={onToggle}
      className={`relative p-4 rounded-sm border transition-colors cursor-pointer select-none text-left ${selected
          ? 'bg-[var(--sutra-muted-gold)]/10 border-[var(--sutra-muted-gold)] ring-1 ring-[var(--sutra-muted-gold)]/40 shadow-xs'
          : 'bg-[var(--bg-2)] border-[var(--border)] hover:border-[var(--sutra-muted-gold)]/40 hover:bg-[var(--bg-3)]'
        }`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <div className={`w-4 h-4 rounded-xs flex items-center justify-center border transition-colors ${selected
              ? 'bg-[var(--sutra-muted-gold)] border-[var(--sutra-muted-gold)] text-[var(--sutra-warm-ivory)]'
              : 'border-[var(--border)] bg-[var(--bg-3)] text-transparent'
            }`}>
            <Check className="w-3 h-3" />
          </div>
          <h3 className="font-medium text-xs text-[var(--sutra-charcoal)]">{module.name}</h3>
        </div>

        {module.priority && (
          <span className={`text-[10px] px-2 py-0.5 rounded-sm font-medium ${module.priority === 'Must Have'
              ? 'badge-red'
              : module.priority === 'Should Have'
                ? 'badge-amber'
                : 'badge-green'
            }`}>
            {module.priority}
          </span>
        )}
      </div>

      <p className="text-xs text-[var(--text-2)] mb-2 line-clamp-2 leading-relaxed font-light">
        {module.description}
      </p>

      {module.features && module.features.length > 0 && (
        <div className="space-y-1 pt-2 border-t border-[var(--border)]">
          <span className="text-[10px] uppercase tracking-wider text-[var(--text-3)] font-medium">Features</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {module.features.slice(0, 3).map((feat, idx) => (
              <span
                key={idx}
                className="text-[10px] px-1.5 py-0.5 rounded-xs bg-[var(--bg-3)] text-[var(--text-2)] border border-[var(--border)]"
              >
                {feat}
              </span>
            ))}
            {module.features.length > 3 && (
              <span className="text-[10px] px-1 py-0.5 rounded-xs bg-[var(--bg-3)] text-[var(--text-3)]">
                +{module.features.length - 3}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
