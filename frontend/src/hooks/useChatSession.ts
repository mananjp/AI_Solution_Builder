'use client';

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { mvpApi, solutionApi, workspaceApi } from '@/lib/api';
import type { MVPBuild, OpenCodeBuildProgress, Solution } from '@/types';

export type ChatRole = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  role: ChatRole;
  content: string;
  agent?: string;
}

export interface BuildCapability {
  sidecar_online: boolean;
  llm_provider: string;
  llm_authenticated: boolean;
  simulation: boolean;
  mode: string;
}

export interface Milestone {
  key: string;
  index: number;
  status: 'pending' | 'active' | 'completed';
}

export interface BuildProgress {
  phase: string;
  step: number;
  totalSteps: number;
  /** Real percentage reported by the build pipeline (0-100). */
  target: number;
  message: string;
  steps: Milestone[];
  logs: string[];
  startedAt: number;
  buildId: string | null;
  fileCount: number | null;
}

export type EngineStatus = 'connecting' | 'online' | 'offline';
export type AsyncStatus = 'idle' | 'loading' | 'ready' | 'error';
export type StreamStage = 'idle' | 'thinking' | 'building';

export interface ChatState {
  // ── Identity ────────────────────────────────────────────
  solutionId: string | null;
  appName: string;
  sessionId: string | null;

  // ── Conversation ────────────────────────────────────────
  messages: ChatMessage[];
  input: string;
  context: { filename: string; text: string } | null;
  conversation: AsyncStatus;

  // ── Stream ──────────────────────────────────────────────
  streaming: boolean;
  stage: StreamStage;
  error: string | null;

  // ── Build ───────────────────────────────────────────────
  buildRequested: boolean;
  progress: BuildProgress | null;
  builds: MVPBuild[];
  buildsStatus: AsyncStatus;

  // ── Engine ──────────────────────────────────────────────
  engine: EngineStatus;
  capability: BuildCapability | null;

  // ── Sidecar ─────────────────────────────────────────────
  history: Solution[];
  historyStatus: AsyncStatus;
  historyQuery: string;
  sidecarTab: 'history' | 'context';
  sidecarOpen: boolean;
}

export const initialChatState: ChatState = {
  solutionId: null,
  appName: '',
  sessionId: null,
  messages: [],
  input: '',
  context: null,
  conversation: 'idle',
  streaming: false,
  stage: 'idle',
  error: null,
  buildRequested: false,
  progress: null,
  builds: [],
  buildsStatus: 'idle',
  engine: 'connecting',
  capability: null,
  history: [],
  historyStatus: 'idle',
  historyQuery: '',
  sidecarTab: 'history',
  sidecarOpen: false,
};

export type ChatAction =
  | { type: 'set-input'; value: string }
  | { type: 'set-app-name'; value: string }
  | { type: 'toggle-build-requested'; value?: boolean }
  | { type: 'set-sidecar-tab'; value: 'history' | 'context' }
  | { type: 'set-history-query'; value: string }
  | { type: 'set-sidecar-open'; value: boolean }
  | { type: 'set-engine'; value: EngineStatus }
  | { type: 'set-capability'; value: BuildCapability | null }
  | { type: 'set-error'; value: string | null }
  | { type: 'set-context'; value: { filename: string; text: string } | null }
  // History
  | { type: 'history/loading' }
  | { type: 'history/loaded'; items: Solution[] }
  | { type: 'history/failed' }
  | { type: 'history/upsert'; solution: Solution }
  | { type: 'history/remove'; id: string }
  // Conversation lifecycle
  | { type: 'conversation/loading' }
  | { type: 'conversation/loaded'; solution: Solution; agent: string; welcome: string }
  | { type: 'conversation/empty'; welcome: string }
  | { type: 'conversation/failed' }
  | { type: 'activate'; solutionId: string | null; appName?: string; welcome: string }
  // Stream
  | { type: 'stream/start'; build: boolean; now: number }
  | { type: 'stream/agent-start'; sessionId: string | null; solutionId: string | null; appName?: string | null }
  | { type: 'user/message'; message: string }
  | { type: 'stream/message'; message: string; agent?: string }
  | { type: 'stream/progress'; progress: OpenCodeBuildProgress }
  | { type: 'stream/finish' }
  | { type: 'stream/fail'; message: string }
  // Builds
  | { type: 'builds/loading' }
  | { type: 'builds/loaded'; builds: MVPBuild[] }
  | { type: 'builds/upsert'; build: MVPBuild };

