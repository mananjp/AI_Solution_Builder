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
      className={`relative p-4 rounded-xl border transition-colors cursor-pointer select-none text-left ${selected
          ? 'bg-[#161616] border-[#6366f1]'
          : 'bg-[#111] border-[#1a1a1a] hover:border-[#2e2e2e]'
        }`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2">
          <div className={`w-4 h-4 rounded flex items-center justify-center border transition-colors ${selected
              ? 'bg-[#6366f1] border-[#6366f1] text-white'
              : 'border-[#333] bg-[#0a0a0a] text-transparent'
            }`}>
            <Check className="w-3 h-3" />
          </div>
          <h3 className="font-medium text-xs text-white">{module.name}</h3>
        </div>

        {module.priority && (
          <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${module.priority === 'Must Have'
              ? 'badge-red'
              : module.priority === 'Should Have'
                ? 'badge-amber'
                : 'badge-green'
            }`}>
            {module.priority}
          </span>
        )}
      </div>

      <p className="text-xs text-[#555] mb-2 line-clamp-2 leading-relaxed">
        {module.description}
      </p>

      {module.features && module.features.length > 0 && (
        <div className="space-y-1 pt-2 border-t border-[#1a1a1a]">
          <span className="text-[10px] uppercase tracking-wider text-[#555] font-medium">Features</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {module.features.slice(0, 3).map((feat, idx) => (
              <span
                key={idx}
                className="text-[10px] px-1.5 py-0.5 rounded bg-[#0a0a0a] text-[#a1a1a1] border border-[#1a1a1a]"
              >
                {feat}
              </span>
            ))}
            {module.features.length > 3 && (
              <span className="text-[10px] px-1 py-0.5 rounded bg-[#0a0a0a] text-[#555]">
                +{module.features.length - 3}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
