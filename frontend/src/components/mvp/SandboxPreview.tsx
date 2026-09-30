'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Globe, Loader2, MessageSquare, RefreshCw, Rocket, Send, Sparkles, X } from 'lucide-react';
import { mvpApi, sendSandboxChatStream } from '@/lib/api';
import { MVPBuild, MVPDeployStatus } from '@/types';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

interface SandboxMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export function SandboxPreview({
  build,
  onClose,
}: {
  build: MVPBuild;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<SandboxMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [deployStatus, setDeployStatus] = useState<MVPDeployStatus | null>(null);
  const [iframeStatus, setIframeStatus] = useState<'idle' | 'loading' | 'loaded' | 'error'>('loading');
  // Bumped on every reload to force the iframe to remount. The reload button
  // previously only reset `iframeStatus`, but the iframe's `key` was the URL, so
  // React reused the same element, `onLoad` never fired again, and the loading
  // overlay covered the preview permanently.
  const [reloadNonce, setReloadNonce] = useState(0);
  const msgCounter = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);

  const src = build.frontend_url || build.render_service_url || null;

  const handleReload = useCallback(() => {
    setIframeStatus('loading');
    setReloadNonce((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const st = await mvpApi.deployStatus(build.build_id);
        if (!cancelled) setDeployStatus(st);
      } catch {
        // keep last known
      }
    };
    poll();
    const timer = setInterval(poll, 6000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [build.build_id]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || isStreaming) return;
    setInput('');
    msgCounter.current += 1;
    const userMsg: SandboxMessage = { id: `u-${msgCounter.current}`, role: 'user', content: text };
    const botMsg: SandboxMessage = { id: `a-${msgCounter.current}`, role: 'assistant', content: '' };
    setMessages((prev) => [...prev, userMsg, botMsg]);
    setIsStreaming(true);

    const history = messages.slice(-8).map((m) => ({ role: m.role, content: m.content }));
    try {
      await sendSandboxChatStream(
        build.build_id,
        { message: text, history },
        {
          onEvent: (event, data) => {
            if (event === 'message' && data?.content) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === botMsg.id ? { ...m, content: String(data.content) } : m
                )
              );
            }
          },
          onComplete: (data) => {
            const content = data?.content ? String(data.content) : '';
            if (content) {
              setMessages((prev) => prev.map((m) => (m.id === botMsg.id ? { ...m, content } : m)));
            }
            setIsStreaming(false);
          },
          onError: (err) => {
            const msg =
              typeof err === 'object' && err && 'message' in err
                ? String((err as { message: string }).message)
                : 'Sandbox agent unreachable.';
            setMessages((prev) =>
              prev.map((m) => (m.id === botMsg.id ? { ...m, content: msg } : m))
            );
            setIsStreaming(false);
          },
        }
      );
    } catch (e) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === botMsg.id
            ? { ...m, content: `Sandbox agent error: ${e instanceof Error ? e.message : 'unknown'}` }
            : m
        )
      );
      setIsStreaming(false);
    }
  };

  const overall = deployStatus?.overall || build.deploy_state?.status || build.render_deploy_status;
  const services = deployStatus?.services || build.deploy_state?.services || {};
  const serviceNames = Object.keys(services);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--sutra-ink)]/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-6xl h-[88vh] bg-[var(--bg)] border border-[var(--sutra-strong)] shadow-2xl flex flex-col sm:p-5 p-3">
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-3 mb-3">
          <h3 className="text-[14px] font-serif text-[var(--sutra-ink)] flex items-center gap-2">
            <Rocket className="w-4 h-4 text-[var(--sutra-strong)]" />
            <span>Sandbox Preview — Build #{build.build_number}</span>
            {src ? (
              <Badge variant="success" className="text-[10px]">live app</Badge>
            ) : (
              <Badge variant="warning" className="text-[10px]">not deployed</Badge>
            )}
          </h3>
          <Button variant="ghost" size="icon-sm" onClick={onClose} className="text-[var(--text-3)] hover:text-[var(--sutra-ink)] transition-colors">
            <X className="w-4 h-4" />
          </Button>
        </div>

        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-0">
          {/* Preview iframe */}
          <div className="lg:col-span-8 flex flex-col h-[40vh] lg:h-full min-h-0">
            <div className="flex items-center justify-between gap-2 border border-[var(--border)] bg-[var(--bg-2)] px-3 py-2">
              <div className="flex items-center gap-2 min-w-0">
                <Globe className="w-3.5 h-3.5 text-[var(--sutra-strong)] shrink-0" />
                <span className="text-[11px] font-mono text-[var(--text-2)] truncate">{src || 'No live URL yet'}</span>
              </div>
              {src && (
                <div className="flex items-center gap-2 shrink-0">
                  <Button variant="outline" size="icon-sm"
                    onClick={handleReload}
                    className="p-1.5 border border-[var(--border)] text-[var(--text-3)] hover:text-[var(--sutra-ink)] transition-colors"
                    title="Reload preview"
                  >
                    <RefreshCw className="w-3 h-3" />
                  </Button>
                  <a
                    href={src}
                    target="_blank"
                    rel="noreferrer"
                    className="p-1.5 border border-[var(--border)] text-[var(--text-3)] hover:text-[var(--sutra-ink)] transition-colors"
                    title="Open in new tab"
                  >
                    <Globe className="w-3 h-3" />
                  </a>
                </div>
              )}
            </div>

            <div className="flex-1 bg-[var(--bg-2)] border border-t-0 border-[var(--border)] relative min-h-0">
              {src ? (
                <>
                  {iframeStatus !== 'loaded' && (
                    <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-[var(--bg-2)] text-[var(--text-2)]">
                      {/* A failed load must not render a spinner: the copy says
                          the preview is unreachable, so a rotating loader
                          contradicted it and implied work still in progress. */}
                      {iframeStatus === 'error' ? (
                        <>
                          <AlertTriangle className="w-5 h-5 text-[var(--amber)]" />
                          <p className="text-[11px] font-light max-w-xs text-center">
                            Preview could not be reached. It may be waking from Render
                            free-tier sleep — reload shortly.
                          </p>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            onClick={handleReload}
                          >
                            <RefreshCw className="w-3 h-3" />
                            Reload
                          </Button>
                        </>
                      ) : (
                        <>
                          <Loader2 className="w-5 h-5 animate-spin text-[var(--sutra-strong)]" />
                          <p className="text-[11px] font-light max-w-xs text-center">
                            Loading live app preview…
                          </p>
                        </>
                      )}
                    </div>
                  )}
                  <iframe
                    key={`${src}#${reloadNonce}`}
                    src={src}
                    title={`Sandbox preview — ${build.build_id.slice(0, 8)}`}
                    className="w-full h-full border-0"
                    sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                    onLoad={() => setIframeStatus('loaded')}
                    onError={() => setIframeStatus('error')}
                  />
                </>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center gap-3 p-6">
                  <Rocket className="w-8 h-8 text-[var(--text-3)]" />
                  <p className="text-[12px] text-[var(--text-2)] font-light max-w-sm">
                    This build isn&apos;t deployed yet — the preview needs a live URL.
                  </p>
                  <p className="text-[11px] font-mono text-[var(--sutra-strong)]">
                    Use <strong>Deploy</strong> on the build card first, then return here to inspect the running app.
                  </p>
                  <Badge variant="warning" className="text-[10px]">Deploy required</Badge>
                </div>
              )}

              {src && overall && overall !== 'live' && (
                <div className="absolute bottom-0 inset-x-0 z-10 border-t border-[var(--border)] bg-[var(--bg)]/95 px-3 py-2 flex items-center gap-2 text-[10px] font-mono text-[var(--text-2)]">
                  <Loader2 className="w-3 h-3 animate-spin text-[var(--sutra-strong)] shrink-0" />
                  <span className="truncate">
                    Render status: {overall} {serviceNames.map((n) => `${n}=${services[n]?.status || 'building'}`).join(' · ')}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Chat side panel */}
          <div className="lg:col-span-4 flex flex-col h-[46vh] lg:h-full min-h-0 border border-[var(--border)] bg-[var(--bg-2)]">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border)] bg-[var(--bg)]">
              <MessageSquare className="w-3.5 h-3.5 text-[var(--sutra-strong)]" />
              <span className="text-[10px] uppercase tracking-widest font-bold text-[var(--sutra-ink)]">
                Sandbox Agent
              </span>
              <Sparkles className="w-3 h-3 text-[var(--sutra-strong)] ml-auto" />
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {messages.length === 0 && (
                <p className="text-[11px] text-[var(--text-2)] font-light leading-relaxed">
                  This assistant knows exactly what was built — the entities, API, files, and any
                  live URLs. Try: <em>“What&apos;s the data model?”</em>, <em>“How does auth work?”</em>, or{' '}
                  <em>“Which endpoints does the frontend call?”</em>
                </p>
              )}
              {messages.map((m) => (
                <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[85%] px-3 py-2 text-[11px] leading-relaxed break-words whitespace-pre-wrap shadow-sm border ${
                      m.role === 'user'
                        ? 'bg-[var(--sutra-ink)] text-[var(--sutra-canvas)] border-[var(--sutra-ink)]'
                        : 'bg-[var(--bg)] border-[var(--border)] text-[var(--text-1)]'
                    }`}
                  >
                    {m.content || (isStreaming && <Loader2 className="w-3 h-3 animate-spin text-[var(--sutra-strong)]" />)}
                  </div>
                </div>
              ))}
              <div ref={endRef} />
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="border-t border-[var(--border)] bg-[var(--bg)] p-2 flex items-center gap-2"
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about this app…"
                disabled={isStreaming || !src}
                className="flex-1 px-3 py-2 bg-[var(--bg-2)] border border-[var(--border)] text-[12px] text-[var(--sutra-ink)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-strong)] transition-colors disabled:opacity-50"
              />
              <Button variant="default" size="icon-sm"
                type="submit"
                disabled={!input.trim() || isStreaming || !src}
                className="p-2.5 bg-[var(--sutra-ink)] hover:bg-[var(--foreground)] text-[var(--sutra-canvas)] transition-colors disabled:opacity-50 shrink-0"
              >
                <Send className="w-3.5 h-3.5" />
              </Button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}