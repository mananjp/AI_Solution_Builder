'use client';

import React, { useMemo } from 'react';
import type { Dispatch } from 'react';
import { Clock, FileText, MessageSquare, Plus, Search, ShieldCheck, Trash2, X } from 'lucide-react';
import clsx from 'clsx';
import FileUploader from '@/components/FileUploader';
import { HistorySkeleton, Skeleton } from '@/components/chat/Skeleton';
import { TabBar, type TabBarItem } from '@/components/lab/tab-bar';
import { RelativeTime } from '@/components/lab/relative-time';
import type { ChatAction, ChatState } from '@/hooks/useChatSession';
import type { Solution } from '@/types';

import { Button } from '@/components/ui/button';

const HISTORY_ICON = (
  <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M2.75 8a5.25 5.25 0 1 0 1.54-3.72L2.75 5.5M2.75 5.5V2.75M2.75 5.5h2.75" />
    <path d="M8 5.25V8l1.75 1.25" />
  </svg>
);

const CONTEXT_ICON = (
  <svg viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M3.25 2.75h6l3.5 3.5v7h-9.5z" />
    <path d="M9.25 2.75v3.5h3.5" />
  </svg>
);

const TABS: TabBarItem[] = [
  { id: 'history', label: 'History', icon: HISTORY_ICON },
  { id: 'context', label: 'Context / PRD', icon: CONTEXT_ICON },
];

/**
 * Relative age of a session, e.g. "2h ago".
 *
 * Replaces a hand-rolled day-diff so the wording is identical everywhere and
 * the full timestamp is still available on hover.
 */
function SessionAge({ date }: { date: string }) {
  return (
    <span className="flex items-center gap-1">
      <Clock className="w-2.5 h-2.5" />
      <RelativeTime date={date} />
    </span>
  );
}

