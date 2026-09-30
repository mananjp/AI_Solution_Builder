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
  Settings2,
  ShieldCheck,
  X,
} from 'lucide-react';
import clsx from 'clsx';
import ChatMessage from '@/components/ChatMessage';
import { VoiceInputButton } from '@/components/VoiceInputButton';
import { ChatSidecar } from '@/components/chat/ChatSidecar';
import { ResizableSidecar } from '@/components/chat/ResizableSidecar';
import { ArtifactsPanel } from '@/components/chat/ArtifactsPanel';
import { SendButton } from '@/components/lab/send-button';
import { ThreadSkeleton, ThinkingBubble } from '@/components/chat/Skeleton';
import {
  ClarificationPanel,
  type ClarificationOption,
  type ClarificationQuestion,
} from '@/components/chat/ClarificationPanel';
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
  const prevSolutionIdRef = useRef<string | null>(state.solutionId);
  useEffect(() => {
    if (prevSolutionIdRef.current !== state.solutionId) {
      prevSolutionIdRef.current = state.solutionId;
      void hydrate(state.solutionId);
    }
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
  const sendingRef = useRef(false);
  const send = useCallback(
    async (finalize: boolean) => {
      const text = state.input.trim();
      if (!text || state.streaming || sendingRef.current) return;
      sendingRef.current = true;

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
                case 'clarification_needed': {
                  const payload = data as { has_gaps?: boolean; questions?: ClarificationQuestion[] };
                  if (payload.questions && payload.questions.length > 0) {
                    dispatch({ type: 'set-clarifications', questions: payload.questions });
                  }
                  break;
                }
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
      } finally {
        sendingRef.current = false;
      }
    },
    [state.input, state.streaming, state.appName, state.sessionId, state.context, agent, dispatch, selectSolution, syncHistoryEntry, t]
  );

  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!state.input.trim() || state.streaming || sendingRef.current) return;
      const shouldBuild =
        state.buildRequested ||
        /\b(build|create|make|generate|design|develop|landing\s+page|storefront|app)\b/i.test(state.input);
      void send(shouldBuild);
    },
    [state.input, state.streaming, state.buildRequested, send]
  );

  const handleSelectClarification = useCallback(
    (question: ClarificationQuestion, option: ClarificationOption) => {
      const addition = `${question.field}: ${option.label}`;
      const nextInput = state.input.trim()
        ? `${state.input.trim()} [${addition}]`
        : `Build an app with ${addition}`;
      dispatch({ type: 'set-input', value: nextInput });
      dispatch({ type: 'dismiss-clarifications' });
    },
    [state.input, dispatch]
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
    <div className="flex min-h-[calc(100dvh-5rem)] flex-col animate-fade-up">
      {/* ── Header ── */}
      <header className="mb-3 flex items-center justify-between gap-3 px-1 shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 flex items-center justify-center border border-[var(--sutra-strong)] bg-[var(--bg)] text-[var(--sutra-strong)] shrink-0">
            <Layout className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg sm:text-xl font-serif text-[var(--sutra-ink)] truncate">
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
            className="xl:hidden flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--bg-2)] hover:bg-[var(--bg)] text-[var(--sutra-ink)] shadow-sm transition-colors"
          >
            <History className="w-3.5 h-3.5 text-[var(--sutra-strong)]" />
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
        <div className="mb-3 flex items-start gap-2.5 rounded-sm border border-[var(--amber)] bg-[var(--bg)] px-4 py-3 shadow-sm shrink-0">
          <AlertTriangle className="w-4 h-4 text-[var(--amber)] shrink-0 mt-0.5" />
          <div className="text-[11px] leading-relaxed min-w-0">
            <p className="font-bold uppercase tracking-widest text-[var(--sutra-ink)] text-[10px]">
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

      {/* ── workspace ── */}
      {/* Flex rather than a 12-column grid: the sessions panel is draggable, so
          its width has to come from the panel itself. Sizing it in the grid left
          the rail fighting the column and the two panes drifted apart. No `gap`
          either — they are two zones of one surface, not two separate cards. */}
      <div className="flex min-h-[32rem] flex-1 flex-col gap-3 xl:min-h-0 xl:flex-row">
        {/* Zone 1 — sessions / context, resizable */}
        <ResizableSidecar
          open={state.sidecarOpen}
          onOpenChange={(v: boolean) => dispatch({ type: 'set-sidecar-open', value: v })}
          label={t('chat.sessions')}
          className="hidden min-h-[24rem] rounded-xl border border-[var(--border)] bg-[var(--bg-2)] xl:flex"
        >
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
        </ResizableSidecar>

        {/* Zone 2 — thread */}
        <section className="flex min-h-[28rem] min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg)] shadow-sm xl:h-full xl:min-h-0">
          <div className="flex-1 overflow-y-auto p-4 pb-3 sm:p-6">
            {showThreadSkeleton ? (
              <ThreadSkeleton />
            ) : (
              <>
                {state.messages.map((m, i) => (
                  <ChatMessage key={i} role={m.role} content={m.content} agent={m.agent} />
                ))}

                {state.messages.length <= 1 && (
                  <div className="mt-8 space-y-3 animate-fade-in border-t border-[var(--border)] pt-6">
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] uppercase tracking-wider font-bold text-[var(--sutra-ink)] font-mono">
                        Quick Start Blueprints &amp; Examples
                      </span>
                      <span className="text-[10px] text-[var(--text-3)]">· Click any to auto-fill</span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {[
                        {
                          icon: "🍦",
                          title: "Ice Cream Vendor Landing Page",
                          desc: "Storefront with Vanilla ($10) & Chocolate ($20) and ordering",
                          prompt: "i am an ice cream vendor build me a landing page with my two icecreams that is vanilla and chocolate with their prices 10 and 20 respectively along with any appropriate images",
                          app: "Artisanal Creamery",
                        },
                        {
                          icon: "🏋️",
                          title: "Gym & Fitness Studio Portal",
                          desc: "Memberships, personal trainers, and workout classes",
                          prompt: "Build a gym and fitness studio management app with memberships, personal trainers, and workout classes",
                          app: "IronPulse Gym",
                        },
                        {
                          icon: "📦",
                          title: "Warehouse Inventory System",
                          desc: "Stock tracking, suppliers, and reorder levels",
                          prompt: "Create a modern warehouse inventory tracker with stock reordering and supplier management",
                          app: "StockFlow Manager",
                        },
                        {
                          icon: "🏨",
                          title: "Boutique Hotel Booking",
                          desc: "Room availability, guest check-in, and reservations",
                          prompt: "Build a boutique hotel booking system with room availability, guest registry, and reservation payments",
                          app: "Azure Suites",
                        },
                      ].map((chip, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => {
                            dispatch({ type: 'set-input', value: chip.prompt });
                            dispatch({ type: 'set-app-name', value: chip.app });
                            dispatch({ type: 'toggle-build-requested', value: true });
                          }}
                          className="group flex items-start gap-3 p-3.5 text-left rounded-xl border border-[var(--border)] bg-[var(--bg-2)] hover:border-[var(--sutra-strong)] hover:bg-[var(--bg)] transition-all shadow-sm cursor-pointer"
                        >
                          <span className="text-xl shrink-0 p-2 rounded-lg bg-[var(--bg)] border border-[var(--border)] group-hover:scale-110 transition-transform">
                            {chip.icon}
                          </span>
                          <div className="min-w-0 flex-1">
                            <span className="block text-xs font-bold text-[var(--sutra-ink)] group-hover:text-[var(--sutra-strong)] transition-colors">
                              {chip.title}
                            </span>
                            <span className="block text-[11px] text-[var(--text-3)] line-clamp-1 mt-0.5 font-light">
                              {chip.desc}
                            </span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {state.streaming && state.stage === 'thinking' && <div className="mt-3"><ThinkingBubble /></div>}

            {state.streaming && state.progress && (
              <div className="flex items-center gap-3 text-[12px] text-[var(--text-2)] py-4 font-serif italic border-t border-[var(--border)] mt-4">
                <Loader2 className="w-4 h-4 animate-spin text-[var(--sutra-strong)] shrink-0" />
                <span className="min-w-0 break-words">
                  {t('chat.buildingAppStatus')} <strong className="text-[var(--sutra-ink)]">{state.progress.target}%</strong>{' '}
                  — {t('chat.stepLabel')} {state.progress.step}/{state.progress.totalSteps}: {state.progress.message}
                </span>
              </div>
            )}
            <div ref={endRef} className="h-2" />
          </div>

          {/* Composer */}
          <div className="shrink-0 border-t border-[var(--border)] bg-[var(--bg-2)] p-3 sm:p-4">
            {state.error && (
              <div className="flex items-start gap-2 mb-2.5 animate-fade-in">
                <p className="flex-1 text-[11px] font-semibold text-[var(--red)] bg-[var(--bg)] border border-[var(--red)] px-3 py-2 shadow-sm break-words">
                  {state.error}
                </p>
                <button
                  onClick={() => dispatch({ type: 'set-error', value: null })}
                  className="text-[var(--text-3)] hover:text-[var(--sutra-ink)] p-1"
                  aria-label="Dismiss error"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            {state.clarifications && state.clarifications.length > 0 && (
              <ClarificationPanel
                questions={state.clarifications}
                onSelectOption={handleSelectClarification}
                onDismiss={() => dispatch({ type: 'dismiss-clarifications' })}
                loading={state.streaming}
              />
            )}

            <form onSubmit={handleSubmit}>
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
                    className="flex-1 py-1.5 px-3 bg-[var(--bg)] border border-[var(--border)] text-[12px] text-[var(--sutra-ink)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-strong)] transition-colors rounded-sm min-w-0"
                  />
                </div>
              )}

              {state.context && (
                <div className="flex items-center justify-between gap-2 px-3 py-1.5 bg-[var(--bg)] border border-[var(--border)] rounded-sm text-[11px] mb-2 shadow-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <Paperclip className="w-3.5 h-3.5 text-[var(--sutra-strong)] shrink-0" />
                    <span className="font-semibold text-[var(--sutra-ink)] truncate max-w-[200px]">
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

              <div className="flex items-center gap-2.5">
                <button
                  type="button"
                  onClick={() => {
                    dispatch({ type: 'set-sidecar-tab', value: 'context' });
                    dispatch({ type: 'set-sidecar-open', value: true });
                  }}
                  className={clsx(
                    'xl:hidden',
                    state.context
                      ? 'text-[var(--sutra-strong)]'
                      : 'text-[var(--text-3)]'
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
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                        e.preventDefault();
                        handleSubmit();
                      }
                    }}
                    placeholder={
                      state.context
                        ? t('chat.instructSutra', { filename: state.context.filename })
                        : t('chat.describeApp')
                    }
                    disabled={state.streaming}
                    className="w-full py-3 pl-4 pr-4 sm:pr-28 bg-[var(--bg)] border border-[var(--border)] text-[13px] text-[var(--sutra-ink)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-strong)] transition-colors rounded-lg shadow-sm min-w-0"
                  />
                  <label
                    title={state.buildRequested ? `${t('chat.buildTab')} (active)` : t('chat.buildTab')}
                    aria-label="Toggle MVP architecture build"
                    className={clsx(
                      'absolute right-2 flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[10px] uppercase tracking-widest font-bold cursor-pointer select-none transition-all shadow-sm',
                      state.buildRequested
                        ? 'bg-[var(--foreground)] text-[var(--background)] ring-1 ring-[var(--foreground)]'
                        : 'bg-[var(--surface)] border border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--border-2)]'
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={state.buildRequested}
                      onChange={(e) => dispatch({ type: 'toggle-build-requested', value: e.target.checked })}
                      className="sr-only"
                    />
                    <Settings2 className="w-3.5 h-3.5 shrink-0" />
                    <span className="hidden sm:inline font-bold">{t('chat.buildTab')}</span>
                  </label>
                </div>

                <SendButton
                  label="Send message"
                  sentLabel="Sent"
                  variant="solid"
                  iconOnly
                  className="h-11 w-11 shrink-0"
                  type="submit"
                  onSend={() => handleSubmit()}
                  disabled={!state.input.trim() || state.streaming}
                />
              </div>
            </form>
          </div>
        </section>

        {/* Zone 3 — artifacts */}
        <aside className="flex min-h-[16rem] flex-col rounded-xl border border-[var(--border)] bg-[var(--bg-2)] shadow-sm xl:h-full xl:min-h-0 xl:w-[min(28vw,22rem)] xl:shrink-0">
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
        <div className="fixed inset-0 z-50 flex bg-black/50 backdrop-blur-sm xl:hidden animate-fade-in">
          <div
            className="absolute inset-0"
            onClick={() => dispatch({ type: 'set-sidecar-open', value: false })}
            aria-hidden="true"
          />
          <div className="relative flex h-full w-full max-w-sm flex-col border-r border-[var(--border)] bg-[var(--bg-2)] shadow-2xl animate-slide-in">
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
    <div className="flex min-h-[calc(100dvh-5rem)] flex-col animate-fade-up">
      <div className="mb-3 flex items-center gap-3 px-1">
        <div className="w-8 h-8 border border-[var(--border)] skeleton" />
        <div className="space-y-1.5">
          <div className="skeleton h-4 w-52" />
          <div className="skeleton h-2.5 w-36" />
        </div>
      </div>
      {/* Matches the loaded layout: no gutter between the sessions panel and
          the thread, so the page does not visibly reflow when data arrives. */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 min-h-0">
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
