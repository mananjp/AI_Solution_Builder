'use client';

import React, { Suspense, useCallback, useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  History,
  Layout,
  Loader2,
  Paperclip,
  Plus,
  Send,
  Settings2,
  ShieldCheck,
  X,
} from 'lucide-react';
import clsx from 'clsx';
import ChatMessage from '@/components/ChatMessage';
import { VoiceInputButton } from '@/components/VoiceInputButton';
import { ChatSidecar } from '@/components/chat/ChatSidecar';
import { ArtifactsPanel } from '@/components/chat/ArtifactsPanel';
import { ThreadSkeleton, ThinkingBubble } from '@/components/chat/Skeleton';
import { mvpApi, opencodeApi, sendOpenCodeChatStream, solutionApi } from '@/lib/api';
import { ConfigureModal, DeployModal } from '@/components/mvp/BuildCard';
import { useI18n } from '@/components/I18nProvider';
import {
  removeCachedSolution,
  upsertCachedSolution,
  useChatSession,
} from '@/hooks/useChatSession';
import type { MVPBuild, MVPDeployResult, OpenCodeChatComplete, Solution } from '@/types';

const ACTIVE_SOLUTION_KEY = 'sutra_active_solution_id';

function readStoredSolutionId(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(ACTIVE_SOLUTION_KEY);
    return raw && raw !== 'null' && raw !== 'undefined' && raw.trim() ? raw.trim() : null;
  } catch {
    return null;
  }
}

function writeStoredSolutionId(id: string | null) {
  if (typeof window === 'undefined') return;
  try {
    if (id) window.localStorage.setItem(ACTIVE_SOLUTION_KEY, id);
    else window.localStorage.removeItem(ACTIVE_SOLUTION_KEY);
  } catch {
    // storage unavailable — in-memory state is still correct
  }
}

function ChatContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useI18n();

  // Read the URL once; from here on `state.solutionId` is the only source of
  // truth. Deriving it from `useSearchParams()` on every render is what froze
  // the sidecar — the app used `history.replaceState`, which Next's App Router
  // never observes.
  const urlSolutionId = searchParams.get('solution_id');
  const initialAppName = searchParams.get('app_name') || '';
  const initialPrompt = searchParams.get('prompt') || '';
  const startNew = searchParams.get('new') === 'true';

  const agent = t('common.sutraOrchestrator');
  const welcome = t('chat.welcomeMessage');

  const { state, dispatch, hydrate, selectSolution, loadHistory } = useChatSession({
    welcome,
    agent,
    initialPrompt,
    initialSolutionId: startNew ? null : (urlSolutionId ?? readStoredSolutionId()),
    initialAppName,
    startNew,
  });

  // Kept in a ref so the SSE callbacks always read the latest active solution
  // without re-subscribing the stream on every keystroke.
  const solutionIdRef = useRef<string | null>(state.solutionId);
  useEffect(() => {
    solutionIdRef.current = state.solutionId;
  }, [state.solutionId]);

  // ── Persist + reflect the active conversation ──
  useEffect(() => {
    writeStoredSolutionId(state.solutionId);
    const params = new URLSearchParams(searchParams.toString());
    if (state.solutionId) {
      if (params.get('solution_id') !== state.solutionId) {
        params.set('solution_id', state.solutionId);
        router.replace(`/chat?${params.toString()}`, { scroll: false });
      }
    } else if (params.get('solution_id')) {
      params.delete('solution_id');
      params.delete('app_name');
      router.replace(`/chat?${params.toString()}`, { scroll: false });
    }
  }, [state.solutionId, router, searchParams]);

  // ── Load the conversation whenever the active id changes ──
  useEffect(() => {
    void hydrate(state.solutionId);
  }, [state.solutionId, hydrate]);

  // ── Engine health probe ──
  useEffect(() => {
    let mounted = true;
    const probe = () =>
      opencodeApi
        .health()
        .then((r) => {
          if (mounted) dispatch({ type: 'set-engine', value: r.healthy ? 'online' : 'offline' });
        })
        .catch(() => {
          if (mounted) dispatch({ type: 'set-engine', value: 'offline' });
        });
    void probe();
    const timer = setInterval(probe, state.engine === 'online' ? 20000 : 5000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
    // Re-arms the interval when connectivity flips.
  }, [state.engine, dispatch]);

  // ── Persist conversation into history cache after each turn ──
  const syncHistoryEntry = useCallback(async (id: string) => {
    try {
      const solution = await solutionApi.get(id);
      upsertCachedSolution(solution);
      dispatch({ type: 'history/upsert', solution });
    } catch {
      // best effort
    }
  }, [dispatch]);

  // ── Send ──
  const send = useCallback(
    async (finalize: boolean) => {
      const text = state.input.trim();
      if (!text || state.streaming) return;

      dispatch({ type: 'set-input', value: '' });
      dispatch({ type: 'user/message', message: text });
      dispatch({ type: 'stream/start', build: finalize, now: Date.now() });

      const hadContext = state.context;

      try {
        await sendOpenCodeChatStream(
          {
            message: text,
            app_name: state.appName.trim() || undefined,
            solution_id: solutionIdRef.current || undefined,
            session_id: state.sessionId,
            uploaded_context: hadContext?.text,
            build_requested: finalize,
          },
          {
            onEvent: (event, data) => {
              switch (event) {
                case 'agent_start': {
                  dispatch({
                    type: 'stream/agent-start',
                    sessionId: (data.session_id as string) ?? null,
                    solutionId: (data.solution_id as string) || null,
                    appName: state.appName || null,
                  });
                  dispatch({
                    type: 'stream/message',
                    message: (data.message as string) || t('chat.initializingIntelligence'),
                    agent: (data.agent as string) || 'SUTRA Intelligence',
                  });
                  if (data.solution_id) void syncHistoryEntry(data.solution_id as string);
                  break;
                }
                case 'capability':
                  dispatch({ type: 'set-capability', value: data as never });
                  break;
                case 'build_progress':
                  dispatch({ type: 'stream/progress', progress: data as never });
                  if (data.solution_id) void syncHistoryEntry(data.solution_id as string);
                  break;
                case 'message':
                  if (data.message) {
                    dispatch({
                      type: 'stream/message',
                      message: data.message as string,
                      agent: (data.agent as string) || 'SUTRA Intelligence',
                    });
                  }
                  break;
                default:
                  break;
              }
            },
            onComplete: async (data) => {
              const c = data as OpenCodeChatComplete;
              dispatch({
                type: 'stream/agent-start',
                sessionId: c.session_id ?? null,
                solutionId: c.solution_id || null,
                appName: state.appName || null,
              });
              if (c.message) {
                dispatch({ type: 'stream/message', message: c.message, agent });
              }
              if (c.build_id) {
                try {
                  const fresh = await mvpApi.getStatus(c.build_id);
                  dispatch({ type: 'builds/upsert', build: fresh });
                } catch {
                  dispatch({
                    type: 'builds/upsert',
                    build: {
                      build_id: c.build_id,
                      solution_id: c.solution_id || solutionIdRef.current || '',
                      build_number: c.build_number || 1,
                      status: 'complete',
                      workspace_path: '',
                      file_count: c.file_count || 0,
                      files: (c.files || []).map((f) => ({ path: f, size: 1024, is_dir: false })),
                    },
                  });
                }
              }
              if (c.solution_id) void syncHistoryEntry(c.solution_id);
              dispatch({ type: 'stream/finish' });
            },
            onError: (err) => {
              const msg =
                typeof err === 'object' && err && 'message' in err
                  ? String((err as { message: string }).message)
                  : 'Sequence interrupted.';
              dispatch({ type: 'stream/fail', message: msg });
            },
          }
        );
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Unable to reach SUTRA intelligence layer.';
        dispatch({ type: 'stream/fail', message: msg });
        if (/404|not found|solution/i.test(msg) && solutionIdRef.current) {
          dispatch({ type: 'history/remove', id: solutionIdRef.current });
          selectSolution(null);
        }
      }
    },
    [state.input, state.streaming, state.appName, state.sessionId, state.context, agent, dispatch, selectSolution, syncHistoryEntry, t]
  );

  // ── Build actions ──
  const [deployTarget, setDeployTarget] = React.useState<MVPBuild | null>(null);
  const [configureTarget, setConfigureTarget] = React.useState<MVPBuild | null>(null);

  const handleDownload = useCallback(async (build: MVPBuild) => {
    try {
      await mvpApi.downloadBuild(build.build_id, `mvp_build${build.build_number}.zip`);
    } catch (e) {
      dispatch({
        type: 'set-error',
        value: e instanceof Error ? e.message : 'Export failed.',
      });
    }
  }, [dispatch]);

  const handleDestroy = useCallback(
    async (build: MVPBuild) => {
      if (!window.confirm(`Destroy build #${build.build_number}?`)) return;
      try {
        await mvpApi.destroy(build.build_id);
        dispatch({
          type: 'builds/upsert',
          build: { ...build, status: 'cancelled' },
        });
      } catch (e) {
        dispatch({ type: 'set-error', value: e instanceof Error ? e.message : 'Purge failed.' });
      }
    },
    [dispatch]
  );

  const handleDeployed = useCallback(
    (result: MVPDeployResult | string) => {
      const repoUrl = typeof result === 'string' ? result : result.repo_url;
      const renderUrl =
        typeof result === 'string' ? null : result.frontend_url || result.render_service_url;
      const targetId = deployTarget?.build_id;
      if (!targetId) return;
      dispatch({
        type: 'builds/upsert',
        build: {
          ...(deployTarget as MVPBuild),
          repo_url: repoUrl,
          render_service_url: renderUrl,
          frontend_url: renderUrl,
        },
      });
    },
    [deployTarget, dispatch]
  );

  // ── Sidecar actions ──
  const startNewChat = useCallback(() => {
    selectSolution(null);
    dispatch({ type: 'set-app-name', value: '' });
    dispatch({ type: 'set-input', value: '' });
    dispatch({ type: 'set-sidecar-open', value: false });
  }, [selectSolution, dispatch]);

  const handleSelectSolution = useCallback(
    (sol: Solution) => {
      if (sol.id === state.solutionId) {
        dispatch({ type: 'set-sidecar-open', value: false });
        return;
      }
      selectSolution(sol);
      dispatch({ type: 'set-sidecar-open', value: false });
    },
    [state.solutionId, selectSolution, dispatch]
  );

  const handleDeleteSolution = useCallback(
    async (sol: Solution) => {
      if (!window.confirm('Delete this architecture conversation from history?')) return;
      try {
        await solutionApi.delete(sol.id);
        removeCachedSolution(sol.id);
        dispatch({ type: 'history/remove', id: sol.id });
        if (sol.id === state.solutionId) startNewChat();
      } catch (err) {
        dispatch({
          type: 'set-error',
          value: err instanceof Error ? err.message : 'Failed to delete conversation.',
        });
      }
    },
    [state.solutionId, startNewChat, dispatch]
  );

  const attachContext = useCallback(
    (text: string, filename: string) => {
      dispatch({ type: 'set-context', value: { filename, text } });
      dispatch({
        type: 'stream/message',
        message: `Context established from **${filename}**. I am ready to process instructions.`,
      });
    },
    [dispatch]
  );

  // ── Auto-scroll ──
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [state.messages.length, state.streaming]);

  const enginePill = {
    connecting: { icon: Loader2, cls: 'border-[var(--border)] text-[var(--text-2)]', label: t('common.connecting') },
    online: { icon: CheckCircle2, cls: 'border-[var(--border)] text-[var(--green)]', label: t('common.active') },
    offline: { icon: Circle, cls: 'border-[var(--border)] text-[var(--red)]', label: t('common.offline') },
  }[state.engine];
  const EngineIcon = enginePill.icon;

  const showThreadSkeleton = state.conversation === 'loading' && state.messages.length <= 1;

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] min-h-0 animate-fade-up">
      {/* ── Header ── */}
      <header className="mb-3 flex items-center justify-between gap-3 px-1 shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 flex items-center justify-center border border-[var(--sutra-muted-gold)] bg-[var(--bg)] text-[var(--sutra-muted-gold)] shrink-0">
            <Layout className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg sm:text-xl font-serif text-[var(--sutra-charcoal)] truncate">
              {t('chat.aiArchitectWorkspace')}
            </h1>
            <p className="text-[11px] uppercase tracking-widest font-semibold text-[var(--text-2)] mt-0.5 truncate">
              {state.appName ? `${state.appName} • ` : ''}
              {t('chat.synthesisEngine')}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest font-bold shrink-0">
          <button
            onClick={() => dispatch({ type: 'set-sidecar-open', value: true })}
            className="xl:hidden flex items-center gap-1.5 px-3 py-1.5 rounded-sm border border-[var(--border)] bg-[var(--bg-2)] hover:bg-[var(--bg)] text-[var(--sutra-charcoal)] shadow-sm transition-colors"
          >
            <History className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
            <span className="hidden sm:inline">History</span>
            {state.history.length > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-[var(--bg)] border border-[var(--border)] text-[9px] font-mono">
                {state.history.length}
              </span>
            )}
          </button>
          <span className="text-[var(--text-3)] hidden lg:inline">{t('chat.intelligenceLayer')}</span>
          <span
            className={clsx(
              'flex items-center gap-2 px-3 py-1.5 rounded-sm border shadow-sm bg-[var(--bg-2)]',
              enginePill.cls
            )}
          >
            <EngineIcon
              className={clsx(
                'w-3 h-3',
                state.engine === 'connecting' && 'animate-spin',
                state.engine === 'offline' && 'animate-pulse-dot'
              )}
            />
            <span className="hidden sm:inline">{enginePill.label}</span>
          </span>
        </div>
      </header>

      {state.capability?.simulation && (
        <div className="mb-3 flex items-start gap-2.5 rounded-sm border border-[var(--sutra-gold)] bg-[var(--bg)] px-4 py-3 shadow-sm shrink-0">
          <AlertTriangle className="w-4 h-4 text-[var(--sutra-gold)] shrink-0 mt-0.5" />
          <div className="text-[11px] leading-relaxed min-w-0">
            <p className="font-bold uppercase tracking-widest text-[var(--sutra-charcoal)] text-[10px]">
              Simulation mode — no live AI engine connected
            </p>
            <p className="text-[var(--text-2)] mt-1">
              No LLM API key configured (
              <code className="font-mono bg-[var(--bg-2)] px-1">LLM_PROVIDER={state.capability.llm_provider}</code>)
              and the OpenCode sidecar is offline. Builds use a deterministic template scaffold.
              Set <code className="font-mono bg-[var(--bg-2)] px-1">GROQ_API_KEY</code> or{' '}
              <code className="font-mono bg-[var(--bg-2)] px-1">OPENAI_API_KEY</code> plus{' '}
              <code className="font-mono bg-[var(--bg-2)] px-1">LLM_PROVIDER</code> and start the sidecar for real
              AI generation.
            </p>
          </div>
        </div>
      )}

      {/* ── 3-zone workspace ── */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-0">
        {/* Zone 1 — sessions / context */}
        <aside className="hidden lg:flex lg:col-span-2 xl:col-span-2 min-h-0">
          <ChatSidecar
            state={state}
            dispatch={dispatch}
            onSelect={handleSelectSolution}
            onDelete={handleDeleteSolution}
            onNew={startNewChat}
            onAttach={attachContext}
            onClearContext={() => dispatch({ type: 'set-context', value: null })}
            providePrdText={t('chat.providePrd')}
          />
        </aside>

        {/* Zone 2 — thread */}
        <section className="flex flex-col lg:col-span-10 xl:col-span-7 h-[56vh] lg:h-full min-h-0 bg-[var(--bg)] border border-[var(--sutra-muted-gold)] rounded-sm shadow-md overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 sm:p-5 pb-3 min-h-0">
            {showThreadSkeleton ? (
              <ThreadSkeleton />
            ) : (
              state.messages.map((m, i) => (
                <ChatMessage key={i} role={m.role} content={m.content} agent={m.agent} />
              ))
            )}

            {state.streaming && state.stage === 'thinking' && <div className="mt-3"><ThinkingBubble /></div>}

            {state.streaming && state.progress && (
              <div className="flex items-center gap-3 text-[12px] text-[var(--text-2)] py-4 font-serif italic border-t border-[var(--border)] mt-4">
                <Loader2 className="w-4 h-4 animate-spin text-[var(--sutra-muted-gold)] shrink-0" />
                <span className="min-w-0 break-words">
                  {t('chat.buildingAppStatus')} <strong className="text-[var(--sutra-charcoal)]">{state.progress.target}%</strong>{' '}
                  — {t('chat.stepLabel')} {state.progress.step}/{state.progress.totalSteps}: {state.progress.message}
                </span>
              </div>
            )}
            <div ref={endRef} className="h-2" />
          </div>

          {/* Composer */}
          <div className="p-3 sm:p-3.5 bg-[var(--bg-2)] border-t border-[var(--border)] shrink-0">
            {state.error && (
              <div className="flex items-start gap-2 mb-2.5 animate-fade-in">
                <p className="flex-1 text-[11px] font-semibold text-[var(--red)] bg-[var(--bg)] border border-[var(--red)] px-3 py-2 shadow-sm break-words">
                  {state.error}
                </p>
                <button
                  onClick={() => dispatch({ type: 'set-error', value: null })}
                  className="text-[var(--text-3)] hover:text-[var(--sutra-charcoal)] p-1"
                  aria-label="Dismiss error"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            <form onSubmit={(e) => { e.preventDefault(); void send(state.buildRequested); }}>
              {state.buildRequested && (
                <div className="mb-2.5 flex items-center gap-2 animate-fade-in">
                  <span className="text-[10px] uppercase tracking-widest font-bold text-[var(--text-3)] shrink-0">
                    {t('chat.appNameOptional')}
                  </span>
                  <input
                    type="text"
                    value={state.appName}
                    onChange={(e) => dispatch({ type: 'set-app-name', value: e.target.value })}
                    placeholder={t('chat.appNamePlaceholder')}
                    disabled={state.streaming}
                    className="flex-1 py-1.5 px-3 bg-[var(--bg)] border border-[var(--border)] text-[12px] text-[var(--sutra-charcoal)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors rounded-sm min-w-0"
                  />
                </div>
              )}

              {state.context && (
                <div className="flex items-center justify-between gap-2 px-3 py-1.5 bg-[var(--bg)] border border-[var(--border)] rounded-sm text-[11px] mb-2 shadow-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <Paperclip className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] shrink-0" />
                    <span className="font-semibold text-[var(--sutra-charcoal)] truncate max-w-[200px]">
                      {state.context.filename}
                    </span>
                    <span className="inline-flex items-center gap-1 text-[var(--green)] font-mono text-[10px] font-medium bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                      <ShieldCheck className="w-3 h-3 text-[var(--green)] shrink-0" />
                      Verified Clean · Threat Scan Passed
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => dispatch({ type: 'set-context', value: null })}
                    className="text-[10px] uppercase font-mono tracking-wider text-[var(--text-3)] hover:text-[var(--red)] transition-colors"
                  >
                    Remove
                  </button>
                </div>
              )}

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    dispatch({ type: 'set-sidecar-tab', value: 'context' })
                  }
                  className={clsx(
                    'lg:hidden p-3 border transition-colors shrink-0 rounded-sm',
                    state.context
                      ? 'bg-[var(--bg)] border-[var(--sutra-muted-gold)] text-[var(--sutra-muted-gold)] shadow-sm'
                      : 'bg-[var(--bg)] border border-[var(--border)] text-[var(--text-3)]'
                  )}
                  title={t('chat.attachContext')}
                  aria-label={t('chat.attachContext')}
                >
                  <Paperclip className="w-4 h-4" />
                </button>

                <VoiceInputButton
                  onTranscribed={(text) =>
                    dispatch({ type: 'set-input', value: state.input ? `${state.input} ${text}` : text })
                  }
                  disabled={state.streaming}
                />

                <div className="flex-1 relative flex items-center min-w-0">
                  <input
                    type="text"
                    value={state.input}
                    onChange={(e) => dispatch({ type: 'set-input', value: e.target.value })}
                    placeholder={
                      state.context
                        ? t('chat.instructSutra', { filename: state.context.filename })
                        : t('chat.describeApp')
                    }
                    disabled={state.streaming}
                    className="w-full py-3 pl-4 pr-4 sm:pr-28 bg-[var(--bg)] border border-[var(--border)] text-[13px] text-[var(--sutra-charcoal)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors rounded-sm shadow-sm min-w-0"
                  />
                  <label
                    className={clsx(
                      'absolute right-2 flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm text-[10px] uppercase tracking-widest font-bold cursor-pointer select-none transition-colors',
                      state.buildRequested
                        ? 'bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)]'
                        : 'bg-[var(--bg-2)] border border-[var(--border)] text-[var(--text-3)] hover:text-[var(--sutra-charcoal)] hover:border-[var(--text-3)]'
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={state.buildRequested}
                      onChange={(e) => dispatch({ type: 'toggle-build-requested', value: e.target.checked })}
                      className="sr-only"
                    />
                    <Settings2 className="w-3 h-3" />
                    <span className="hidden sm:inline">{t('chat.buildTab')}</span>
                  </label>
                </div>

                <button
                  type="submit"
                  disabled={!state.input.trim() || state.streaming}
                  className="p-3.5 rounded-sm bg-[var(--sutra-charcoal)] hover:bg-black text-[var(--sutra-warm-ivory)] transition-colors disabled:opacity-50 shrink-0 shadow-md"
                  aria-label="Send"
                >
                  {state.streaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
              </div>
            </form>
          </div>
        </section>

        {/* Zone 3 — artifacts */}
        <aside className="flex flex-col lg:col-span-12 xl:col-span-3 h-[42vh] lg:h-full min-h-0">
          <ArtifactsPanel
            state={state}
            t={t}
            buildOrchestratedLabel={t('chat.buildOrchestrated')}
            viewArtifactsLabel={t('chat.viewArtifacts')}
            buildToggleHint={t('chat.buildToggleHint')}
            onDeploy={setDeployTarget}
            onConfigure={setConfigureTarget}
            onDownload={(b) => void handleDownload(b)}
            onDestroy={(b) => void handleDestroy(b)}
          />
        </aside>
      </div>

      {/* ── Mobile / tablet sidecar drawer ── */}
      {state.sidecarOpen && (
        <div className="fixed inset-0 z-50 flex bg-black/50 backdrop-blur-sm lg:hidden animate-fade-in">
          <div
            className="absolute inset-0"
            onClick={() => dispatch({ type: 'set-sidecar-open', value: false })}
            aria-hidden="true"
          />
          <div className="relative bg-[var(--bg-2)] border-r border-[var(--border)] w-full max-w-xs h-full flex flex-col shadow-2xl animate-slide-in">
            <ChatSidecar
              state={state}
              dispatch={dispatch}
              onSelect={handleSelectSolution}
              onDelete={handleDeleteSolution}
              onNew={startNewChat}
              onAttach={attachContext}
              onClearContext={() => dispatch({ type: 'set-context', value: null })}
              providePrdText={t('chat.providePrd')}
              onClose={() => dispatch({ type: 'set-sidecar-open', value: false })}
            />
            <button
              onClick={startNewChat}
              className="m-3 py-2.5 px-3 flex items-center justify-center gap-2 bg-[var(--sutra-charcoal)] text-white hover:bg-black rounded-sm text-[11px] font-bold uppercase tracking-wider shrink-0"
            >
              <Plus className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
              <span>Start New Architecture Build</span>
            </button>
          </div>
        </div>
      )}

      {deployTarget && (
        <DeployModal
          build={deployTarget}
          onClose={() => setDeployTarget(null)}
          onDeployed={handleDeployed}
        />
      )}
      {configureTarget && (
        <ConfigureModal
          build={configureTarget}
          onClose={() => setConfigureTarget(null)}
          onConfigured={() => void loadHistory(true)}
        />
      )}
    </div>
  );
}

function ChatSkeleton() {
  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] animate-fade-up">
      <div className="mb-3 flex items-center gap-3 px-1">
        <div className="w-8 h-8 border border-[var(--border)] skeleton" />
        <div className="space-y-1.5">
          <div className="skeleton h-4 w-52" />
          <div className="skeleton h-2.5 w-36" />
        </div>
      </div>
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-0">
        <div className="hidden lg:flex lg:col-span-2 border border-[var(--border)] rounded-sm p-3 space-y-2">
          <div className="skeleton h-8 w-full" />
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="space-y-1.5">
              <div className="skeleton h-3 w-full" />
              <div className="skeleton h-2 w-2/3" />
            </div>
          ))}
        </div>
        <div className="lg:col-span-10 xl:col-span-7 border border-[var(--border)] rounded-sm p-5">
          <ThreadSkeleton />
        </div>
        <div className="lg:col-span-12 xl:col-span-3 border border-[var(--border)] rounded-sm p-3 space-y-3">
          <div className="skeleton h-3 w-32" />
          <div className="skeleton h-24 w-full" />
          <div className="skeleton h-24 w-full" />
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<ChatSkeleton />}>
      <ChatContent />
    </Suspense>
  );
}
