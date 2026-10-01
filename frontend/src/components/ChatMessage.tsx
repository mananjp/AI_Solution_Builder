'use client';

import React, { useState } from 'react';
import { User, Copy, Check } from 'lucide-react';
import MarkdownRenderer from './MarkdownRenderer';

interface ChatMessageProps {
  role: 'user' | 'assistant' | 'system';
  content: string;
  agent?: string;
  timestamp?: string;
}

export default function ChatMessage({ role, content, agent }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isAssistant = role === 'assistant';

  if (!isAssistant) {
    return (
      <div className="flex justify-end my-6">
        <div className="max-w-[80%] flex items-start gap-3">
          <div className="bg-[var(--bg-2)] border border-[var(--border)] rounded-sm px-5 py-4 shadow-sm text-[13px] text-[var(--sutra-charcoal)] leading-relaxed">
            <div className="whitespace-pre-wrap font-medium">{content}</div>
          </div>
          <div className="w-8 h-8 flex items-center justify-center shrink-0 text-[var(--text-3)] border border-[var(--border)] bg-[var(--bg)] mt-1">
            <User className="w-4 h-4" />
          </div>
        </div>
      </div>
    );
  }

  // SUTRA Editorial Response
  return (
    <div className="my-10 pr-12">
      {/* SUTRA Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex items-center justify-center shrink-0">
          <span className="text-[var(--sutra-muted-gold)] font-sanskrit font-bold text-lg leading-none drop-shadow-sm">सूत्र</span>
        </div>
        <div className="flex items-center justify-between flex-1 border-b border-[var(--border)] pb-1">
          <span className="text-[10px] uppercase tracking-widest font-semibold text-[var(--sutra-charcoal)]">
            {agent || 'SUTRA Intelligence'}
          </span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-[var(--text-2)] hover:text-[var(--sutra-charcoal)] transition-colors"
            title="Copy message"
          >
            {copied ? <Check className="w-3 h-3 text-[var(--sutra-deep-gold)]" /> : <Copy className="w-3 h-3" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      {/* SUTRA Content */}
      <div className="text-[13px] text-[var(--sutra-charcoal)] leading-relaxed pl-9">
        <MarkdownRenderer content={content} />
      </div>
    </div>
  );
}
