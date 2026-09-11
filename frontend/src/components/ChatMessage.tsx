'use client';

import React, { useState } from 'react';
import { User, Copy, Check, Sparkles } from 'lucide-react';

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

  // Format message lines (handles bold text, bullet points, numbered lists)
  const formatContent = (text: string) => {
    return text.split('\n').map((line, i) => {
      // Bullet points
      if (line.trim().startsWith('- ') || line.trim().startsWith('* ')) {
        const bulletText = line.trim().substring(2);
        return (
          <li key={i} className="ml-4 list-disc text-slate-300 my-1 leading-relaxed">
            {renderFormattedInline(bulletText)}
          </li>
        );
      }
      // Numbered lists
      const numberedMatch = line.trim().match(/^(\d+)\.\s+(.*)/);
      if (numberedMatch) {
        return (
          <li key={i} className="ml-4 list-decimal text-slate-300 my-1 leading-relaxed">
            {renderFormattedInline(numberedMatch[2])}
          </li>
        );
      }
      // Headers
      if (line.startsWith('### ')) {
        return <h4 key={i} className="text-sm font-bold text-indigo-300 mt-3 mb-1">{line.replace('### ', '')}</h4>;
      }
      if (line.startsWith('## ')) {
        return <h3 key={i} className="text-base font-bold text-white mt-4 mb-1.5">{line.replace('## ', '')}</h3>;
      }
      if (line.startsWith('# ')) {
        return <h2 key={i} className="text-lg font-extrabold text-white mt-4 mb-2">{line.replace('# ', '')}</h2>;
      }
      // Regular paragraph
      if (!line.trim()) {
        return <div key={i} className="h-2" />;
      }
      return (
        <p key={i} className="my-1 leading-relaxed">
          {renderFormattedInline(line)}
        </p>
      );
    });
  };

  const renderFormattedInline = (text: string) => {
    // Bold formatting **text**
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={index} className="text-indigo-200 font-semibold">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });
  };

  return (
    <div className={`flex gap-3.5 my-4 ${isAssistant ? 'justify-start' : 'justify-end'}`}>
      {/* Assistant Avatar */}
      {isAssistant && (
        <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center text-white flex-shrink-0 shadow-md shadow-indigo-500/20 mt-1">
          <Sparkles className="w-4 h-4" />
        </div>
      )}

      {/* Message Bubble */}
      <div
        className={`relative max-w-[85%] md:max-w-[75%] rounded-2xl p-4 text-sm ${
          isAssistant
            ? 'bg-slate-900/80 border border-white/5 text-slate-200 shadow-lg'
            : 'bg-gradient-to-r from-indigo-600 to-indigo-700 text-white shadow-md shadow-indigo-500/10'
        }`}
      >
        {/* Agent header pill */}
        {isAssistant && (
          <div className="flex items-center justify-between gap-4 mb-2 pb-2 border-b border-white/5">
            <span className="text-[11px] font-semibold text-indigo-400 flex items-center gap-1.5 uppercase tracking-wider">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
              {agent || 'AI Solution Architect'}
            </span>
            <button
              onClick={handleCopy}
              className="text-slate-400 hover:text-slate-200 text-xs p-1 rounded hover:bg-white/5 transition-colors"
              title="Copy message"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        )}

        {/* Content */}
        <div className="space-y-1">{formatContent(content)}</div>
      </div>

      {/* User Avatar */}
      {!isAssistant && (
        <div className="w-8 h-8 rounded-xl bg-slate-800 border border-white/10 flex items-center justify-center text-slate-300 flex-shrink-0 mt-1">
          <User className="w-4 h-4" />
        </div>
      )}
    </div>
  );
}