// ── Build phase model ─────────────────────────────────────
// Mirrors the phases the backend actually emits (app/api/opencode_chat.py).
// `designing` is a sub-phase of `scaffolding` — both map to milestone 3.
export const BUILD_PHASES = [
  'analyzing',
  'persisting',
  'scaffolding',
  'designing',
  'coding',
  'illustrating',
  'verifying',
  'packaging',
  'completed',
] as const;

export type BuildPhase = (typeof BUILD_PHASES)[number];

const PHASE_MILESTONE: Record<string, number> = {
  analyzing: 0,
  persisting: 1,
  scaffolding: 2,
  designing: 2,
  coding: 3,
  illustrating: 4,
  verifying: 5,
  packaging: 6,
  completed: 7,
};

export const TOTAL_MILESTONES = 7;

/** Derive the milestone checklist from the last observed phase. */
export function milestonesFromPhase(phase: string, _target: number, done: boolean): Milestone[] {
  const current = PHASE_MILESTONE[phase] ?? 0;
  return Array.from({ length: TOTAL_MILESTONES }, (_, i) => ({
    key: `m${i + 1}`,
    index: i,
    status: (done || i < current ? 'completed' : i === current ? 'active' : 'pending') as Milestone['status'],
  }));
}

function appendLog(progress: BuildProgress | null, message: string): BuildProgress {
  const startedAt = progress?.startedAt ?? Date.now();
  const seconds = Math.round((Date.now() - startedAt) / 1000);
  const previous = progress?.logs ?? [];
  const last = previous[previous.length - 1];
  if (last && last.slice(last.indexOf('] ') + 2) === message) return progress!;
  return { ...(progress as BuildProgress), logs: [...previous, `[${seconds}s] ${message}`] };
}

