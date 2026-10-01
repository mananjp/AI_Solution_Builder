'use client';

import React, { useState, type ReactElement, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';
import { Check, Copy } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export default function MarkdownRenderer({ content, className = '' }: MarkdownRendererProps) {
  if (!content) return null;

  return (
    <div className={`min-w-0 space-y-3 break-words text-[13px] leading-6 text-[var(--sutra-ink)] [overflow-wrap:anywhere] ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          h1: ({ children }) => <h1 className="mt-6 text-xl font-semibold leading-tight first:mt-0">{children}</h1>,
          h2: ({ children }) => <h2 className="mt-5 border-b border-[var(--border)] pb-2 text-lg font-semibold leading-tight first:mt-0">{children}</h2>,
          h3: ({ children }) => <h3 className="mt-4 text-base font-semibold leading-snug first:mt-0">{children}</h3>,
          h4: ({ children }) => <h4 className="mt-3 text-sm font-semibold first:mt-0">{children}</h4>,
          p: ({ children }) => <p className="my-2 min-w-0">{children}</p>,
          ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5 marker:text-[var(--sutra-strong)]">{children}</ul>,
          ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5 marker:text-[var(--sutra-strong)]">{children}</ol>,
          li: ({ children }) => <li className="pl-1">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="my-3 border-l-2 border-[var(--sutra-strong)] bg-[var(--bg-2)] py-1 pl-4 text-[var(--text-2)]">
              {children}
            </blockquote>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[var(--info)] underline decoration-current/40 underline-offset-2 hover:decoration-current"
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="my-3 max-w-full overflow-x-auto rounded-lg border border-[var(--border)]">
              <table className="w-full border-collapse text-left text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-[var(--bg-2)]">{children}</thead>,
          th: ({ children }) => <th className="whitespace-nowrap border-b border-[var(--border)] px-3 py-2 font-semibold">{children}</th>,
          td: ({ children }) => <td className="border-t border-[var(--border)] px-3 py-2 align-top">{children}</td>,
          code: ({ children, className: codeClass }) => (
            <code className={`${codeClass ?? ''} rounded bg-[var(--bg-2)] px-1.5 py-0.5 font-mono text-[0.92em] text-[var(--sutra-ink)]`}>
              {children}
            </code>
          ),
          pre: ({ children }) => {
            const child = React.Children.toArray(children)[0] as ReactElement<{
              className?: string;
              children?: ReactNode;
            }> | undefined;
            const source = child?.props?.children;
            const code = (Array.isArray(source) ? source.join('') : String(source ?? '')).replace(/\n$/, '');
            const language = child?.props?.className?.match(/language-([\w-]+)/)?.[1] ?? 'code';
            return <CodeBlock language={language} code={code} />;
          },
          hr: () => <hr className="my-4 border-[var(--border)]" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="my-4 min-w-0 max-w-full overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg-2)] font-mono text-xs shadow-sm">
      <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] bg-[var(--bg)] px-3 py-1.5">
        <span className="min-w-0 truncate text-[10px] font-semibold uppercase tracking-wider text-[var(--text-2)]">
          {language}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleCopy}
          className="h-8 shrink-0 gap-2 px-3 text-xs"
          aria-label={copied ? 'Code copied' : 'Copy code'}
        >
          {copied ? <Check className="size-3.5 text-[var(--green)]" /> : <Copy className="size-3.5" />}
          <span>{copied ? 'Copied' : 'Copy code'}</span>
        </Button>
      </div>
      <pre className="max-w-full overflow-x-auto p-4 text-[var(--sutra-ink)] leading-relaxed">
        <code className="font-mono">{code}</code>
      </pre>
    </div>
  );
}
