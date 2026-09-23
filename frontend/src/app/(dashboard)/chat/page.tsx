'use client';

import React, { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  Send,
  Paperclip,
  Loader2,
  CheckCircle2,
  Circle,
  FileText,
  Layout,
  Layers,
  Settings2,
  Play,
  Clock,
  Terminal,
  Activity,
} from 'lucide-react';
import ChatMessage from '@/components/ChatMessage';
import FileUploader from '@/components/FileUploader';
import { opencodeApi, sendOpenCodeChatStream, mvpApi } from '@/lib/api';
import { MVPBuild, MVPDeployResult, OpenCodeChatComplete, OpenCodeBuildProgress } from '@/types';
import { BuildCard, ConfigureModal, DeployModal } from '@/components/mvp/BuildCard';

type Msg = { role: 'user' | 'assistant' | 'system'; content: string; agent?: string };

interface BuildProgressState {
  phase: string;
  step: number;
  total_steps: number;
  percentage: number;
  message: string;
  logs: string[];
  startedAt: number;
}

const BUILD_MILESTONES = [
  { step: 1, label: 'Domain Architecture & Specs', phase: 'analyzing' },
  { step: 2, label: 'Database & API Schema Registry', phase: 'persisting' },
  { step: 3, label: 'Full-Stack Codebase Scaffold', phase: 'scaffolding' },
  { step: 4, label: 'Domain Models & REST Routers', phase: 'coding' },
  { step: 5, label: 'Interactive UI Studios & Playground', phase: 'frontend' },
  { step: 6, label: 'Codebase Integrity Verification', phase: 'verifying' },
  { step: 7, label: 'Production Package Archive (.zip)', phase: 'packaging' },
];

