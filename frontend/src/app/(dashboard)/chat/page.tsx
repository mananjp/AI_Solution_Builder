'use client';

import React, { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Send, Paperclip, Loader2, Wrench, CheckCircle2, Circle } from 'lucide-react';
import ChatMessage from '@/components/ChatMessage';
import FileUploader from '@/components/FileUploader';
import { opencodeApi, sendOpenCodeChatStream, mvpApi } from '@/lib/api';
import { MVPBuild, MVPDeployResult, OpenCodeChatComplete } from '@/types';
import { BuildCard, ConfigureModal, DeployModal } from '@/components/mvp/BuildCard';

type Msg = { role: 'user' | 'assistant' | 'system'; content: string; agent?: string };

function ChatContent() {
  const searchParams = useSearchParams();
  const initialPrompt = searchParams.get('prompt') || '';

  const [input, setInput] = useState(initialPrompt);
  const [messages, setMessages] = useState<Msg[]>([{
    role: 'assistant',
    agent: 'AI Developer',
    content: "I'm your custom app builder. Tell me what you want to build and I'll scaffold a working FastAPI + Next.js app. Upload a spec/PRD for extra context, and toggle **Build** whenever you're ready to finalize a deployable build.",
  }]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [solutionId, setSolutionId] = useState<string | null>(null);
  const [uploadedContext, setUploadedContext] = useState('');
  const [uploadedFilename, setUploadedFilename] = useState('');
  const [showUploader, setShowUploader] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [buildRequested, setBuildRequested] = useState(false);
  const [finalizedBuild, setFinalizedBuild] = useState<MVPBuild | null>(null);
  const [engineOnline, setEngineOnline] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deployTarget, setDeployTarget] = useState<MVPBuild | null>(null);
  const [configureTarget, setConfigureTarget] = useState<MVPBuild | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, isStreaming]);

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
    try {
      await sendOpenCodeChatStream(
        { message: text, solution_id: solutionId, session_id: sessionId, uploaded_context: uploadedContext, build_requested: finalize },
        {
          onEvent: (event, data) => {
            if (event === 'agent_start') {
              if (typeof data.session_id === 'string') setSessionId(data.session_id);
              if (typeof data.solution_id === 'string') setSolutionId(data.solution_id);
              push(data.message as string || 'Connected to AI build engine…', (data.agent as string) || 'AI Developer');
            } else if (event === 'message' && data.message) {
              push(data.message as string, (data.agent as string) || 'AI Developer');
            }
          },
          onComplete: (data) => {
            const c = data as OpenCodeChatComplete;
            if (c.session_id) setSessionId(c.session_id);
            if (c.solution_id) setSolutionId(c.solution_id);
            push(c.message || 'Done.', 'AI Developer');
            if (c.build_id) {
              setFinalizedBuild({ build_id: c.build_id, solution_id: c.solution_id || solutionId || '', build_number: c.build_number || 1, status: 'complete', workspace_path: '', file_count: 0 });
            }
            if (finalize) setBuildRequested(false);
            setIsStreaming(false);
          },
          onError: (err) => {
            const msg = typeof err === 'object' && err && 'message' in err ? String((err as { message: string }).message) : 'Something went wrong.';
            setError(msg);
            push(msg, 'AI Developer');
            setIsStreaming(false);
          },
        }
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to reach the AI build engine.');
      setIsStreaming(false);
    }
  };

  const handleDownload = async (build: MVPBuild) => {
    try { await mvpApi.downloadBuild(build.build_id, `mvp_build${build.build_number}.zip`); }
    catch (e) { setError(e instanceof Error ? e.message : 'Download failed.'); }
  };

  const handleDestroy = async (build: MVPBuild) => {
    if (!window.confirm(`Destroy build #${build.build_number}?`)) return;
    try { await mvpApi.destroy(build.build_id); setFinalizedBuild(null); }
    catch (e) { setError(e instanceof Error ? e.message : 'Destroy failed.'); }
  };

  const handleDeployed = (result: MVPDeployResult | string) => {
    const repoUrl = typeof result === 'string' ? result : result.repo_url;
    const renderUrl = typeof result === 'string' ? null : (result.frontend_url || result.render_service_url);
    setFinalizedBuild((p) => p ? { ...p, repo_url: repoUrl, render_service_url: renderUrl, frontend_url: renderUrl } : p);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] max-w-4xl mx-auto">

      {/* Header */}
      <div className="mb-4 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#161616] border border-[#242424] flex items-center justify-center text-[#6366f1]">
            <Wrench className="w-4 h-4" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white">Custom App Builder</h1>
            <p className="text-[11px] text-[#555]">Chat → scaffold FastAPI + Next.js workspace in real time</p>
          </div>
        </div>

        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-[11px] font-medium ${engineOnline === null ? 'bg-[#111] border-[#1a1a1a] text-[#555]'
            : engineOnline ? 'bg-[#22c55e0a] border-[#22c55e20] text-[#4ade80]'
              : 'bg-[#f59e0b0a] border-[#f59e0b20] text-[#fbbf24]'
          }`}>
          {engineOnline === null
            ? <Loader2 className="w-3 h-3 animate-spin" />
            : engineOnline
              ? <CheckCircle2 className="w-3 h-3" />
              : <Circle className="w-3 h-3 animate-pulse-dot" />
          }
          {engineOnline === null ? 'Checking…' : engineOnline ? 'Engine Online' : 'Engine Offline'}
        </div>
      </div>

      {/* Thread */}
      <div className="flex-1 bg-[#0f0f0f] border border-[#1a1a1a] rounded-xl p-5 overflow-y-auto space-y-4">
        {messages.map((m, i) => <ChatMessage key={i} role={m.role} content={m.content} agent={m.agent} />)}

        {isStreaming && (
          <div className="flex items-center gap-2.5 text-[12px] text-[#555] py-1">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-[#6366f1]" />
            AI developer is working in your workspace…
          </div>
        )}

        {finalizedBuild && (
          <div className="pt-2 space-y-2">
            <div className="flex items-center gap-2 text-[12px] text-[#4ade80]">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span className="font-medium">Build ready</span>
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
        )}
        <div ref={endRef} />
      </div>

      {/* Input area */}
      <div className="mt-3 space-y-2">
        {error && (
          <p className="text-[11px] text-[#f87171] bg-[#ef444410] border border-[#ef444420] rounded-lg px-3 py-2">{error}</p>
        )}

        {showUploader && (
          <div className="p-3 bg-[#111] border border-[#1a1a1a] rounded-xl">
            <FileUploader
              onParsedContext={(text, filename) => {
                setUploadedContext(text);
                setUploadedFilename(filename);
                setShowUploader(false);
                push(`Extracted content from **${filename}** (${text.length} chars). You can now ask about this document.`);
              }}
              onClear={() => { setUploadedContext(''); setUploadedFilename(''); }}
            />
          </div>
        )}

        <form
          onSubmit={(e) => { e.preventDefault(); handleSend(buildRequested); }}
          className="flex items-center gap-2"
        >
          <button
            type="button"
            onClick={() => setShowUploader(!showUploader)}
            className={`p-2.5 rounded-lg border transition-colors shrink-0 ${uploadedContext
                ? 'bg-[#6366f10a] border-[#6366f130] text-[#818cf8]'
                : 'bg-[#111] border-[#1a1a1a] text-[#555] hover:text-[#a1a1a1] hover:border-[#242424]'
              }`}
            title="Attach PRD"
          >
            <Paperclip className="w-4 h-4" />
          </button>

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={uploadedFilename ? `Ask using context from ${uploadedFilename}…` : 'Describe the app you want to build…'}
            disabled={isStreaming}
            className="flex-1 py-2.5 pl-4 pr-3 rounded-lg bg-[#111] border border-[#1a1a1a] text-white text-[13px] placeholder:text-[#444] focus:outline-none focus:border-[#2e2e2e] transition-colors"
          />

          {/* Build toggle */}
          <label className={`flex items-center gap-1.5 px-3 py-2.5 rounded-lg border text-[12px] font-medium cursor-pointer select-none transition-colors shrink-0 ${buildRequested ? 'bg-[#22c55e0a] border-[#22c55e30] text-[#4ade80]' : 'bg-[#111] border-[#1a1a1a] text-[#555]'
            }`}>
            <input type="checkbox" checked={buildRequested} onChange={(e) => setBuildRequested(e.target.checked)} className="sr-only" />
            Build
          </label>

          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="p-2.5 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white transition-colors disabled:opacity-40 shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>

        <p className="text-[11px] text-[#444]">
          Toggle <span className="text-[#4ade80]">Build</span> and send to finalize a download/deploy-ready build.
        </p>
      </div>

      {deployTarget && <DeployModal build={deployTarget} onClose={() => setDeployTarget(null)} onDeployed={handleDeployed} />}
      {configureTarget && <ConfigureModal build={configureTarget} onClose={() => setConfigureTarget(null)} onConfigured={() => undefined} />}
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="text-[#555] text-sm p-6">Loading…</div>}>
      <ChatContent />
    </Suspense>
  );
}