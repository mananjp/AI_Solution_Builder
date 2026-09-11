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
      className={`relative p-4 rounded-xl border transition-all cursor-pointer select-none text-left ${
        selected
          ? 'bg-indigo-950/40 border-indigo-500/60 shadow-lg shadow-indigo-500/10'
          : 'bg-slate-900/40 border-white/5 hover:border-white/20 hover:bg-slate-900/60'
      }`}
    >
      {/* Checkbox indicator */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <div className={`w-5 h-5 rounded-md flex items-center justify-center border transition-colors ${
            selected
              ? 'bg-indigo-600 border-indigo-500 text-white'
              : 'border-white/20 bg-white/5 text-transparent'
          }`}>
            <Check className="w-3.5 h-3.5" />
          </div>
          <h4 className="font-semibold text-sm text-slate-100">{module.name}</h4>
        </div>

        {module.priority && (
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
            module.priority === 'Must Have'
              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
              : module.priority === 'Should Have'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
          }`}>
            {module.priority}
          </span>
        )}
      </div>

      <p className="text-xs text-slate-400 mb-3 line-clamp-2 leading-relaxed">
        {module.description}
      </p>

      {/* Feature list preview */}
      {module.features && module.features.length > 0 && (
        <div className="space-y-1 pt-2 border-t border-white/5">
          <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Included Features</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {module.features.slice(0, 3).map((feat, idx) => (
              <span
                key={idx}
                className="text-[10px] px-2 py-0.5 rounded-md bg-white/5 text-slate-300 border border-white/5"
              >
                {feat}
              </span>
            ))}
            {module.features.length > 3 && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-white/5 text-slate-500">
                +{module.features.length - 3} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