function reduce(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'set-input':
      return { ...state, input: action.value };

    case 'set-app-name':
      return { ...state, appName: action.value };

    case 'toggle-build-requested':
      return { ...state, buildRequested: action.value ?? !state.buildRequested };

    case 'set-sidecar-tab':
      return { ...state, sidecarTab: action.value, sidecarOpen: true };

    case 'set-history-query':
      return { ...state, historyQuery: action.value };

    case 'set-sidecar-open':
      return { ...state, sidecarOpen: action.value };

    case 'set-engine':
      return state.engine === action.value ? state : { ...state, engine: action.value };

    case 'set-capability':
      return { ...state, capability: action.value };

    case 'set-error':
      return { ...state, error: action.value };

    case 'set-context':
      return { ...state, context: action.value };

    case 'history/loading':
      return { ...state, historyStatus: 'loading' };

    case 'history/loaded':
      return { ...state, history: action.items, historyStatus: 'ready' };

    case 'history/failed':
      return { ...state, historyStatus: 'error' };

    case 'history/upsert': {
      const next = [
        action.solution,
        ...state.history.filter((s) => s.id !== action.solution.id),
      ].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at));
      return { ...state, history: next };
    }

    case 'history/remove':
      return { ...state, history: state.history.filter((s) => s.id !== action.id) };

    case 'conversation/loading':
      return { ...state, conversation: 'loading' };

    case 'conversation/loaded': {
      const { solution, agent } = action;
      const history = solution.conversation_history ?? [];
      return {
        ...state,
        conversation: 'ready',
        sessionId: typeof solution.ai_state?.opencode_session_id === 'string'
          ? solution.ai_state.opencode_session_id
          : state.sessionId,
        appName: solution.title || state.appName,
        messages: history.length
          ? history.map((m) => ({
              role: (m.role as ChatRole) || 'assistant',
              content: m.content || '',
              agent: m.role === 'assistant' ? agent : undefined,
            }))
          : [{ role: 'assistant', agent, content: action.welcome }],
      };
    }

    case 'conversation/empty':
      return {
        ...state,
        conversation: 'ready',
        sessionId: null,
        appName: '',
        messages: [{ role: 'assistant', content: action.welcome }],
      };

    case 'conversation/failed':
      return { ...state, conversation: 'error' };

    case 'activate':
      // Single place where the active conversation changes. Everything that must
      // NOT survive a conversation switch is reset here — that was the sidecar bug.
      return {
        ...state,
        solutionId: action.solutionId,
        appName: action.appName ?? '',
        sessionId: null,
        messages: [{ role: 'assistant', content: action.welcome }],
        context: null,
        conversation: action.solutionId ? 'loading' : 'ready',
        streaming: false,
        stage: 'idle',
        error: null,
        progress: null,
        builds: [],
        buildsStatus: action.solutionId ? 'loading' : 'ready',
        buildRequested: false,
      };

    case 'stream/start':
      return {
        ...state,
        streaming: true,
        stage: action.build ? 'building' : 'thinking',
        error: null,
        progress: action.build
          ? {
              phase: 'analyzing',
              step: 1,
              totalSteps: TOTAL_MILESTONES,
              target: 0,
              message: 'Queueing build pipeline…',
              steps: milestonesFromPhase('analyzing', 0, false),
              logs: ['[0s] Build request accepted by the orchestrator.'],
              startedAt: action.now,
              buildId: null,
              fileCount: null,
            }
          : null,
      };

    case 'stream/agent-start': {
      const next: ChatState = { ...state, sessionId: action.sessionId ?? state.sessionId };
      if (action.solutionId && action.solutionId !== state.solutionId) {
        next.solutionId = action.solutionId;
        next.builds = [];
        next.buildsStatus = 'loading';
        next.conversation = 'ready';
      }
      if (action.appName && !next.appName) next.appName = action.appName;
      return next;
    }

    case 'user/message':
      return { ...state, messages: [...state.messages, { role: 'user', content: action.message }] };

    case 'stream/message':
      return {
        ...state,
        messages: [...state.messages, { role: 'assistant', content: action.message, agent: action.agent }],
      };

    case 'stream/progress': {
      const p = action.progress;
      const target = Math.max(0, Math.min(100, p.percentage ?? 0));
      const done = p.phase === 'completed' || target >= 100;
      const base: BuildProgress = {
        phase: p.phase || 'building',
        step: p.step || 1,
        totalSteps: TOTAL_MILESTONES,
        target,
        message: p.message || 'Building application…',
        steps: milestonesFromPhase(p.phase || 'analyzing', target, done),
        logs: state.progress?.logs ?? [],
        startedAt: state.progress?.startedAt ?? Date.now(),
        buildId: p.build_id ?? state.progress?.buildId ?? null,
        fileCount: p.file_count ?? state.progress?.fileCount ?? null,
      };

      // The backend registers the build row before the pipeline starts, so the
      // artifact card can appear immediately with a real stepper instead of
      // popping into existence at 100%.
      const buildId = base.buildId;
      let builds = state.builds;
      if (buildId && !builds.some((b) => b.build_id === buildId)) {
        builds = [
          {
            build_id: buildId,
            solution_id: p.solution_id ?? state.solutionId ?? '',
            build_number: (builds[0]?.build_number ?? 0) + 1,
            status: done ? 'complete' : 'building',
            workspace_path: '',
            file_count: base.fileCount ?? 0,
            files: [],
            progress: {
              stage: base.phase,
              step: base.step,
              total_steps: base.totalSteps,
              percentage: target,
              message: base.message,
            },
          },
          ...builds,
        ];
      } else if (buildId) {
        builds = builds.map((b) =>
          b.build_id === buildId && b.progress?.percentage !== target
            ? {
                ...b,
                status: done ? 'complete' : 'building',
                progress: {
                  ...(b.progress ?? {}),
                  stage: base.phase,
                  step: base.step,
                  total_steps: base.totalSteps,
                  percentage: target,
                  message: base.message,
                },
              }
            : b
        );
      }

      return { ...state, stage: 'building', progress: appendLog(base, base.message), builds };
    }

    case 'stream/finish':
      return {
        ...state,
        streaming: false,
        stage: 'idle',
        buildRequested: false,
        progress: null,
      };

    case 'stream/fail':
      return {
        ...state,
        streaming: false,
        stage: 'idle',
        error: action.message,
        progress: null,
        messages: [...state.messages, { role: 'assistant', content: action.message }],
      };

    case 'builds/loading':
      return state.buildsStatus === 'loading' ? state : { ...state, buildsStatus: 'loading' };

    case 'builds/loaded':
      return { ...state, builds: action.builds, buildsStatus: 'ready' };

    case 'builds/upsert':
      return {
        ...state,
        buildsStatus: 'ready',
        builds: [
          action.build,
          ...state.builds.filter((b) => b.build_id !== action.build.build_id),
        ],
      };

    default:
      return state;
  }
}

