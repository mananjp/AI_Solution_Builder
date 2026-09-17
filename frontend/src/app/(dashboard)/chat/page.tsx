'use client';

import React, { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  Send,
  Paperclip,
  Loader2,
  Wrench,
  Rocket,
  CircleCheck,
  Radio,
} from 'lucide-react';
import ChatMessage from '@/components/ChatMessage';
import FileUploader from '@/components/FileUploader';
import { opencodeApi, sendOpenCodeChatStream, mvpApi } from '@/lib/api';
import { MVPBuild, MVPDeployResult, OpenCodeChatComplete } from '@/types';
import { BuildCard, ConfigureModal, DeployModal } from '@/components/mvp/BuildCard';

type ChatMessageItem = {
  role: 'user' | 'assistant' | 'system';
  content: string;
  agent?: string;
};

function ChatContent() {
  const searchParams = useSearchParams();
  const initialPrompt = searchParams.get('prompt') || '';

  const [inputMessage, setInputMessage] = useState(initialPrompt);
  const [messages, setMessages] = useState<ChatMessageItem[]>([
    {
      role: 'assistant',
      agent: 'AI Developer',
      content:
        "I'm your custom app builder. Tell me what you want to build and I'll scaffold a working FastAPI + Next.js app and iterate on it with you. Upload a spec/PRD for extra context, and hit **Build App** whenever you're ready to finalize a downloadable, deployable build.",
    },
  ]);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [solutionId, setSolutionId] = useState<string | null>(null);
  const [uploadedContext, setUploadedContext] = useState<string>('');
  const [uploadedFilename, setUploadedFilename] = useState<string>('');
  const [showUploader, setShowUploader] = useState(false);

  const [isStreaming, setIsStreaming] = useState(false);
  const [buildRequested, setBuildRequested] = useState(false);
  const [finalizedBuild, setFinalizedBuild] = useState<MVPBuild | null>(null);
  const [sidecarHealthy, setSidecarHealthy] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [deployTarget, setDeployTarget] = useState<MVPBuild | null>(null);
  const [configureTarget, setConfigureTarget] = useState<MVPBuild | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  useEffect(() => {
    let mounted = true;
    const probe = () => {
      opencodeApi
        .health()
        .then((res) => {
          if (mounted) setSidecarHealthy(Boolean(res.healthy));
        })
        .catch(() => {
          if (mounted) setSidecarHealthy(false);
        });
    };
    probe();
    const interval = setInterval(probe, sidecarHealthy ? 20000 : 4000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [sidecarHealthy]);

  const pushAssistant = (content: string, agent?: string) => {
    setMessages((prev) => [...prev, { role: 'assistant', content, agent }]);
  };

  const handleSendMessage = async (finalize: boolean) => {
    const text = inputMessage.trim();
    if (!text || isStreaming) return;

    setInputMessage('');
    setError(null);
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setIsStreaming(true);

    try {
      await sendOpenCodeChatStream(
        {
          message: text,
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
              const text = data.message || 'Connected to the AI build engine...';
              pushAssistant(text, (data.agent as string) || 'AI Developer');
            } else if (event === 'message' && data.message) {
              pushAssistant(data.message, (data.agent as string) || 'AI Developer');
            }
          },
          onComplete: (data) => {
            const complete = data as OpenCodeChatComplete;
            if (complete.session_id) setSessionId(complete.session_id);
            if (complete.solution_id) setSolutionId(complete.solution_id);
            const text = complete.message || 'Build created.';
            pushAssistant(text, 'AI Developer');

            if (complete.build_id) {
              const build: MVPBuild = {
                build_id: complete.build_id,
                solution_id: complete.solution_id || solutionId || '',
                build_number: complete.build_number || 1,
                status: 'complete',
                workspace_path: '',
                file_count: 0,
              };
              setFinalizedBuild(build);
            }
            if (finalize) {
              setBuildRequested(false);
            }
            setIsStreaming(false);
          },
          onError: (err) => {
            const message =
              typeof err === 'object' && err && 'message' in err
                ? String((err as { message: string }).message)
                : 'Something went wrong talking to the AI build engine.';
            setError(message);
            setMessages((prev) => [
              ...prev,
              { role: 'assistant', agent: 'AI Developer', content: message },
            ]);
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
    try {
      await mvpApi.downloadBuild(build.build_id, `mvp_${build.solution_id.slice(0, 8)}_build${build.build_number}.zip`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed.');
    }
  };

  const handleDestroy = async (build: MVPBuild) => {
    if (!window.confirm(`Destroy this build #${build.build_number}?`)) return;
    try {
      await mvpApi.destroy(build.build_id);
      setFinalizedBuild(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Destroy failed.');
    }
  };

  const handleDeployed = (result: MVPDeployResult | string) => {
    const repoUrl = typeof result === 'string' ? result : result.repo_url;
    const renderUrl = typeof result === 'string' ? null : (result.frontend_url || result.render_service_url);
    const backendUrl = typeof result === 'string' ? null : result.backend_url;
    const renderDash = typeof result === 'string' ? null : result.render_dashboard_url;
    const renderDeploy = typeof result === 'string' ? null : result.render_deploy_url;
    setFinalizedBuild((prev) =>
      prev
        ? {
            ...prev,
            repo_url: repoUrl,
            render_service_url: renderUrl,
            frontend_url: renderUrl,
            backend_url: backendUrl,
            render_dashboard_url: renderDash,
            render_deploy_url: renderDeploy,
          }
        : prev
    );
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20">
            <Wrench className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-extrabold text-white tracking-tight">Custom App Builder</h2>
            <p className="text-[11px] text-slate-500">
              Chat with the AI developer — your FastAPI + Next.js workspace is scaffolded and edited live.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-[11px] font-semibold ${
              sidecarHealthy === null
                ? 'bg-slate-900/60 border-white/10 text-slate-400'
                : sidecarHealthy
                ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
                : 'bg-amber-950/40 border-amber-500/30 text-amber-300'
            }`}
          >
            {sidecarHealthy === null ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : sidecarHealthy ? (
              <CircleCheck className="w-3 h-3" />
            ) : (
              <Radio className="w-3 h-3 animate-pulse" />
            )}
            <span>{sidecarHealthy === null ? 'Checking...' : sidecarHealthy ? 'Engine Online' : 'Engine Offline'}</span>
          </span>
        </div>
      </div>

      {/* Chat Thread Container */}
      <div className="flex-1 bg-slate-950/60 border border-white/5 rounded-2xl p-6 overflow-y-auto backdrop-blur-xl shadow-2xl space-y-4">
        {messages.map((msg, index) => (
          <ChatMessage key={index} role={msg.role} content={msg.content} agent={msg.agent} />
        ))}

        {/* Streaming Indicator */}
        {isStreaming && (
          <div className="flex items-center gap-3 p-3.5 rounded-xl bg-indigo-950/30 border border-indigo-500/20 max-w-sm text-indigo-300 text-xs">
            <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
            <span>The AI developer is working in your workspace...</span>
          </div>
        )}

        {/* Finalized Build Card */}
        {finalizedBuild && (
          <div className="my-6 space-y-3">
            <div className="flex items-center gap-2">
              <CircleCheck className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-white">Your app is built and ready</h3>
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

        <div ref={chatEndRef} />
      </div>

      {/* Chat Input & File Uploader Bar */}
      <div className="mt-4 space-y-2">
        {error && (
          <p className="text-[11px] text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-xl px-3 py-2">
            {error}
          </p>
        )}

        {showUploader && (
          <div className="p-3 bg-slate-900/60 border border-white/10 rounded-2xl">
            <FileUploader
              onParsedContext={(text, filename) => {
                setUploadedContext(text);
                setUploadedFilename(filename);
                setShowUploader(false);
                pushAssistant(`Extracted content from **${filename}** (${text.length} characters). You can now ask about this document.`);
              }}
              onClear={() => {
                setUploadedContext('');
                setUploadedFilename('');
              }}
            />
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage(buildRequested);
          }}
          className="relative flex items-center"
        >
          <button
            type="button"
            onClick={() => setShowUploader(!showUploader)}
            className={`p-3 rounded-xl border mr-2 transition-colors ${
              uploadedContext
                ? 'bg-indigo-500/20 border-indigo-500/50 text-indigo-300'
                : 'bg-slate-900 border-white/10 text-slate-400 hover:text-slate-200'
            }`}
            title="Attach PRD or specification document"
          >
            <Paperclip className="w-4 h-4" />
          </button>

          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder={
              uploadedFilename
                ? `Ask using context from ${uploadedFilename}...`
                : 'Describe the app you want to build (e.g. "an inventory management API")...'
            }
            disabled={isStreaming}
            className="flex-1 py-3.5 pl-4 pr-32 rounded-xl bg-slate-900 border border-white/10 text-white text-xs placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 transition-colors shadow-inner"
          />

          {/* Finalize toggle */}
          <label
            className={`absolute right-20 flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-[11px] font-semibold cursor-pointer select-none transition-colors ${
              buildRequested ? 'bg-emerald-500/15 text-emerald-300' : 'bg-white/5 text-slate-400'
            }`}
            title="Finalize the build when sending this message"
          >
            <input
              type="checkbox"
              checked={buildRequested}
              onChange={(e) => setBuildRequested(e.target.checked)}
              className="accent-emerald-500"
            />
            <Rocket className={`w-3 h-3 ${buildRequested ? 'text-emerald-300' : 'text-slate-500'}`} />
            Build
          </label>

          <button
            type="submit"
            disabled={!inputMessage.trim() || isStreaming}
            className="absolute right-2 p-2 rounded-lg bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white transition-all disabled:opacity-40"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>

        <p className="text-[10px] text-slate-600 leading-relaxed">
          Toggle <span className="text-emerald-400 font-semibold">Build</span> and send to verify the workspace and create
          a download/deploy-ready build. Building consumes MVP-build credits.
        </p>
      </div>

      {deployTarget && <DeployModal build={deployTarget} onClose={() => setDeployTarget(null)} onDeployed={handleDeployed} />}
      {configureTarget && (
        <ConfigureModal build={configureTarget} onClose={() => setConfigureTarget(null)} onConfigured={() => undefined} />
      )}
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="text-white text-xs p-6">Loading Custom App Builder...</div>}>
      <ChatContent />
    </Suspense>
  );
}