'use client';

import React, { useMemo } from 'react';
import type { Dispatch } from 'react';
import { Clock, FileText, History, MessageSquare, Plus, Search, Trash2, X } from 'lucide-react';
import clsx from 'clsx';
import FileUploader from '@/components/FileUploader';
import { HistorySkeleton, Skeleton } from '@/components/chat/Skeleton';
import type { ChatAction, ChatState } from '@/hooks/useChatSession';
import type { Solution } from '@/types';

function formatSessionDate(dateString: string): string {
  try {
    const d = new Date(dateString);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - d.getTime()) / 86_400_000);
    if (diffDays <= 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return dateString;
  }
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
          ? 'border-[var(--sutra-muted-gold)] bg-[var(--bg)] shadow-sm'
          : 'border-transparent hover:border-[var(--border)] hover:bg-[var(--bg)]'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            {active && <span className="w-1.5 h-1.5 rounded-full bg-[var(--sutra-muted-gold)] shrink-0" />}
            <p
              className={clsx(
                'text-xs font-semibold truncate',
                active ? 'text-[var(--sutra-charcoal)] font-bold' : 'text-[var(--text-2)] group-hover:text-[var(--sutra-charcoal)]'
              )}
            >
              {solution.title || 'Untitled Build'}
            </p>
          </div>
          <div className="flex items-center gap-2 mt-1 text-[10px] text-[var(--text-3)] font-mono">
            <span className="flex items-center gap-1">
              <Clock className="w-2.5 h-2.5" />
              {formatSessionDate(solution.created_at)}
            </span>
            {messageCount > 0 && <span>• {messageCount} msg{messageCount > 1 ? 's' : ''}</span>}
          </div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="opacity-0 group-hover:opacity-100 focus:opacity-100 p-1 hover:text-red-600 text-[var(--text-3)] transition-all shrink-0"
          title="Delete conversation"
          aria-label={`Delete ${solution.title || 'conversation'}`}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
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
      <button
        onClick={onNew}
        className="w-full mb-3 py-2 px-3 flex items-center justify-center gap-2 bg-[var(--bg)] hover:bg-[var(--sutra-charcoal)] text-[var(--sutra-charcoal)] hover:text-white border border-[var(--sutra-muted-gold)]/50 hover:border-[var(--sutra-charcoal)] rounded-sm text-[11px] font-bold uppercase tracking-wider transition-all shadow-sm"
      >
        <Plus className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
        <span>New Architecture Build</span>
      </button>

      <div className="relative mb-2">
        <Search className="w-3.5 h-3.5 text-[var(--text-3)] absolute left-2.5 top-2" />
        <input
          type="text"
          value={state.historyQuery}
          onChange={(e) => onQuery(e.target.value)}
          placeholder={state.history.length ? 'Search conversations…' : 'Search conversations…'}
          className="w-full pl-8 pr-8 py-1.5 text-xs bg-[var(--bg)] border border-[var(--border)] rounded-sm text-[var(--sutra-charcoal)] placeholder-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)]"
        />
        {state.historyQuery && (
          <button
            onClick={() => onQuery('')}
            className="absolute right-2 top-1.5 text-[var(--text-3)] hover:text-[var(--sutra-charcoal)]"
            aria-label="Clear search"
          >
            <X className="w-3.5 h-3.5" />
          </button>
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
        <div className="p-3 bg-[var(--bg)] border border-[var(--sutra-muted-gold)] text-[12px]">
          <p className="font-semibold text-[var(--sutra-charcoal)] break-all">{state.context.filename}</p>
          <p className="text-[10px] uppercase tracking-widest text-[var(--text-2)] mt-2 font-bold">
            {state.context.text.length.toLocaleString()} characters parsed
          </p>
        </div>
        <button onClick={onClear} className="btn btn-ghost w-full text-[10px] uppercase tracking-widest font-semibold">
          Clear context
        </button>
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
      <div className="flex border-b border-[var(--border)] bg-[var(--bg)] text-[11px] font-bold uppercase tracking-wider shrink-0">
        <button
          onClick={() => dispatch({ type: 'set-sidecar-tab', value: 'history' })}
          className={clsx(
            'flex-1 py-3 px-3 flex items-center justify-center gap-1.5 border-b-2 transition-colors',
            state.sidecarTab === 'history'
              ? 'border-[var(--sutra-muted-gold)] text-[var(--sutra-charcoal)] bg-[var(--bg-2)]'
              : 'border-transparent text-[var(--text-3)] hover:text-[var(--sutra-charcoal)]'
          )}
          aria-pressed={state.sidecarTab === 'history'}
        >
          <History className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
          <span>History</span>
          {state.history.length > 0 && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--bg)] border border-[var(--border)] text-[var(--text-2)] font-mono">
              {state.history.length}
            </span>
          )}
        </button>
        <button
          onClick={() => dispatch({ type: 'set-sidecar-tab', value: 'context' })}
          className={clsx(
            'flex-1 py-3 px-3 flex items-center justify-center gap-1.5 border-b-2 transition-colors',
            state.sidecarTab === 'context'
              ? 'border-[var(--sutra-muted-gold)] text-[var(--sutra-charcoal)] bg-[var(--bg-2)]'
              : 'border-transparent text-[var(--text-3)] hover:text-[var(--sutra-charcoal)]'
          )}
          aria-pressed={state.sidecarTab === 'context'}
        >
          <FileText className="w-3.5 h-3.5 text-[var(--text-3)]" />
          <span>Context / PRD</span>
          {state.context && <span className="w-2 h-2 rounded-full bg-emerald-500" />}
        </button>
        {onClose && (
          <button
            onClick={onClose}
            className="px-3 text-[var(--text-3)] hover:text-[var(--sutra-charcoal)] border-l border-[var(--border)]"
            aria-label="Close panel"
          >
            <X className="w-3.5 h-3.5" />
          </button>
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
