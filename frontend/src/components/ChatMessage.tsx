'use client';

import React, { useState } from 'react';
import { User, Copy, Check, Bot } from 'lucide-react';
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

  return (
    <div className={`flex gap-3 my-3 ${isAssistant ? 'justify-start' : 'justify-end'}`}>
      {isAssistant && (
        <div className="w-7 h-7 rounded-lg bg-[#161616] border border-[#2e2e2e] flex items-center justify-center text-[#6366f1] shrink-0 mt-0.5">
          <Bot className="w-3.5 h-3.5" />
        </div>
      )}

      <div
        className={`relative max-w-[88%] md:max-w-[82%] rounded-xl px-4 py-3 text-[13px] leading-relaxed ${isAssistant
            ? 'bg-[#111] border border-[#1a1a1a] text-[#f5f5f5]'
            : 'bg-[#6366f1] text-white font-medium'
          }`}
      >
        {isAssistant && (
          <div className="flex items-center justify-between gap-3 mb-2 pb-2 border-b border-[#1a1a1a]">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#818cf8] uppercase tracking-wider">
              <span className="w-1.5 h-1.5 rounded-full bg-[#6366f1]" />
              {agent || 'AI Developer'}
            </span>
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#161616] hover:bg-[#1f1f1f] border border-[#2a2a2a] text-[#666] hover:text-[#a1a1a1] transition-colors text-[11px]"
              title="Copy message"
            >
              {copied ? <Check className="w-3 h-3 text-[#4ade80]" /> : <Copy className="w-3 h-3" />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        )}

        {isAssistant ? (
          <MarkdownRenderer content={content} />
        ) : (
          <div className="whitespace-pre-wrap">{content}</div>
        )}
      </div>

      {!isAssistant && (
        <div className="w-7 h-7 rounded-lg bg-[#1c1c1c] border border-[#2e2e2e] flex items-center justify-center text-[#a1a1a1] shrink-0 mt-0.5">
          <User className="w-3.5 h-3.5" />
        </div>
      )}
    </div>
  );
}
