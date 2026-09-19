'use client';

import React from 'react';
import {
  FileText,
  Sparkles,
  Cpu,
  Layout,
  Database,
  CheckCircle2,
  Loader2,
  Compass
} from 'lucide-react';

interface AgentProgressTrackerProps {
  currentAgent: string | null;
  status: 'idle' | 'analyzing' | 'recommending' | 'generating' | 'complete' | 'failed';
}

export default function AgentProgressTracker({ currentAgent, status }: AgentProgressTrackerProps) {
  const steps = [
    {
      id: 'business_analyst',
      name: 'Business Analyst',
      desc: 'Domain analysis & extraction',
      icon: FileText,
    },
    {
      id: 'business_recommendation',
      name: 'Recommendation Engine',
      desc: 'Module matching',
      icon: Compass,
    },
    {
      id: 'solutions_architect',
      name: 'Solutions Architect',
      desc: 'System architecture HLD/LLD',
      icon: Cpu,
    },
    {
      id: 'ux_agent',
      name: 'UX Designer',
      desc: 'Wireframe specs',
      icon: Layout,
    },
    {
      id: 'database_api_agent',
      name: 'DB & API Engineer',
      desc: 'Postgres & OpenAPI specs',
      icon: Database,
    },
    {
      id: 'blueprint_generator',
      name: 'Synthesizer',
      desc: 'Delivery roadmap',
      icon: Sparkles,
    },
  ];

  const getStepState = (stepIndex: number, stepId: string) => {
    if (status === 'complete') return 'completed';
    if (status === 'idle') return 'pending';

    const agentOrder = [
      'business_analyst',
      'business_recommendation',
      'solutions_architect',
      'ux_agent',
      'database_api_agent',
      'blueprint_generator'
    ];
    const currentIndex = agentOrder.indexOf(currentAgent || '');

    if (currentAgent === stepId) return 'running';
    if (currentIndex > stepIndex) return 'completed';
    return 'pending';
  };

  return (
    <div className="sutra-card p-6">
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-[var(--border)]">
        <h4 className="text-sm font-semibold text-[var(--sutra-charcoal)] flex items-center gap-2 uppercase tracking-widest">
          <span className="w-1.5 h-1.5 bg-[var(--sutra-muted-gold)]"></span>
          Orchestration Timeline
        </h4>
        <span className="sutra-label text-[10px]">
          {status === 'complete' ? 'Synthesized' : status === 'idle' ? 'Ready' : 'Executing Swarm'}
        </span>
      </div>

      <div className="flex flex-col gap-0 relative">
        {/* Continuous timeline line */}
        <div className="absolute left-[19px] top-4 bottom-4 w-px bg-[var(--border)]"></div>
        
        {steps.map((step, idx) => {
          const state = getStepState(idx, step.id);
          const Icon = step.icon;
          const isLast = idx === steps.length - 1;

          return (
            <div key={step.id} className={`flex gap-6 relative ${isLast ? '' : 'pb-6'}`}>
              {/* Timeline Node */}
              <div className="relative z-10 flex flex-col items-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center transition-colors duration-500 border ${
                  state === 'running'
                    ? 'bg-[var(--bg)] border-[var(--sutra-muted-gold)] text-[var(--sutra-muted-gold)]'
                    : state === 'completed'
                    ? 'bg-[var(--sutra-soft-cream)] border-[var(--sutra-muted-gold)] text-[var(--sutra-deep-gold)]'
                    : 'bg-[var(--bg-2)] border-[var(--border)] text-[var(--text-3)]'
                }`}>
                  {state === 'completed' ? (
                    <CheckCircle2 className="w-4 h-4" />
                  ) : state === 'running' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Icon className="w-4 h-4 opacity-50" />
                  )}
                </div>
              </div>

              {/* Content */}
              <div className={`flex-1 pt-2 ${state === 'pending' ? 'opacity-50' : 'opacity-100'} transition-opacity duration-500`}>
                <h5 className="text-xs font-semibold text-[var(--sutra-charcoal)] tracking-wide uppercase">
                  {step.name}
                </h5>
                <p className="text-[13px] text-[var(--text-2)] mt-1 font-light">
                  {step.desc}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
