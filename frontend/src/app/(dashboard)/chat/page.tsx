'use client';

import React, { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  PaperPlane,
  Paperclip,
  CircleNotch,
  ArrowRight,
  CheckCircle,
  Lightbulb,
  User,
  Robot,
  Storefront,
  Hospital,
  Truck,
  Code,
  Sparkle,
} from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import FileUploader from '@/components/FileUploader';
import RecommendationCard from '@/components/RecommendationCard';
import {
  authApi,
  workspaceApi,
  solutionApi,
  sendChatMessageStream,
  confirmRecommendationsStream,
} from '@/lib/api';
import { RecommendedModule } from '@/types';

const AGENT_STEPS = [
  { key: 'business_analyst', label: 'Business Analyst', icon: '📋' },
  { key: 'business_recommendation', label: 'Recommendations', icon: '💡' },
  { key: 'solutions_architect', label: 'Architecture', icon: '🏗️' },
  { key: 'ux_agent', label: 'UX Design', icon: '🎨' },
  { key: 'process_intelligence', label: 'Process Flows', icon: '⚙️' },
  { key: 'database_api_agent', label: 'Database & API', icon: '🗄️' },
  { key: 'code_synthesizer', label: 'Code Synthesis', icon: '💻' },
  { key: 'blueprint_generator', label: 'Blueprint', icon: '📊' },
];

const CATEGORY_GROUP_ORDER = ['Core', 'Integration', 'Data', 'UI', 'Auth'] as const;

const CATEGORY_COLORS: Record<string, string> = {
  Core: 'text-primary',
  Integration: 'text-chart-4',
  Data: 'text-success',
  UI: 'text-chart-5',
  Auth: 'text-destructive',
};

const TEMPLATES = [
  {
    title: 'Retail & Commerce',
    description: 'Omnichannel retail with POS, inventory, loyalty',
    prompt:
      'Design a full omnichannel retail platform with POS terminals, real-time inventory tracking, customer loyalty & rewards, and multi-warehouse management.',
    icon: Storefront,
  },
  {
    title: 'Healthcare EHR',
    description: 'Telemedicine with HIPAA, scheduling, video',
    prompt:
      'Design a HIPAA-compliant Electronic Health Records system with telemedicine video visits, patient scheduling, prescriptions, and insurance billing.',
    icon: Hospital,
  },
  {
    title: 'Logistics Dispatch',
    description: 'Freight with route planning, tracking, POD',
    prompt:
      'Design a freight logistics and dispatch platform with route optimization, real-time driver tracking, proof of delivery, and warehouse management.',
    icon: Truck,
  },
  {
    title: 'B2B SaaS Platform',
    description: 'Multi-tenant with billing, RBAC, audit',
    prompt:
      'Design a multi-tenant B2B SaaS platform with subscription billing, role-based access control, audit logging, and tenant isolation.',
    icon: Code,
  },
];

