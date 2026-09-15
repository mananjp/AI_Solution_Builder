'use client';

import React from 'react';
import { Check } from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { RecommendedModule } from '@/types';

interface RecommendationCardProps {
  module: RecommendedModule;
  enabled: boolean;
  onToggle: () => void;
}

const categoryColors: Record<string, string> = {
  Core: 'bg-primary/10 text-primary border-primary/20',
  Integration: 'bg-chart-4/10 text-chart-4 border-chart-4/20',
  Data: 'bg-success/10 text-success border-success/20',
  UI: 'bg-chart-5/10 text-chart-5 border-chart-5/20',
  Auth: 'bg-destructive/10 text-destructive border-destructive/20',
  Infrastructure: 'bg-muted-foreground/10 text-muted-foreground border-muted-foreground/20',
};

const priorityLabels: Record<string, { label: string; variant: 'default' | 'secondary' | 'outline' }> = {
  must_have: { label: 'Must Have', variant: 'default' },
  should_have: { label: 'Should Have', variant: 'secondary' },
  nice_to_have: { label: 'Nice to Have', variant: 'outline' },
};

export default function RecommendationCard({ module, enabled, onToggle }: RecommendationCardProps) {
  const priority = priorityLabels[module.priority || 'must_have'] || priorityLabels.must_have;
  const colorClass = categoryColors[module.category || 'Infrastructure'] || categoryColors.Infrastructure;

  return (
    <div
      className={cn(
        'rounded-lg border p-3 transition-all cursor-pointer',
        enabled
          ? 'border-primary/30 bg-primary/5'
          : 'border-border bg-card opacity-60'
      )}
      onClick={onToggle}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[12px] font-semibold text-foreground truncate">
              {module.name}
            </span>
            <Badge variant={priority.variant} className="text-[9px] px-1.5 py-0 shrink-0">
              {priority.label}
            </Badge>
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed line-clamp-2 mb-2">
            {module.description}
          </p>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className={cn('text-[9px] px-1.5 py-0', colorClass)}>
              {module.category}
            </Badge>
            <span className="text-[10px] text-muted-foreground/60">
              {module.features?.length || 0} features
            </span>
          </div>
        </div>

        <Switch
          checked={enabled}
          onCheckedChange={onToggle}
          onClick={(e) => e.stopPropagation()}
          className="shrink-0 mt-1"
        />
      </div>

      {/* Feature preview */}
      {enabled && module.features && module.features.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border/50">
          <div className="flex flex-col gap-1">
            {module.features.slice(0, 3).map((feat, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <Check className="size-2.5 text-success shrink-0" weight="bold" />
                <span className="text-[10px] text-muted-foreground">{feat}</span>
              </div>
            ))}
            {module.features.length > 3 && (
              <span className="text-[10px] text-muted-foreground/50 ml-4">
                +{module.features.length - 3} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
