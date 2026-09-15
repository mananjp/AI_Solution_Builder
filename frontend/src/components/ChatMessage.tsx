'use client';

import React, { useState } from 'react';
import { Copy, Check } from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/utils';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  agentName?: string;
  timestamp?: string;
}

function renderMarkdown(text: string): React.ReactNode {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Code block
    if (line.trim().startsWith('```')) {
      const codeLines: string[] = [];
      const lang = line.trim().replace('```', '').trim();
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing ```
      elements.push(
        <pre key={key++} className="bg-secondary rounded-md p-3 my-2 overflow-x-auto">
          {lang && (
            <div className="text-[9px] font-mono text-muted-foreground/60 mb-2 uppercase tracking-wider">
              {lang}
            </div>
          )}
          <code className="text-[12px] font-mono text-foreground/90 leading-relaxed">
            {codeLines.join('\n')}
          </code>
        </pre>
      );
      continue;
    }

    // Heading
    if (line.startsWith('### ')) {
      elements.push(<h3 key={key++} className="text-[13px] font-bold mt-4 mb-2 text-foreground">{line.replace('### ', '')}</h3>);
      i++;
      continue;
    }
    if (line.startsWith('## ')) {
      elements.push(<h2 key={key++} className="text-[14px] font-bold mt-5 mb-2 text-foreground">{line.replace('## ', '')}</h2>);
      i++;
      continue;
    }
    if (line.startsWith('# ')) {
      elements.push(<h1 key={key++} className="text-[15px] font-bold mt-6 mb-3 text-foreground">{line.replace('# ', '')}</h1>);
      i++;
      continue;
    }

    // Table
    if (line.includes('|') && i + 1 < lines.length && lines[i + 1]?.includes('---')) {
      const headers = line.split('|').filter(Boolean).map((h) => h.trim());
      i += 2; // skip header + separator
      const rows: string[][] = [];
      while (i < lines.length && lines[i].includes('|')) {
        rows.push(lines[i].split('|').filter(Boolean).map((c) => c.trim()));
        i++;
      }
      elements.push(
        <div key={key++} className="my-3 overflow-x-auto">
          <table className="w-full text-[11px] border-collapse">
            <thead>
              <tr className="border-b border-border">
                {headers.map((h, hi) => (
                  <th key={hi} className="text-left py-1.5 px-2 font-semibold text-muted-foreground">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className="border-b border-border/50">
                  {row.map((cell, ci) => (
                    <td key={ci} className="py-1.5 px-2 text-foreground/80">
                      {renderInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // Unordered list
    if (line.match(/^[\s]*[-*]\s/)) {
      const listItems: string[] = [];
      while (i < lines.length && lines[i].match(/^[\s]*[-*]\s/)) {
        listItems.push(lines[i].replace(/^[\s]*[-*]\s/, ''));
        i++;
      }
      elements.push(
        <ul key={key++} className="my-2 flex flex-col gap-0.5">
          {listItems.map((item, li) => (
            <li key={li} className="flex items-start gap-2 text-[12px] text-foreground/80 leading-relaxed">
              <span className="text-primary mt-1.5 shrink-0">•</span>
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // Ordered list
    if (line.match(/^[\s]*\d+\.\s/)) {
      const listItems: string[] = [];
      while (i < lines.length && lines[i].match(/^[\s]*\d+\.\s/)) {
        listItems.push(lines[i].replace(/^[\s]*\d+\.\s/, ''));
        i++;
      }
      elements.push(
        <ol key={key++} className="my-2 flex flex-col gap-0.5">
          {listItems.map((item, li) => (
            <li key={li} className="flex items-start gap-2 text-[12px] text-foreground/80 leading-relaxed">
              <span className="text-primary font-mono text-[10px] mt-0.5 shrink-0">{li + 1}.</span>
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ol>
      );
      continue;
    }

    // Empty line
    if (line.trim() === '') {
      i++;
      continue;
    }

    // Paragraph
    elements.push(
      <p key={key++} className="text-[12px] text-foreground/80 leading-relaxed my-1.5">
        {renderInline(line)}
      </p>
    );
    i++;
  }

  return elements;
}

function renderInline(text: string): React.ReactNode {
  // Handle **bold**, `code`, and plain text
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*.*?\*\*|`[^`]+`)/g;
  let lastIndex = 0;
  let match;
  let key = 0;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith('**')) {
      parts.push(<strong key={key++} className="font-semibold text-foreground">{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('`')) {
      parts.push(
        <code key={key++} className="bg-secondary px-1 py-0.5 rounded text-[11px] font-mono text-primary">
          {token.slice(1, -1)}
        </code>
      );
    }
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}

export default function ChatMessage({ role, content, agentName, timestamp }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={cn('flex gap-3 group', role === 'user' ? 'justify-end' : 'justify-start')}>
      {role === 'assistant' && (
        <Avatar className="size-6 shrink-0 mt-0.5">
          <AvatarFallback className="bg-primary/15 text-primary text-[9px] font-bold border border-primary/20">
            AI
          </AvatarFallback>
        </Avatar>
      )}

      <div className={cn('flex flex-col gap-1 max-w-[85%]', role === 'user' && 'items-end')}>
        {agentName && role === 'assistant' && (
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-medium text-primary">{agentName}</span>
            {timestamp && (
              <span className="text-[9px] text-muted-foreground/50 font-mono">{timestamp}</span>
            )}
          </div>
        )}

        <div
          className={cn(
            'rounded-lg px-3 py-2.5 text-[12px]',
            role === 'user'
              ? 'bg-primary/10 text-foreground border border-primary/15'
              : 'bg-secondary text-foreground/90 border border-border'
          )}
        >
          {role === 'assistant' ? renderMarkdown(content) : (
            <p className="leading-relaxed">{content}</p>
          )}
        </div>

        {role === 'assistant' && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            className="h-5 px-1.5 text-[9px] text-muted-foreground/50 hover:text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
          >
            {copied ? <Check className="size-2.5" /> : <Copy className="size-2.5" />}
            {copied ? 'Copied' : 'Copy'}
          </Button>
        )}
      </div>

      {role === 'user' && (
        <Avatar className="size-6 shrink-0 mt-0.5">
          <AvatarFallback className="bg-secondary text-[9px] font-bold border border-border">
            U
          </AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}