function AgentProgressTracker({
  currentAgent,
  pipelineStatus,
  agentMessage,
}: {
  currentAgent: string | null;
  pipelineStatus: string;
  agentMessage?: string;
}) {
  const activeStepIndex = currentAgent
    ? AGENT_STEPS.findIndex((s) => s.key === currentAgent)
    : -1;

  const progressPercent =
    pipelineStatus === 'complete'
      ? 100
      : pipelineStatus === 'idle'
        ? 0
        : activeStepIndex >= 0
          ? Math.round(((activeStepIndex + 1) / AGENT_STEPS.length) * 100)
          : 0;

  if (pipelineStatus === 'idle') return null;

  const activeStep = activeStepIndex >= 0 ? AGENT_STEPS[activeStepIndex] : null;

  return (
    <div className="flex flex-col gap-3 p-3 bg-card border border-border rounded-lg">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CircleNotch
            className={cn(
              'size-3.5',
              pipelineStatus === 'complete' ? 'text-success' : 'animate-spin text-primary'
            )}
          />
          <span className="text-xs font-medium text-foreground">
            {pipelineStatus === 'complete'
              ? 'Pipeline Complete'
              : activeStep
                ? `${activeStep.icon} ${activeStep.label}`
                : 'Processing Agents'}
          </span>
        </div>
        <span className="text-xs text-muted-foreground tabular-nums">{progressPercent}%</span>
      </div>
      <Progress value={progressPercent} />
      {agentMessage && pipelineStatus !== 'complete' && (
        <div className="text-[11px] text-muted-foreground italic truncate">{agentMessage}</div>
      )}
      <div className="flex items-center gap-1 overflow-x-auto pb-1">
        {AGENT_STEPS.map((step, idx) => {
          const isActive = step.key === currentAgent;
          const isDone =
            pipelineStatus === 'complete' ||
            (activeStepIndex >= 0 && idx < activeStepIndex);

          return (
            <div
              key={step.key}
              className={cn(
                'flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-medium whitespace-nowrap shrink-0 transition-colors',
                isActive && 'bg-primary/10 text-primary',
                isDone && !isActive && 'text-success',
                !isActive && !isDone && 'text-muted-foreground'
              )}
            >
              {isDone && !isActive ? (
                <CheckCircle className="size-2.5" />
              ) : isActive ? (
                <CircleNotch className="size-2.5 animate-spin" />
              ) : (
                <span className="size-2.5 flex items-center justify-center rounded-full bg-current text-background text-[8px] font-bold">
                  {idx + 1}
                </span>
              )}
              <span className="truncate max-w-[90px]">{step.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function WelcomeScreen({ onSelectTemplate }: { onSelectTemplate: (prompt: string) => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4 py-12">
      <div className="flex flex-col items-center gap-2 mb-8">
        <div className="flex size-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Sparkle className="size-6" />
        </div>
        <h1 className="text-xl font-semibold text-foreground">AI Solution Architect</h1>
        <p className="text-sm text-muted-foreground text-center max-w-md">
          Describe your system and I will analyze the domain, recommend subsystem modules, and
          generate production-grade architecture blueprints.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 w-full max-w-lg mb-8">
        {TEMPLATES.map((tpl) => {
          const Icon = tpl.icon;
          return (
            <button
              key={tpl.title}
              onClick={() => onSelectTemplate(tpl.prompt)}
              className="flex flex-col gap-2 p-4 rounded-lg border border-border bg-card text-left transition-colors hover:bg-accent/50 hover:border-primary/30 cursor-pointer group"
            >
              <div className="flex items-center gap-2">
                <div className="flex size-8 items-center justify-center rounded-md bg-secondary text-secondary-foreground group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                  <Icon className="size-4" />
                </div>
                <span className="text-sm font-medium text-foreground leading-tight">
                  {tpl.title}
                </span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{tpl.description}</p>
            </button>
          );
        })}
      </div>

      <p className="text-xs text-muted-foreground/60">Or describe your system in plain language</p>
    </div>
  );
}

function ChatContent() {
  const searchParams = useSearchParams();
  const initialPrompt = searchParams.get('prompt') || '';

  const [inputMessage, setInputMessage] = useState(initialPrompt);
  const [messages, setMessages] = useState<
    Array<{ role: 'user' | 'assistant' | 'system'; content: string; agent?: string }>
  >([]);
  const [hasStarted, setHasStarted] = useState(false);

  const [solutionId, setSolutionId] = useState<string | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const [uploadedContext, setUploadedContext] = useState('');
  const [uploadedFilename, setUploadedFilename] = useState('');
  const [showUploader, setShowUploader] = useState(false);

  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [agentMessage, setAgentMessage] = useState<string>('');
  const [pipelineStatus, setPipelineStatus] = useState<
    'idle' | 'analyzing' | 'recommending' | 'generating' | 'complete' | 'failed'
  >('idle');
  const [isStreaming, setIsStreaming] = useState(false);

  const [recommendations, setRecommendations] = useState<RecommendedModule[]>([]);
  const [selectedModules, setSelectedModules] = useState<string[]>([]);
  const [initError, setInitError] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, recommendations, pipelineStatus]);

  useEffect(() => {
    if (initialPrompt) {
      setHasStarted(true);
    }
  }, [initialPrompt]);

  // Auto-send initial prompt once session is ready
  const initialPromptSent = useRef(false);
  useEffect(() => {
    if (initialPrompt && sessionReady && solutionId && !initialPromptSent.current) {
      initialPromptSent.current = true;
      // Small delay to let the UI render first
      setTimeout(() => handleSendMessage(initialPrompt), 300);
    }
  }, [initialPrompt, sessionReady, solutionId]);

  useEffect(() => {
    async function initSession() {
      try {
        const { getAuthToken } = await import('@/lib/api');
        if (!getAuthToken() && process.env.NODE_ENV === 'development') {
          try {
            const demo = await authApi.login({
              email: 'demo@aibuilder.example',
              password: 'DemoPass123!',
            });
            if (demo?.access_token) {
              setInitError(null);
            }
          } catch {
            // keep the user on the page and surface a friendly message below
          }
        }
        if (!getAuthToken()) {
          setInitError('Please log in to use the AI chat.');
          return;
        }
        const wsList = await workspaceApi.list();
        let ws = wsList && wsList[0];
        if (!ws) {
          ws = await workspaceApi.create({ name: 'Architecture Workspace' });
        }
        const existing = await solutionApi.list(ws.id);
        const draft = existing.find((s) => s.status === 'discovery' || s.status === 'recommending');
        if (draft) {
          setSolutionId(draft.id);
        } else {
          const existing = await solutionApi.list(ws.id);
          const draft = existing.find((s) => s.status === 'discovery' || s.status === 'recommending');
          if (draft) {
            setSolutionId(draft.id);
          } else {
            const sol = await solutionApi.create({
              workspace_id: ws.id,
              title: 'Solution Design Session',
              description: 'Interactive session with AI Solution Builder swarm',
            });
            setSolutionId(sol.id);
          }
        }
        setSessionReady(true);
      } catch (err: any) {
        console.error('Chat session init failed:', err);
        const msg = err?.message || err?.detail || 'Failed to initialize chat session.';
        if (msg.includes('401') || msg.toLowerCase().includes('unauthorized')) {
          setInitError('Please log in to use the AI chat.');
        } else {
          setInitError(msg);
        }
      }
    }
    initSession();
  }, []);

  const handleSendMessage = async (textOverride?: string) => {
    const text = textOverride || inputMessage;
    if (!text.trim() || isStreaming) return;

    if (!hasStarted) setHasStarted(true);

    setInputMessage('');
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setIsStreaming(true);
    setPipelineStatus('analyzing');
    setCurrentAgent('business_analyst');

    try {
      if (!solutionId) {
        setMessages((prev) => [
          ...prev,
          { role: 'system', content: 'Session is still loading. Please wait a moment and try again.' },
        ]);
        setIsStreaming(false);
        setPipelineStatus('idle');
        return;
      }
      await sendChatMessageStream(
        {
          solution_id: solutionId,
          message: text,
          uploaded_context: uploadedContext,
        },
        {
          onEvent: (_event, data) => {
            if (data.agent) setCurrentAgent(data.agent);
            if (data.message) setAgentMessage(data.message);
            if (data.type === 'agent_start') {
              setMessages((prev) => [
                ...prev,
                {
                  role: 'assistant',
                  agent: data.agent || 'Pipeline',
                  content: data.message || `Starting ${data.agent}...`,
                },
              ]);
            }
          },
          onComplete: (data) => {
            const streamStatus = data.status as 'complete' | 'recommending' | undefined;
            setPipelineStatus(streamStatus || 'complete');
            setAgentMessage('');
            setCurrentAgent(null);
            if (data.status === 'recommending' && data.recommendations) {
              const recs: RecommendedModule[] = data.recommendations.map((r) => {
                if (typeof r === 'string') {
                  return {
                    name: r,
                    description: `Automated ${r} subsystem module.`,
                    features: ['Standard CRUD', 'API Endpoints', 'Postgres Models'],
                  };
                }
                return r;
              });
              setRecommendations(recs);
              setSelectedModules(recs.map((r) => r.name));
            }
            if (data.message) {
              setMessages((prev) => [
                ...prev,
                { role: 'assistant', agent: 'AI Architect', content: data.message! },
              ]);
            }
            setIsStreaming(false);
          },
          onError: (err) => {
            console.error('Chat stream error', err);
            const errMsg = (err as any)?.message
              || (err as any)?.detail
              || (typeof err === 'string' ? err : JSON.stringify(err))
              || 'An error occurred while processing your request.';
            setMessages((prev) => [
              ...prev,
              { role: 'system', content: `Error: ${errMsg}` },
            ]);
            setPipelineStatus('failed');
            setIsStreaming(false);
          },
        }
      );
    } catch (err: any) {
      console.error('Chat send error', err);
      const errMsg = err?.message || 'Failed to send message.';
      setMessages((prev) => [
        ...prev,
        { role: 'system', content: `Error: ${errMsg}` },
      ]);
      setPipelineStatus('failed');
      setIsStreaming(false);
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSendMessage();
  };



  const handleToggleModule = (name: string) => {
    setSelectedModules((prev) =>
      prev.includes(name) ? prev.filter((m) => m !== name) : [...prev, name]
    );
  };

  const handleConfirmRecommendations = async () => {
    if (selectedModules.length === 0 || isStreaming || !solutionId) return;

    setIsStreaming(true);
    setPipelineStatus('generating');
    setCurrentAgent('solutions_architect');

    try {
      await confirmRecommendationsStream(
        {
          solution_id: solutionId,
          accepted_modules: selectedModules,
        },
        {
          onEvent: (_event, data) => {
            if (data.agent) setCurrentAgent(data.agent);
            if (data.message) setAgentMessage(data.message);
          },
          onComplete: () => {
            setPipelineStatus('complete');
            setAgentMessage('');
            setCurrentAgent(null);
            setIsStreaming(false);
            setMessages((prev) => [
              ...prev,
              {
                role: 'assistant',
                agent: 'Blueprint Synthesizer',
                content:
                  'All solution blueprints, architecture diagrams, PostgreSQL schemas, and delivery roadmaps have been successfully synthesized! Click the button below to inspect your complete engineering specification.',
              },
            ]);
          },
          onError: (err) => {
            console.error('Recommendation confirmation error', err);
            setPipelineStatus('failed');
            setIsStreaming(false);
          },
        }
      );
    } catch (err) {
      console.error('Recommendation confirmation error', err);
      setPipelineStatus('failed');
      setIsStreaming(false);
    }
  };



  const groupedRecommendations = CATEGORY_GROUP_ORDER.reduce(
    (acc, category) => {
      const matching = recommendations.filter(
        (r) => r.category && r.category.toLowerCase().includes(category.toLowerCase())
      );
      if (matching.length > 0) {
        acc.push({ category, modules: matching });
      }
      return acc;
    },
    [] as Array<{ category: string; modules: RecommendedModule[] }>
  );

  const uncategorizedModules = recommendations.filter(
    (r) =>
      !r.category ||
      !CATEGORY_GROUP_ORDER.some((cat) =>
        r.category!.toLowerCase().includes(cat.toLowerCase())
      )
  );
  if (uncategorizedModules.length > 0) {
    groupedRecommendations.push({ category: 'Other', modules: uncategorizedModules });
  }

  if (!hasStarted) {
    return (
      <div className="flex h-[calc(100vh-2.75rem)] flex-col items-center justify-center max-w-3xl mx-auto px-4">
        {initError && (
          <div className="w-full max-w-lg mb-6 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive text-center">
            {initError}
          </div>
        )}
        <WelcomeScreen onSelectTemplate={(prompt) => handleSendMessage(prompt)} />
        <div className="w-full max-w-lg pb-8">
          <div className="flex flex-col gap-3">
            {showUploader && (
              <FileUploader
                onParsedContext={(text, filename) => {
                  setUploadedContext(text);
                  setUploadedFilename(filename);
                  setShowUploader(false);
                }}
                onClear={() => {
                  setUploadedContext('');
                  setUploadedFilename('');
                }}
              />
            )}
            <form onSubmit={handleFormSubmit} className="flex items-end gap-2">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => setShowUploader(!showUploader)}
                className={cn(
                  'shrink-0',
                  uploadedContext && 'bg-accent text-accent-foreground'
                )}
                title="Attach document"
              >
                <Paperclip className="size-4" />
              </Button>
              <Textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                placeholder={
                  uploadedFilename
                    ? `Using context from ${uploadedFilename}. Describe your system...`
                    : 'Describe what system or business you want to build...'
                }
                disabled={isStreaming}
                className="min-h-[44px] max-h-32 resize-none"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
              />
              <Button
                type="submit"
                size="icon"
                disabled={!inputMessage.trim() || isStreaming || !sessionReady}
                className="shrink-0"
              >
                {isStreaming ? (
                  <CircleNotch className="size-4 animate-spin" />
                ) : (
                  <PaperPlane className="size-4" />
                )}
              </Button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-2.75rem)] max-w-[768px] mx-auto flex-col">
      <div className="flex-1 flex flex-col min-h-0">
        {/* Agent Progress Tracker - horizontal bar at top */}
        <div className="shrink-0 pb-3">
           <AgentProgressTracker currentAgent={currentAgent} pipelineStatus={pipelineStatus} agentMessage={agentMessage} />
        </div>

        {/* Messages */}
        <div className="flex-1 min-h-0">
          <ScrollArea className="h-full">
            <div className="flex flex-col gap-4 py-4">
              {messages.map((msg, index) => (
                <div key={index} className={cn(
                  'flex items-start gap-3 px-1',
                  msg.role === 'system' && 'justify-center'
                )}>
                  {msg.role === 'system' ? (
                    <div className="rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-xs text-destructive max-w-md text-center">
                      {msg.content}
                    </div>
                  ) : (
                  <>
                  <Avatar size="default">
                    <AvatarFallback
                      className={cn(
                        msg.role === 'user'
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-secondary text-secondary-foreground'
                      )}
                    >
                      {msg.role === 'user' ? (
                        <User className="size-4" />
                      ) : (
                        <Robot className="size-4" />
                      )}
                    </AvatarFallback>
                  </Avatar>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge variant={msg.role === 'user' ? 'default' : 'secondary'} className="text-xs">
                        {msg.role === 'user' ? 'You' : 'AI Architect'}
                      </Badge>
                      {msg.agent && msg.role === 'assistant' && (
                        <span className="text-[10px] text-muted-foreground">{msg.agent}</span>
                      )}
                    </div>
                    <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                      {msg.content}
                    </p>
                  </div>
                  </>
                  )}
                </div>
              ))}

              {/* Recommendations inline */}
              {pipelineStatus === 'recommending' && recommendations.length > 0 && (
                <div className="flex flex-col gap-4 px-1">
                  {groupedRecommendations.map((group) => (
                    <div key={group.category} className="flex flex-col gap-2">
                      <div className="flex items-center gap-2">
                        <Separator className="flex-1" />
                        <span
                          className={cn(
                            'text-[10px] font-semibold uppercase tracking-wider',
                            CATEGORY_COLORS[group.category] || 'text-muted-foreground'
                          )}
                        >
                          {group.category}
                        </span>
                        <Separator className="flex-1" />
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {group.modules.map((mod, idx) => (
                          <RecommendationCard
                            key={idx}
                            module={mod}
                            enabled={selectedModules.includes(mod.name)}
                            onToggle={() => handleToggleModule(mod.name)}
                          />
                        ))}
                      </div>
                    </div>
                  ))}

                  <div className="flex items-center justify-between pt-2">
                    <Badge variant="outline" className="text-xs">
                      {selectedModules.length} of {recommendations.length} selected
                    </Badge>
                    <Button
                      onClick={handleConfirmRecommendations}
                      disabled={selectedModules.length === 0 || isStreaming}
                    >
                      <Lightbulb className="size-4" />
                      <span>Confirm Modules & Generate</span>
                    </Button>
                  </div>
                </div>
              )}

              {/* Completion banner */}
              {pipelineStatus === 'complete' && (
                <div className="px-1">
                  <div className="flex items-center justify-between gap-4 p-4 rounded-lg border border-success/30 bg-success/5 animate-in slide-in-from-bottom-2 fade-in duration-500">
                    <div className="flex items-center gap-3">
                      <div className="flex size-10 items-center justify-center rounded-lg bg-success/10 text-success">
                        <CheckCircle className="size-6" />
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-foreground">Blueprint Ready</h4>
                        <p className="text-xs text-muted-foreground">
                          HLD, LLD, wireframes, schemas, and roadmap are compiled.
                        </p>
                      </div>
                    </div>
                    <Button
                      size="sm"
                      nativeButton={false}
                      render={
                        <Link
                          href={`/solution/${solutionId}`}
                          className="flex items-center gap-1.5"
                        />
                      }
                    >
                      View Blueprint
                      <ArrowRight className="size-3.5" />
                    </Button>
                  </div>
                </div>
              )}

              {/* Streaming indicator */}
              {isStreaming && pipelineStatus !== 'recommending' && pipelineStatus !== 'complete' && (
                <div className="flex items-center gap-3 px-1">
                  <Avatar size="default">
                    <AvatarFallback className="bg-accent text-accent-foreground">
                      <Robot className="size-4" />
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-accent text-accent-foreground">
                    <CircleNotch className="size-3.5 animate-spin" />
                    <span className="text-xs font-medium">
                      {AGENT_STEPS.find((s) => s.key === currentAgent)?.label || currentAgent || 'Swarm'} is working...
                    </span>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>
          </ScrollArea>
        </div>
      </div>

      {/* Input area */}
      <div className="shrink-0 pt-3 pb-4 flex flex-col gap-2 border-t border-border">
        {showUploader && (
          <div className="pb-2">
            <FileUploader
              onParsedContext={(text, filename) => {
                setUploadedContext(text);
                setUploadedFilename(filename);
                setShowUploader(false);
                setMessages((prev) => [
                  ...prev,
                  {
                    role: 'assistant',
                    agent: 'Document Ingestion',
                    content: `Extracted content from **${filename}** (${text.length} characters). You can now ask questions about this document or generate an architecture based on it.`,
                  },
                ]);
              }}
              onClear={() => {
                setUploadedContext('');
                setUploadedFilename('');
              }}
            />
          </div>
        )}

        <div className="flex items-end gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => setShowUploader(!showUploader)}
            className={cn(
              'shrink-0',
              uploadedContext && 'bg-accent text-accent-foreground'
            )}
            title="Attach PRD or specification document"
          >
            <Paperclip className="size-4" />
          </Button>

          <form onSubmit={handleFormSubmit} className="flex-1 flex items-end gap-2">
            <Textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder={
                uploadedFilename
                  ? `Ask or generate architecture using context from ${uploadedFilename}...`
                  : 'Describe what system or business you want to build...'
              }
              disabled={isStreaming}
              className="min-h-[44px] max-h-32 resize-none"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
            />
            <Button
              type="submit"
              size="icon"
              disabled={!inputMessage.trim() || isStreaming || !sessionReady}
              className="shrink-0"
            >
              {isStreaming ? (
                <CircleNotch className="size-4 animate-spin" />
              ) : (
                <PaperPlane className="size-4" />
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-[calc(100vh-2.75rem)] text-muted-foreground text-sm">
          Loading AI Architect Studio...
        </div>
      }
    >
      <ChatContent />
    </Suspense>
  );
}
