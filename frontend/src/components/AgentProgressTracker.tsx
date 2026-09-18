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
    <div className="p-4 rounded-xl bg-[#111] border border-[#1a1a1a]">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-semibold text-white flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-[#6366f1]" />
          <span>Multi-Agent Swarm Pipeline</span>
        </h4>
        <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${status === 'complete'
            ? 'badge-green'
            : status === 'generating' || status === 'analyzing'
              ? 'badge-blue animate-pulse'
              : 'badge-gray'
          }`}>
          {status === 'complete' ? 'Synthesized' : status === 'idle' ? 'Ready' : 'Executing Swarm'}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        {steps.map((step, idx) => {
          const state = getStepState(idx, step.id);
          const Icon = step.icon;

          return (
            <div
              key={step.id}
              className={`p-3 rounded-lg border transition-colors text-left flex flex-col justify-between min-h-[85px] ${state === 'running'
                  ? 'bg-[#161616] border-[#6366f1]'
                  : state === 'completed'
                    ? 'bg-[#0a0a0a] border-[#22c55e40]'
                    : 'bg-[#0a0a0a] border-[#1a1a1a] opacity-50'
                }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <div className={`p-1 rounded ${state === 'running'
                    ? 'text-[#818cf8]'
                    : state === 'completed'
                      ? 'text-[#4ade80]'
                      : 'text-[#555]'
                  }`}>
                  <Icon className="w-3.5 h-3.5" />
                </div>
                {state === 'running' && (
                  <Loader2 className="w-3.5 h-3.5 text-[#818cf8] animate-spin" />
                )}
                {state === 'completed' && (
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#4ade80]" />
                )}
              </div>

              <div>
                <p className={`text-[11px] font-medium leading-tight ${state === 'running' ? 'text-white font-semibold' : state === 'completed' ? 'text-[#a1a1a1]' : 'text-[#555]'
                  }`}>
                  {step.name}
                </p>
                <p className="text-[10px] text-[#555] leading-tight mt-0.5 line-clamp-1">
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