function ChatContent() {
  const searchParams = useSearchParams();
  const initialPrompt = searchParams.get('prompt') || '';
  const initialSolutionId = searchParams.get('solution_id') || null;

  const [input, setInput] = useState(initialPrompt);
  const [appName, setAppName] = useState(searchParams.get('app_name') || '');
  const [messages, setMessages] = useState<Msg[]>([{
    role: 'assistant',
    agent: 'SUTRA Orchestrator',
    content: "I am SUTRA, your intelligence architect. Describe your application requirements, and I will synthesize a complete FastAPI + Next.js solution. Provide a PRD or spec for enhanced context, and select **Build** to finalize the architecture.",
  }]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [solutionId, setSolutionId] = useState<string | null>(initialSolutionId);
  const [uploadedContext, setUploadedContext] = useState('');
  const [uploadedFilename, setUploadedFilename] = useState('');
  const [showUploader, setShowUploader] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [buildRequested, setBuildRequested] = useState(false);
  const [buildProgress, setBuildProgress] = useState<BuildProgressState | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [finalizedBuild, setFinalizedBuild] = useState<MVPBuild | null>(null);
  const [engineOnline, setEngineOnline] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deployTarget, setDeployTarget] = useState<MVPBuild | null>(null);
  const [configureTarget, setConfigureTarget] = useState<MVPBuild | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, isStreaming]);

  // Auto-scroll the live build log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [buildProgress?.logs]);

  // Elapsed time timer for active builds
  useEffect(() => {
    if (!isStreaming || !buildProgress) return;
    const timer = setInterval(() => {
      setElapsedSeconds(Math.round((Date.now() - buildProgress.startedAt) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [isStreaming, buildProgress]);

  // Load any existing build for this solution on mount
  useEffect(() => {
    if (!solutionId) return;
    mvpApi.listBuilds(solutionId)
      .then((builds) => {
        if (builds && builds.length > 0) {
          setFinalizedBuild(builds[0]);
        }
      })
      .catch(() => undefined);
  }, [solutionId]);

  useEffect(() => {
    let mounted = true;
    const probe = () => opencodeApi.health()
      .then((r) => { if (mounted) setEngineOnline(Boolean(r.healthy)); })
      .catch(() => { if (mounted) setEngineOnline(false); });
    probe();
    const t = setInterval(probe, engineOnline ? 20000 : 5000);
    return () => { mounted = false; clearInterval(t); };
  }, [engineOnline]);

  const push = (content: string, agent?: string) =>
    setMessages((p) => [...p, { role: 'assistant', content, agent }]);

  const handleSend = async (finalize: boolean) => {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput('');
    setError(null);
    setMessages((p) => [...p, { role: 'user', content: text }]);
    setIsStreaming(true);

    if (finalize) {
      setBuildProgress({
        phase: 'analyzing',
        step: 1,
        total_steps: 7,
        percentage: 10,
        message: 'Synthesizing application architecture & specifications...',
        logs: ['[0s] Initializing custom full-stack build sequence...'],
        startedAt: Date.now(),
      });
      setElapsedSeconds(0);
    }

    try {
      await sendOpenCodeChatStream(
        {
          message: text,
          app_name: appName.trim() || undefined,
          solution_id: solutionId,
          session_id: sessionId,
          uploaded_context: uploadedContext,
          build_requested: finalize,
        },
        {
          onEvent: (event, data) => {
            if (event === 'agent_start') {
              if (typeof data.session_id === 'string') setSessionId(data.session_id);
              if (typeof data.solution_id === 'string') setSolutionId(data.solution_id);
              push((data.message as string) || 'Initializing intelligence sequence…', (data.agent as string) || 'SUTRA Intelligence');
            } else if (event === 'build_progress') {
              const p = data as unknown as OpenCodeBuildProgress;
              if (p.solution_id) setSolutionId(p.solution_id);

              if (p.session_id) setSessionId(p.session_id);
              setBuildProgress((prev) => {
                const startedAt = prev?.startedAt || Date.now();
                const sec = Math.round((Date.now() - startedAt) / 1000);
                const prevLogs = prev?.logs || [];
                return {
                  phase: p.phase || 'building',
                  step: p.step || 1,
                  total_steps: p.total_steps || 7,
                  percentage: p.percentage ?? 15,
                  message: p.message || 'Building application...',
                  logs: [...prevLogs, `[${sec}s] ${p.message}`],
                  startedAt,
                };
              });
            } else if (event === 'message' && data.message) {
              push(data.message as string, (data.agent as string) || 'SUTRA Intelligence');
            }
          },
          onComplete: async (data) => {
            const c = data as OpenCodeChatComplete;
            if (c.session_id) setSessionId(c.session_id);
            if (c.solution_id) setSolutionId(c.solution_id);
            push(c.message || 'Synthesis complete.', 'SUTRA Orchestrator');
            if (c.build_id) {
              try {
                const fresh = await mvpApi.getStatus(c.build_id);
                setFinalizedBuild(fresh);
              } catch {
                setFinalizedBuild({
                  build_id: c.build_id,
                  solution_id: c.solution_id || solutionId || '',
                  build_number: c.build_number || 1,
                  status: 'complete',
                  workspace_path: '',
                  file_count: c.file_count || 0,
                  files: (c.files || []).map((f) => ({ path: f, size: 1024, is_dir: false })),
                });
              }
            }
            if (finalize) setBuildRequested(false);
            setBuildProgress(null);
            setIsStreaming(false);
          },
          onError: (err) => {
            const msg = typeof err === 'object' && err && 'message' in err ? String((err as { message: string }).message) : 'Sequence interrupted.';
            setError(msg);
            push(msg, 'SUTRA Orchestrator');
            setBuildProgress(null);
            setIsStreaming(false);
          },
        }
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to reach SUTRA intelligence layer.');
      setBuildProgress(null);
      setIsStreaming(false);
    }
  };

  const handleDownload = async (build: MVPBuild) => {
    try { await mvpApi.downloadBuild(build.build_id, `mvp_build${build.build_number}.zip`); }
    catch (e) { setError(e instanceof Error ? e.message : 'Export failed.'); }
  };

  const handleDestroy = async (build: MVPBuild) => {
    if (!window.confirm(`Destroy build #${build.build_number}?`)) return;
    try { await mvpApi.destroy(build.build_id); setFinalizedBuild(null); }
    catch (e) { setError(e instanceof Error ? e.message : 'Purge failed.'); }
  };

  const handleDeployed = (result: MVPDeployResult | string) => {
    const repoUrl = typeof result === 'string' ? result : result.repo_url;
    const renderUrl = typeof result === 'string' ? null : (result.frontend_url || result.render_service_url);
    setFinalizedBuild((p) => p ? { ...p, repo_url: repoUrl, render_service_url: renderUrl, frontend_url: renderUrl } : p);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] animate-fade-up">

      {/* Header */}
      <div className="mb-4 flex items-center justify-between gap-4 px-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 flex items-center justify-center border border-[var(--sutra-muted-gold)] bg-[var(--bg)] text-[var(--sutra-muted-gold)]">
            <Layout className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-xl font-serif text-[var(--sutra-charcoal)]">AI Architect Workspace</h1>
            <p className="text-[11px] uppercase tracking-widest font-semibold text-[var(--text-2)] mt-0.5">Synthesis Engine</p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-bold">
          <span className="text-[var(--text-3)]">Intelligence Layer</span>
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-sm border shadow-sm ${
              engineOnline === null ? 'bg-[var(--bg-2)] border-[var(--border)] text-[var(--text-2)]'
              : engineOnline ? 'bg-[var(--bg-2)] border-[var(--border)] text-[var(--green)]'
              : 'bg-[var(--bg-2)] border-[var(--border)] text-[var(--red)]'
            }`}>
            {engineOnline === null
              ? <Loader2 className="w-3 h-3 animate-spin" />
              : engineOnline
                ? <CheckCircle2 className="w-3 h-3" />
                : <Circle className="w-3 h-3 animate-pulse-dot" />
            }
            {engineOnline === null ? 'Connecting...' : engineOnline ? 'Active' : 'Offline'}
          </div>
        </div>
      </div>

      {/* 3-Zone Workspace */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0">
        
        {/* ZONE 1: CONTEXT (3 cols) */}
        <div className="hidden lg:flex flex-col lg:col-span-3 h-full sutra-card bg-[var(--bg-2)] border-[var(--border)] min-w-0">
          <div className="p-4 border-b border-[var(--border)] flex items-center gap-2 bg-[var(--bg)]">
            <FileText className="w-4 h-4 text-[var(--text-3)]" />
            <h2 className="text-[11px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">Contextual Data</h2>
          </div>
          <div className="flex-1 p-4 overflow-y-auto overflow-x-hidden">
            {uploadedContext ? (
              <div className="space-y-4">
                <div className="p-3 bg-[var(--bg)] border border-[var(--sutra-muted-gold)] text-[12px]">
                  <p className="font-semibold text-[var(--sutra-charcoal)] break-all">{uploadedFilename}</p>
                  <p className="text-[10px] uppercase tracking-widest text-[var(--text-2)] mt-2 font-bold">{uploadedContext.length} characters parsed</p>
                </div>
                <button
                  onClick={() => { setUploadedContext(''); setUploadedFilename(''); }}
                  className="btn btn-ghost w-full text-[10px] uppercase tracking-widest font-semibold"
                >
                  Clear Context
                </button>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-4">
                <FileUploader
                  onParsedContext={(text, filename) => {
                    setUploadedContext(text);
                    setUploadedFilename(filename);
                    push(`Context established from **${filename}**. I am ready to process instructions.`);
                  }}
                  onClear={() => { setUploadedContext(''); setUploadedFilename(''); }}
                />
                <p className="text-[11px] text-[var(--text-2)] font-light max-w-[200px] break-words">
                  Provide a PRD, specs, or schema. SUTRA will incorporate this into the architecture.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* ZONE 2: WORKSPACE / CHAT (6 cols) */}
        <div className="flex flex-col lg:col-span-6 h-full sutra-card border-[var(--sutra-muted-gold)] shadow-md overflow-hidden bg-[var(--bg)] relative min-w-0">
          {/* Thread */}
          <div className="flex-1 overflow-y-auto p-6 pb-4">
            {messages.map((m, i) => <ChatMessage key={i} role={m.role} content={m.content} agent={m.agent} />)}

            {isStreaming && (
              <div className="flex items-center gap-3 text-[12px] text-[var(--text-2)] py-4 font-serif italic border-t border-[var(--border)] mt-4">
                <Loader2 className="w-4 h-4 animate-spin text-[var(--sutra-muted-gold)]" />
                {buildProgress ? (
                  <span>
                    Building application: <strong className="text-[var(--sutra-charcoal)]">{buildProgress.percentage}%</strong> — Step {buildProgress.step}/{buildProgress.total_steps}: {buildProgress.message}
                  </span>
                ) : (
                  'Synthesizing architecture...'
                )}
              </div>
            )}
            <div ref={endRef} className="h-4" />
          </div>

          {/* Input area */}
          <div className="p-4 bg-[var(--bg-2)] border-t border-[var(--border)]">
            {error && (
              <p className="text-[11px] font-semibold text-[var(--red)] bg-[var(--bg)] border border-[var(--red)] px-4 py-2 mb-3 shadow-sm">{error}</p>
            )}

            {buildRequested && (
              <div className="mb-2.5 flex items-center gap-2 animate-fade-in">
                <span className="text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)] shrink-0">App Name (optional):</span>
                <input
                  type="text"
                  value={appName}
                  onChange={(e) => setAppName(e.target.value)}
                  placeholder="e.g. FitPulse Gym, Gourmet Bistro, PetHaven..."
                  disabled={isStreaming}
                  className="flex-1 py-1.5 px-3 bg-[var(--bg)] border border-[var(--border)] text-[12px] text-[var(--sutra-charcoal)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors rounded-sm"
                />
              </div>
            )}

            <form
              onSubmit={(e) => { e.preventDefault(); handleSend(buildRequested); }}
              className="flex items-center gap-3"
            >
              {/* Context Toggle for mobile */}
              <button
                type="button"
                onClick={() => setShowUploader(!showUploader)}
                className={`lg:hidden p-3 border transition-colors shrink-0 rounded-sm ${uploadedContext
                    ? 'bg-[var(--bg)] border-[var(--sutra-muted-gold)] text-[var(--sutra-muted-gold)] shadow-sm'
                    : 'bg-[var(--bg)] border-[var(--border)] text-[var(--text-3)]'
                  }`}
                title="Attach context"
              >
                <Paperclip className="w-4 h-4" />
              </button>

              <div className="flex-1 relative flex items-center min-w-0">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={uploadedFilename ? `Instruct SUTRA (Context: ${uploadedFilename})...` : 'Describe your application...'}
                  disabled={isStreaming}
                  className="w-full py-3.5 pl-4 pr-24 bg-[var(--bg)] border border-[var(--border)] text-[13px] text-[var(--sutra-charcoal)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors rounded-sm shadow-sm min-w-0"
                />
                
                {/* Build toggle inside input */}
                <label className={`absolute right-2 flex items-center gap-2 px-3 py-1.5 rounded-sm text-[10px] uppercase tracking-widest font-bold cursor-pointer select-none transition-colors ${buildRequested ? 'bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)]' : 'bg-[var(--bg-2)] border border-[var(--border)] text-[var(--text-3)] hover:text-[var(--sutra-charcoal)] hover:border-[var(--text-3)]'
                  }`}>
                  <input type="checkbox" checked={buildRequested} onChange={(e) => setBuildRequested(e.target.checked)} className="sr-only" />
                  <Settings2 className="w-3 h-3" /> Build
                </label>
              </div>

              <button
                type="submit"
                disabled={!input.trim() || isStreaming}
                className="p-3.5 rounded-sm bg-[var(--sutra-charcoal)] hover:bg-black text-[var(--sutra-warm-ivory)] transition-colors disabled:opacity-50 shrink-0 shadow-md"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>

        {/* ZONE 3: ARTIFACT (3 cols) */}
        <div className="hidden lg:flex flex-col lg:col-span-3 h-full sutra-card bg-[var(--bg-2)] border-[var(--border)] min-w-0">
          <div className="p-4 border-b border-[var(--border)] flex items-center justify-between bg-[var(--bg)]">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-[var(--text-3)]" />
              <h2 className="text-[11px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">Build Artifacts</h2>
            </div>
            {isStreaming && buildProgress && (
              <div className="flex items-center gap-1.5 text-[10px] font-mono text-[var(--sutra-muted-gold)] font-bold">
                <Clock className="w-3 h-3 animate-spin" />
                <span>{elapsedSeconds}s</span>
              </div>
            )}
          </div>
          
          <div className="flex-1 p-4 overflow-y-auto">
            {finalizedBuild ? (
              <div className="space-y-4 animate-fade-in">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-bold text-[var(--green)] bg-[var(--bg)] border border-[var(--border)] p-2">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Build Orchestrated</span>
                  </div>
                  {finalizedBuild.solution_id && (
                    <a
                      href={`/solution/${finalizedBuild.solution_id}`}
                      className="text-[11px] font-medium text-[var(--sutra-muted-gold)] hover:underline"
                    >
                      View Artifacts →
                    </a>
                  )}
                </div>
                <BuildCard
                  build={finalizedBuild}
                  isDeployed={Boolean(finalizedBuild.repo_url)}
                  onDeploy={() => setDeployTarget(finalizedBuild)}
                  onConfigure={() => setConfigureTarget(finalizedBuild)}
                  onDownload={() => handleDownload(finalizedBuild)}
                  onDestroy={() => handleDestroy(finalizedBuild)}
                />
              </div>
            ) : isStreaming && (buildRequested || buildProgress) ? (
              /* LIVE BUILD PROGRESS DASHBOARD */
              <div className="space-y-4 animate-fade-in">
                {/* Active Status Badge */}
                <div className="p-3 bg-[var(--bg)] border border-[var(--sutra-muted-gold)] shadow-sm">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">
                      <Activity className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] animate-pulse" />
                      <span>Building Application</span>
                    </div>
                    <span className="text-[11px] font-mono font-bold text-[var(--sutra-muted-gold)]">
                      {buildProgress?.percentage ?? 15}%
                    </span>
                  </div>

                  {/* Progress Bar */}
                  <div className="w-full h-1.5 bg-[var(--bg-2)] rounded-full overflow-hidden border border-[var(--border)]">
                    <div
                      className="h-full bg-gradient-to-r from-[var(--sutra-muted-gold)] to-[var(--green)] transition-all duration-500 ease-out"
                      style={{ width: `${Math.max(5, buildProgress?.percentage ?? 15)}%` }}
                    />
                  </div>

                  <p className="text-[11px] text-[var(--text-2)] font-light mt-2 break-words">
                    {buildProgress?.message || 'Synthesizing application structure...'}
                  </p>
                </div>

                {/* Milestone Checklist */}
                <div className="bg-[var(--bg)] border border-[var(--border)] p-3 space-y-2">
                  <h3 className="text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)] mb-2">
                    Execution Milestones
                  </h3>
                  <div className="space-y-2">
                    {BUILD_MILESTONES.map((m) => {
                      const currentStep = buildProgress?.step || 1;
                      const isComplete = currentStep > m.step;
                      const isCurrent = currentStep === m.step;
                      return (
                        <div key={m.step} className="flex items-center gap-2.5 text-[11px]">
                          {isComplete ? (
                            <CheckCircle2 className="w-3.5 h-3.5 text-[var(--green)] shrink-0" />
                          ) : isCurrent ? (
                            <Loader2 className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] animate-spin shrink-0" />
                          ) : (
                            <Circle className="w-3.5 h-3.5 text-[var(--text-3)]/40 shrink-0" />
                          )}
                          <span
                            className={
                              isComplete
                                ? 'text-[var(--sutra-charcoal)] font-medium'
                                : isCurrent
                                ? 'text-[var(--sutra-charcoal)] font-bold'
                                : 'text-[var(--text-3)] font-light'
                            }
                          >
                            {m.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Live Activity Log */}
                {buildProgress?.logs && buildProgress.logs.length > 0 && (
                  <div className="bg-[var(--bg)] border border-[var(--border)] p-3">
                    <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)] mb-2">
                      <Terminal className="w-3 h-3" />
                      <span>Live Build Log</span>
                    </div>
                    <div className="max-h-36 overflow-y-auto space-y-1 font-mono text-[10px] text-[var(--text-2)] bg-[var(--bg-2)] p-2 rounded-sm border border-[var(--border)]">
                      {buildProgress.logs.map((log, idx) => (
                        <div key={idx} className="break-words leading-tight">
                          <span className="text-[var(--sutra-muted-gold)]">{log}</span>
                        </div>
                      ))}
                      <div ref={logEndRef} />
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center space-y-4 opacity-60">
                <div className="w-12 h-12 flex items-center justify-center border border-[var(--border)] border-dashed">
                  <Play className="w-5 h-5 text-[var(--text-3)]" />
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-widest font-bold text-[var(--sutra-charcoal)]">Awaiting Synthesis</p>
                  <p className="text-[11px] text-[var(--text-2)] font-light max-w-[180px] mx-auto mt-2">
                    Toggle <span className="font-semibold">BUILD</span> before sending to generate a deployable MVP architecture.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>

      {deployTarget && <DeployModal build={deployTarget} onClose={() => setDeployTarget(null)} onDeployed={handleDeployed} />}
      {configureTarget && <ConfigureModal build={configureTarget} onClose={() => setConfigureTarget(null)} onConfigured={() => undefined} />}
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-full text-[var(--text-2)] font-serif italic">Initializing Workspace...</div>}>
      <ChatContent />
    </Suspense>
  );
}