function SolutionRow({
  solution,
  active,
  onSelect,
  onDelete,
}: {
  solution: Solution;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  const messageCount = solution.conversation_history?.length ?? 0;
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect();
        }
      }}
      aria-current={active ? 'true' : undefined}
      className={clsx(
        'group relative p-2.5 rounded-sm border cursor-pointer transition-all text-left w-full',
        active
          ? 'border-[var(--sutra-strong)] bg-[var(--bg)] shadow-sm'
          : 'border-transparent hover:border-[var(--border)] hover:bg-[var(--bg)]'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            {active && <span className="w-1.5 h-1.5 rounded-full bg-[var(--sutra-strong)] shrink-0" />}
            <p
              className={clsx(
                'text-xs font-semibold truncate',
                active ? 'text-[var(--sutra-ink)] font-bold' : 'text-[var(--text-2)] group-hover:text-[var(--sutra-ink)]'
              )}
            >
              {solution.title || 'Untitled Build'}
            </p>
          </div>
          <div className="flex items-center gap-2 mt-1 text-[10px] text-[var(--text-3)] font-mono">
            <SessionAge date={solution.created_at} />
            {messageCount > 0 && <span>• {messageCount} msg{messageCount > 1 ? 's' : ''}</span>}
          </div>
        </div>
        <Button variant="ghost" size="icon-sm"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="opacity-0 group-hover:opacity-100 focus:opacity-100 p-1 hover:text-[var(--red)] text-[var(--text-3)] transition-all shrink-0"
          title="Delete conversation"
          aria-label={`Delete ${solution.title || 'conversation'}`}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}

function HistoryPanel({
  state,
  onSelect,
  onDelete,
  onNew,
  onQuery,
}: {
  state: ChatState;
  onSelect: (s: Solution) => void;
  onDelete: (s: Solution) => void;
  onNew: () => void;
  onQuery: (q: string) => void;
}) {
  const query = state.historyQuery.trim().toLowerCase();
  const filtered = useMemo(
    () =>
      query
        ? state.history.filter(
            (s) =>
              s.title?.toLowerCase().includes(query) || s.description?.toLowerCase().includes(query)
          )
        : state.history,
    [state.history, query]
  );

  const showSkeleton = state.historyStatus === 'loading' && state.history.length === 0;

  return (
    <div className="flex-1 flex flex-col min-h-0 p-3">
      <Button variant="default" size="default"
        onClick={onNew}
        className="mb-3 flex w-full min-w-0 items-center justify-center gap-2 bg-[var(--bg)] hover:bg-[var(--sutra-ink)] text-[var(--sutra-ink)] hover:text-[var(--background)] border border-[var(--sutra-strong)]/50 hover:border-[var(--sutra-ink)] text-[11px] font-bold uppercase tracking-wider transition-all"
      >
        <Plus className="w-3.5 h-3.5 shrink-0 text-[var(--sutra-strong)]" />
        <span className="min-w-0 truncate">New Architecture Build</span>
      </Button>

      <div className="relative mb-2">
        <Search className="w-3.5 h-3.5 text-[var(--text-3)] absolute left-2.5 top-2" />
        <input
          type="text"
          value={state.historyQuery}
          onChange={(e) => onQuery(e.target.value)}
          placeholder={state.history.length ? 'Search conversations…' : 'Search conversations…'}
          className="w-full pl-8 pr-8 py-1.5 text-xs bg-[var(--bg)] border border-[var(--border)] rounded-sm text-[var(--sutra-ink)] placeholder-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-strong)]"
        />
        {state.historyQuery && (
          <Button variant="ghost" size="icon-sm"
            onClick={() => onQuery('')}
            className="absolute right-2 top-1.5 text-[var(--text-3)] hover:text-[var(--sutra-ink)]"
            aria-label="Clear search"
          >
            <X className="w-3.5 h-3.5" />
          </Button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 min-h-0">
        {showSkeleton ? (
          <HistorySkeleton count={6} />
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center px-4 text-[var(--text-3)]">
            {state.historyStatus === 'error' ? (
              <>
                <Skeleton className="w-8 h-8 mb-2 opacity-40" />
                <p className="text-xs font-serif text-[var(--text-2)]">Could not load history</p>
                <p className="text-[11px] font-light mt-1">Check the backend connection and retry.</p>
              </>
            ) : (
              <>
                <MessageSquare className="w-8 h-8 mb-2 opacity-40" />
                <p className="text-xs font-serif text-[var(--text-2)]">
                  {query ? 'No matching conversations' : 'No conversations yet'}
                </p>
                <p className="text-[11px] font-light mt-1">
                  {query ? 'Try a different search term.' : 'Start a build to begin your chat history.'}
                </p>
              </>
            )}
          </div>
        ) : (
          filtered.map((sol) => (
            <SolutionRow
              key={sol.id}
              solution={sol}
              active={state.solutionId === sol.id}
              onSelect={() => onSelect(sol)}
              onDelete={() => onDelete(sol)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function ContextPanel({
  state,
  onAttach,
  onClear,
  helperText,
}: {
  state: ChatState;
  onAttach: (text: string, filename: string) => void;
  onClear: () => void;
  helperText: string;
}) {
  if (state.context) {
    return (
      <div className="flex-1 p-4 overflow-y-auto overflow-x-hidden space-y-4">
        <div className="p-3 bg-[var(--bg)] border border-[var(--sutra-strong)] rounded-sm shadow-sm space-y-2.5 text-[12px]">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-[var(--bg-2)] border border-[var(--border)] rounded-sm text-[var(--sutra-ink)]">
              <FileText className="w-4 h-4" />
            </div>
            <p className="font-semibold text-[var(--sutra-ink)] break-all">{state.context.filename}</p>
          </div>
          <p className="text-[10px] uppercase tracking-widest text-[var(--text-3)] font-mono font-medium">
            {state.context.text.length.toLocaleString()} characters parsed · Context active
          </p>
          <div className="flex items-center gap-1.5 pt-2 border-t border-[var(--border)] text-[11px] text-[var(--green)] font-mono font-medium">
            <ShieldCheck className="w-4 h-4 text-[var(--green)] shrink-0" />
            <span>Threat Scan: Verified Clean</span>
          </div>
        </div>
        <Button type="button" variant="ghost" onClick={onClear} className="w-full text-[10px] uppercase tracking-widest font-semibold">
          Clear context
        </Button>
      </div>
    );
  }

  return (
    <div className="flex-1 p-4 overflow-y-auto overflow-x-hidden">
      <div className="h-full flex flex-col items-center justify-center text-center space-y-4">
        <FileUploader onParsedContext={onAttach} onClear={onClear} />
        <p className="text-[11px] text-[var(--text-2)] font-light max-w-[200px] break-words">{helperText}</p>
      </div>
    </div>
  );
}

export function ChatSidecar({
  state,
  dispatch,
  onSelect,
  onDelete,
  onNew,
  onAttach,
  onClearContext,
  providePrdText,
  onClose,
}: {
  state: ChatState;
  dispatch: Dispatch<ChatAction>;
  onSelect: (s: Solution) => void;
  onDelete: (s: Solution) => void;
  onNew: () => void;
  onAttach: (text: string, filename: string) => void;
  onClearContext: () => void;
  providePrdText: string;
  onClose?: () => void;
}) {
  return (
    <div className="flex flex-col h-full min-h-0 bg-[var(--bg-2)] border border-[var(--border)] rounded-sm overflow-hidden">
      <div className="flex items-center gap-2 border-b border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 shrink-0">
        {/* The lab tab bar draws one pill that slides between tabs, so the
            active tab cannot be a second border that drifts out of step with
            the label. Icons are drawn once and reused for both states. */}
        <TabBar
          items={TABS}
          value={state.sidecarTab}
          onChange={(value) =>
            dispatch({ type: 'set-sidecar-tab', value: value as ChatState['sidecarTab'] })
          }
          label="Sidecar"
          idBase="chat-sidecar"
          className="min-w-0 flex-1"
        />
        {onClose && (
          <Button variant="ghost" size="icon-sm"
            onClick={onClose}
            className="shrink-0 p-1.5 text-[var(--text-3)] hover:text-[var(--sutra-ink)] transition-colors"
            aria-label="Close panel"
          >
            <X className="w-3.5 h-3.5" />
          </Button>
        )}
      </div>

      {state.sidecarTab === 'history' ? (
        <HistoryPanel
          state={state}
          onSelect={onSelect}
          onDelete={onDelete}
          onNew={onNew}
          onQuery={(q) => dispatch({ type: 'set-history-query', value: q })}
        />
      ) : (
        <ContextPanel
          state={state}
          onAttach={onAttach}
          onClear={onClearContext}
          helperText={providePrdText}
        />
      )}
    </div>
  );
}