// ── Module-level solution cache (survives remounts → instant history) ──
let cachedSolutions: Solution[] = [];
let cacheStamp = 0;
let inflight: Promise<Solution[]> | null = null;
const CACHE_TTL_MS = 30_000;

export function peekSolutions(): Solution[] | null {
  return cacheStamp ? cachedSolutions : null;
}

async function fetchAllSolutions(): Promise<Solution[]> {
  const workspaces = await workspaceApi.list();
  if (!workspaces?.length) return [];
  const perWorkspace = await Promise.all(
    workspaces.map((ws) => solutionApi.list(ws.id).catch(() => [] as Solution[]))
  );
  return perWorkspace
    .flat()
    .sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at));
}

export function primeSolutions(items: Solution[]) {
  cachedSolutions = items;
  cacheStamp = Date.now();
}

export function upsertCachedSolution(solution: Solution) {
  cachedSolutions = [
    solution,
    ...cachedSolutions.filter((s) => s.id !== solution.id),
  ].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at));
  cacheStamp = Date.now();
}

export function removeCachedSolution(id: string) {
  cachedSolutions = cachedSolutions.filter((s) => s.id !== id);
  cacheStamp = Date.now();
}

export function refreshSolutions(force = false): Promise<Solution[]> {
  if (inflight) return inflight;
  if (!force && cacheStamp && Date.now() - cacheStamp < CACHE_TTL_MS) {
    return Promise.resolve(cachedSolutions);
  }
  inflight = fetchAllSolutions()
    .then((items) => {
      cachedSolutions = items;
      cacheStamp = Date.now();
      return items;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

// ── Smoothed progress ─────────────────────────────────────
// The pipeline has genuinely long silent stretches (LLM spec design, code
// verification). We ease the bar toward the last *reported* percentage and never
// overshoot it — a bar that lies about progress is worse than a slow one. Liveness
// during those stretches is communicated by ``useProgressStalled`` (an
// indeterminate shimmer), and the milestone checklist only ticks on real events.

export function useSmoothProgress(target: number, active: boolean) {
  const [display, setDisplay] = useState(0);
  const targetRef = useRef(target);
  const displayRef = useRef(0);

  useEffect(() => {
    targetRef.current = target;
  }, [target]);

  useEffect(() => {
    if (!active) return;
    const tick = () => {
      const goal = targetRef.current;
      if (displayRef.current === goal) return;
      // Fast ease toward the newly reported value, snapping once close enough
      // that the remainder would only produce sub-pixel jitter.
      const next = displayRef.current + (goal - displayRef.current) * 0.35;
      displayRef.current = goal - next < 0.4 ? goal : next;
      setDisplay(displayRef.current);
    };

    const timer = setInterval(tick, 120);
    return () => clearInterval(timer);
  }, [active]);

  return active ? display : target;
}

/**
 * Percentage the pipeline reports when each milestone is reached.
 *
 * Index = milestone number - 1, so `MILESTONE_PERCENT[i]` is the value reported
 * once milestone `i` completes. Mirrors the emissions in
 * `app/api/opencode_chat.py` (analyzing 10, persisting 30, scaffolding 50,
 * designing 55, coding 70, illustrating 78, verifying 88, packaging 93, done 100).
 */
export const MILESTONE_PERCENT = [30, 50, 70, 78, 88, 93, 100] as const;

/**
 * Progress that never looks frozen.
 *
 * `useSmoothProgress` on its own is not enough: the pipeline reports a fixed
 * percentage for an entire phase, and the two LLM-bound phases (designing the
 * domain, then generating models/schemas/routers) can run for minutes. The bar
 * therefore sat on one number and then snapped to the next, which reads as
 * "stuck at 0%, then suddenly 100%".
 *
 * So the displayed value chases two things at once:
 *  1. the real reported `target`, which always wins when it moves, and
 *  2. an asymptotic creep toward the *next milestone's* percentage as time
 *     passes within the current phase.
 *
 * The creep deliberately stops 1.5 points short of the next milestone: it shows
 * that work is happening without ever claiming a milestone was reached, so the
 * checklist and the real numbers stay honest.
 */
export function useLiveProgress(target: number, active: boolean, milestoneIndex: number) {
  const real = useSmoothProgress(target, active);

  const ceiling = useMemo(() => {
    const next = MILESTONE_PERCENT[Math.min(Math.max(milestoneIndex, 0), MILESTONE_PERCENT.length - 1)];
    return Math.min(next - 1.5, 99);
  }, [milestoneIndex]);

  const [creep, setCreep] = useState(0);
  // Reset the creep window whenever a new real value lands, so time is measured
  // "since the last thing the pipeline actually told us".
  const lastTarget = useRef(target);
  const since = useRef(0);

  useEffect(() => {
    if (lastTarget.current !== target) {
      lastTarget.current = target;
      since.current = 0;
    }
  }, [target]);

  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => {
      since.current += 1;
      // 1 - e^(-t/18) over 1s ticks: fast at first, then asymptotic, so the bar
      // keeps inching forward for minutes without ever hitting the ceiling.
      const elapsed = since.current;
      setCreep(1 - Math.exp(-elapsed / 18));
    }, 1000);
    return () => clearInterval(timer);
  }, [active]);

  if (!active) return target;

  const floor = Math.min(target, ceiling);
  const crept = floor + (ceiling - floor) * creep;
  return Math.max(real, crept);
}

