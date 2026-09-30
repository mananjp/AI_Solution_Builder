'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Copy, Check, Sparkles } from 'lucide-react';
import MarkdownRenderer from './MarkdownRenderer';
import { Button } from "@/components/ui/button";

interface ChatMessageProps {
  role: 'user' | 'assistant' | 'system';
  content: string;
  agent?: string;
  /** True when the previous bubble shares this sender, for grouped corners. */
  groupedWithPrev?: boolean;
  /** True when the next bubble shares this sender. */
  groupedWithNext?: boolean;
  /** Streaming replies need room to grow without the thread jumping. */
  streaming?: boolean;
}

// Bubble corners: 18px open, 6px where two bubbles from the same sender meet,
// so a run of messages reads as one block instead of stacked cards.
const OPEN = 18;
const JOINED = 6;

function radius(from: 'me' | 'them', prevSame: boolean, nextSame: boolean) {
  const top = prevSame ? JOINED : OPEN;
  const bottom = nextSame ? JOINED : OPEN;
  return from === 'me'
    ? `${OPEN}px ${top}px ${bottom}px ${OPEN}px`
    : `${top}px ${OPEN}px ${OPEN}px ${bottom}px`;
}

export default function ChatMessage({
  role,
  content,
  agent,
  groupedWithPrev = false,
  groupedWithNext = false,
  streaming = false,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    []
  );

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  const isUser = role === 'user';

  if (isUser) {
    return (
      <div className={clsxJoin('flex justify-end', groupedWithPrev ? 'mt-1' : 'mt-4')}>
        <div
          style={{ borderRadius: radius('me', groupedWithPrev, groupedWithNext) }}
          className="max-w-[85%] bg-[var(--sutra-ink)] px-4 py-2.5 text-[13px] leading-relaxed text-[var(--sutra-canvas)] shadow-sm break-words whitespace-pre-wrap"
        >
          {content}
        </div>
      </div>
    );
  }

  if (role === 'system') {
    return (
      <div className={clsxJoin('flex justify-center', groupedWithPrev ? 'mt-1' : 'mt-4')}>
        <div className="max-w-[90%] rounded-full border border-[var(--border)] bg-[var(--bg-3)] px-3.5 py-1.5 text-center text-[11px] text-[var(--text-2)]">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className={clsxJoin('pr-10', groupedWithPrev ? 'mt-1' : 'mt-6')}>
      {!groupedWithPrev && (
        <div className="mb-2.5 flex items-center gap-2.5">
          <span
            aria-hidden
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--accent-dim)] text-[var(--sutra-strong)]"
          >
            <Sparkles className="h-3 w-3" />
          </span>
          <span className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-2)]">
            {agent || 'SUTRA Intelligence'}
          </span>
          <span className="h-px flex-1 bg-[var(--border)]" />
        </div>
      )}

      <div className="pl-8">
        <div
          className="border border-[var(--border)] bg-[var(--bg-2)] px-4 py-3 text-[13px] leading-relaxed text-[var(--sutra-ink)] shadow-sm"
          style={{ borderRadius: radius('them', groupedWithPrev, groupedWithNext) }}
        >
          <MarkdownRenderer content={content} />
          {streaming && (
            <span
              aria-hidden
              className="ml-1 inline-block h-3.5 w-[2px] translate-y-0.5 animate-pulse bg-[var(--sutra-strong)] align-middle"
            />
          )}
        </div>

        {!groupedWithNext && (
          <div className="mt-1.5 flex justify-end">
          <Button variant="ghost" size="sm"
            onClick={handleCopy}
            className="gap-1.5 rounded-md px-2 text-[11px] normal-case tracking-normal text-[var(--text-2)] transition-colors hover:text-[var(--sutra-ink)]"
              title="Copy message"
              aria-label={copied ? 'Copied' : 'Copy message'}
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-[var(--green)]" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function clsxJoin(...parts: (string | false | undefined)[]) {
  return parts.filter(Boolean).join(' ');
}
