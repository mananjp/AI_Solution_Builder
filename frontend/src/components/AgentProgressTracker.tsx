'use client';

import React from 'react';
import {
  FileText,
  Compass,
  Cpu,
  Layout,
  Database,
  Lightbulb,
  Check,
  Spinner,
} from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/utils';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';

const agents = [
  { key: 'business_analyst', label: 'Business Analyst', sublabel: 'Domain & scope', icon: FileText },
  { key: 'business_recommendation', label: 'Recommender', sublabel: 'Module selection', icon: Compass },
  { key: 'solutions_architect', label: 'Architect', sublabel: 'System design', icon: Cpu },
  { key: 'ux_agent', label: 'UX Designer', sublabel: 'Wireframes & flow', icon: Layout },
  { key: 'database_api_agent', label: 'Data Engineer', sublabel: 'Schema & API', icon: Database },
  { key: 'blueprint_generator', label: 'Blueprint', sublabel: 'Final synthesis', icon: Lightbulb },
];

interface AgentProgressTrackerProps {
  currentAgent: string | null;
  completedAgents: string[];
  status: string;
  progressPercent?: number;
}

export default function AgentProgressTracker({
  currentAgent,
  completedAgents,
  status,
  progressPercent,
}: AgentProgressTrackerProps) {
  const isRunning = status === 'analyzing' || status === 'generating';
  const overallProgress = progressPercent ?? Math.round((completedAgents.length / agents.length) * 100);

  return (
    <div className="flex flex-col gap-4">
      {/* Overall progress bar */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium text-muted-foreground">
            {isRunning ? 'Pipeline running...' : completedAgents.length === agents.length ? 'Complete' : 'Waiting to start'}
          </span>
          <span className="text-[11px] font-mono text-muted-foreground">
            {completedAgents.length}/{agents.length}
          </span>
        </div>
        <Progress value={overallProgress} className="h-1.5" />
      </div>

      {/* Agent timeline */}
      <div className="flex flex-col gap-0.5">
        {agents.map((agent, i) => {
          const Icon = agent.icon;
          const isCompleted = completedAgents.includes(agent.key);
          const isCurrent = currentAgent === agent.key;
          const isPending = !isCompleted && !isCurrent;

          return (
            <div
              key={agent.key}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md transition-colors',
                isCurrent && 'bg-primary/10',
                isCompleted && 'opacity-70'
              )}
            >
              {/* Icon */}
              <div
                className={cn(
                  'size-7 rounded-md flex items-center justify-center shrink-0 transition-colors',
                  isCompleted && 'bg-success/15 text-success',
                  isCurrent && 'bg-primary/15 text-primary',
                  isPending && 'bg-secondary text-muted-foreground'
                )}
              >
                {isCompleted ? (
                  <Check className="size-3.5" weight="bold" />
                ) : isCurrent ? (
                  <Spinner className="size-3.5 animate-spin" weight="bold" />
                ) : (
                  <Icon className="size-3.5" weight="light" />
                )}
              </div>

              {/* Label */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      'text-[11px] font-medium truncate',
                      isCurrent && 'text-primary',
                      isCompleted && 'text-foreground',
                      isPending && 'text-muted-foreground'
                    )}
                  >
                    {agent.label}
                  </span>
                  {isCurrent && (
                    <Badge variant="secondary" className="text-[9px] px-1.5 py-0 animate-pulse">
                      running
                    </Badge>
                  )}
                </div>
                <span className="text-[10px] text-muted-foreground/70">{agent.sublabel}</span>
              </div>

              {/* Step number */}
              <span className="text-[10px] font-mono text-muted-foreground/50 shrink-0">
                {String(i + 1).padStart(2, '0')}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