/**
 * True once the build has been silent for `idleAfterMs` — i.e. the displayed
 * percentage has stopped moving even though the build is still running.
 *
 * Derived from a slow clock rather than a one-shot timer so a stalled bar can
 * also recover if the pipeline goes quiet and then reports again.
 */
export function useProgressStalled(target: number, active: boolean, idleAfterMs = 2500) {
  const targetRef = useRef(target);
  const [stall, setStall] = useState<{ since: number; at: number } | null>(null);

  useEffect(() => {
    targetRef.current = target;
  }, [target]);

  useEffect(() => {
    if (!active) return;
    let lastSeen = targetRef.current;
    let since = Date.now();
    const timer = setInterval(() => {
      const at = Date.now();
      // A new percentage from the pipeline resets the silence window.
      if (targetRef.current !== lastSeen) {
        lastSeen = targetRef.current;
        since = at;
      }
      setStall((prev) => (prev?.since === since && prev.at === at ? prev : { since, at }));
    }, 500);
    return () => {
      clearInterval(timer);
      setStall(null);
    };
  }, [active]);

  if (!active || !stall) return false;
  return stall.at - stall.since >= idleAfterMs;
}

// ── Hook ──────────────────────────────────────────────────

export interface UseChatSessionOptions {
  welcome: string;
  agent: string;
  initialPrompt?: string;
  initialSolutionId?: string | null;
  initialAppName?: string;
  startNew?: boolean;
}

