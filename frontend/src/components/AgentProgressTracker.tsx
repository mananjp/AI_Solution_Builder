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
      desc: 'Domain analysis & requirements extraction',
      icon: FileText,
    },
    {
      id: 'business_recommendation',
      name: 'Recommendation Engine',
      desc: 'Industry catalog & core module matching',
      icon: Compass,
    },
    {
      id: 'solutions_architect',
      name: 'Solutions Architect',
      desc: 'System architecture (HLD / LLD)',
      icon: Cpu,
    },
    {
      id: 'ux_agent',
      name: 'UX Designer',
      desc: 'Wireframes & interface hierarchies',
      icon: Layout,
    },
    {
      id: 'database_api_agent',
      name: 'Database & API Engineer',
      desc: 'Postgres schemas & OpenAPI endpoints',
      icon: Database,
    },
    {
      id: 'blueprint_generator',
      name: 'Blueprint Synthesizer',
      desc: 'Milestones & delivery roadmap',
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
    <div className="p-4 rounded-2xl bg-slate-900/50 border border-white/5 backdrop-blur-md">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
          <span>Multi-Agent Swarm Pipeline</span>
        </h4>
        <span className={`text-[11px] px-2.5 py-0.5 rounded-full font-medium ${
          status === 'complete'
            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
            : status === 'generating' || status === 'analyzing'
            ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 animate-pulse'
            : 'bg-slate-800 text-slate-400'
        }`}>
          {status === 'complete' ? 'Synthesized' : status === 'idle' ? 'Ready' : 'Executing Swarm'}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5">
        {steps.map((step, idx) => {
          const state = getStepState(idx, step.id);
          const Icon = step.icon;

          return (
            <div
              key={step.id}
              className={`p-3 rounded-xl border transition-all text-left flex flex-col justify-between min-h-[90px] ${
                state === 'running'
                  ? 'bg-indigo-950/40 border-indigo-500/50 shadow-lg shadow-indigo-500/10'
                  : state === 'completed'
                  ? 'bg-slate-800/40 border-emerald-500/30'
                  : 'bg-white/[0.02] border-white/5 opacity-60'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className={`p-1.5 rounded-lg ${
                  state === 'running'
                    ? 'bg-indigo-500/20 text-indigo-400'
                    : state === 'completed'
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'bg-white/5 text-slate-400'
                }`}>
                  <Icon className="w-3.5 h-3.5" />
                </div>
                {state === 'running' && (
                  <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
                )}
                {state === 'completed' && (
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                )}
              </div>

              <div>
                <p className={`text-xs font-semibold leading-tight ${
                  state === 'running' ? 'text-indigo-300' : state === 'completed' ? 'text-slate-200' : 'text-slate-400'
                }`}>
                  {step.name}
                </p>
                <p className="text-[10px] text-slate-500 leading-tight mt-1 line-clamp-1">
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