export function useChatSession(options: UseChatSessionOptions) {
  const { welcome, agent, initialPrompt = '', initialSolutionId = null, initialAppName = '', startNew = false } = options;
  const [state, dispatch] = useReducer(reduce, initialChatState, (base): ChatState => ({
    ...base,
    input: initialPrompt,
    solutionId: startNew ? null : initialSolutionId,
    appName: startNew ? '' : initialAppName,
    messages: [{ role: 'assistant', agent, content: welcome }],
    conversation: startNew || !initialSolutionId ? 'ready' : 'loading',
    buildsStatus: startNew || !initialSolutionId ? 'ready' : 'loading',
  }));

  const loadedRef = useRef<string | null>(null);
  const bootedRef = useRef(false);

  // ── History: cached first, network second (stale-while-revalidate) ──
  const loadHistory = useCallback(async (force = false) => {
    const cached = peekSolutions();
    if (cached) {
      dispatch({ type: 'history/loaded', items: cached });
      if (!force) {
        void refreshSolutions().then((items) => {
          dispatch({ type: 'history/loaded', items });
        });
        return;
      }
    }
    dispatch({ type: 'history/loading' });
    try {
      const items = await refreshSolutions(force);
      dispatch({ type: 'history/loaded', items });
    } catch {
      dispatch({ type: 'history/failed' });
    }
  }, []);

  // ── Conversation hydration: keyed ONLY on state.solutionId ──
  // This is the fix for "switching chat does not change the chat": the active
  // id is React state (updated synchronously), never a frozen search param.
  const hydrate = useCallback(
    async (solutionId: string | null) => {
      if (!solutionId) {
        loadedRef.current = null;
        dispatch({ type: 'conversation/empty', welcome });
        dispatch({ type: 'builds/loaded', builds: [] });
        return;
      }
      if (loadedRef.current === solutionId) return;
      loadedRef.current = solutionId;
      dispatch({ type: 'conversation/loading' });
      dispatch({ type: 'builds/loading' });
      try {
        const [solution, builds] = await Promise.all([
          solutionApi.get(solutionId),
          // Build history is decorative here — never let it block the thread.
          mvpApi.listBuilds(solutionId).catch(() => [] as MVPBuild[]),
        ]);
        const sorted = [...builds].sort((a, b) => (b.build_number || 0) - (a.build_number || 0));
        dispatch({ type: 'builds/loaded', builds: sorted });
        dispatch({ type: 'conversation/loaded', solution, agent, welcome });
        upsertCachedSolution(solution);
      } catch {
        loadedRef.current = null;
        dispatch({ type: 'conversation/failed' });
        dispatch({ type: 'builds/loaded', builds: [] });
      }
    },
    [agent, welcome]
  );

  // ── Boot: pick the initial conversation once ──
  useEffect(() => {
    if (bootedRef.current) return;
    bootedRef.current = true;
    void loadHistory();

    if (startNew) {
      loadedRef.current = null;
      return;
    }
    if (initialSolutionId) {
      void hydrate(initialSolutionId);
      return;
    }
    // No explicit id: resume the most recent conversation if one exists.
    let cancelled = false;
    void (async () => {
      try {
        const items = await refreshSolutions();
        if (cancelled || !items.length) {
          if (!cancelled) dispatch({ type: 'conversation/empty', welcome });
          return;
        }
        const latest = items[0];
        dispatch({ type: 'activate', solutionId: latest.id, appName: latest.title, welcome });
        loadedRef.current = latest.id;
        dispatch({ type: 'conversation/loaded', solution: latest, agent, welcome });
        dispatch({ type: 'builds/loaded', builds: [] });
      } catch {
        if (!cancelled) dispatch({ type: 'conversation/empty', welcome });
      }
    })();
    return () => {
      cancelled = true;
    };
    // Boot only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectSolution = useCallback(
    (solution: Solution | null) => {
      loadedRef.current = null;
      if (!solution) {
        dispatch({ type: 'activate', solutionId: null, welcome });
        return;
      }
      dispatch({ type: 'activate', solutionId: solution.id, appName: solution.title, welcome });
    },
    [welcome]
  );

  const clearError = useCallback(() => dispatch({ type: 'set-error', value: null }), []);

  return useMemo(
    () => ({ state, dispatch, loadHistory, hydrate, selectSolution, clearError, welcome, agent }),
    [state, loadHistory, hydrate, selectSolution, clearError, welcome, agent]
  );
}

export type ChatSession = ReturnType<typeof useChatSession>;
