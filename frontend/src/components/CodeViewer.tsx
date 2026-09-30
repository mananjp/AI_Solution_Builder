'use client';

import { useEffect, useMemo, useState } from 'react';
import { codeToTokens, type BundledLanguage, type ThemedToken } from 'shiki';
import { Loader2 } from 'lucide-react';

/**
 * Read-only source viewer.
 *
 * The previous implementation built an HTML string by regex-replacing keywords
 * into `<span>` tags and assigning it through `dangerouslySetInnerHTML`. That was
 * broken in two ways: it never escaped `&`, so an entity-encoded payload in
 * AI-generated file content decoded back into live markup, and the
 * string-literal pass re-matched the double quotes that the earlier keyword
 * passes had themselves injected, nesting `<span>` inside a tag attribute and
 * producing markup the parser discards.
 *
 * Here shiki tokenises the source and the tokens are rendered as real React
 * elements, so file content is escaped by React and no HTML string is ever
 * constructed.
 */

const EXTENSION_LANGUAGE: Record<string, BundledLanguage> = {
  ts: 'typescript',
  tsx: 'tsx',
  js: 'javascript',
  jsx: 'jsx',
  mjs: 'javascript',
  cjs: 'javascript',
  json: 'json',
  py: 'python',
  rb: 'ruby',
  go: 'go',
  rs: 'rust',
  java: 'java',
  kt: 'kotlin',
  swift: 'swift',
  c: 'c',
  h: 'c',
  cpp: 'cpp',
  hpp: 'cpp',
  cs: 'csharp',
  php: 'php',
  sh: 'shell',
  bash: 'shell',
  zsh: 'shell',
  sql: 'sql',
  html: 'html',
  css: 'css',
  scss: 'scss',
  md: 'markdown',
  yml: 'yaml',
  yaml: 'yaml',
  toml: 'toml',
  dockerfile: 'dockerfile',
  tf: 'hcl',
  proto: 'protobuf',
};

const TOKENIZATION_THEME = 'vitesse-dark';

function languageForPath(path: string): BundledLanguage {
  const name = path.split('/').pop() ?? '';
  if (name.toLowerCase() === 'dockerfile') return 'dockerfile';
  const ext = name.includes('.') ? name.split('.').pop()!.toLowerCase() : '';
  return EXTENSION_LANGUAGE[ext] ?? 'text';
}

/**
 * Syntax families mapped onto the app's own theme variables.
 *
 * Shiki emits TextMate scopes with the language appended (`keyword.control.conditional.tsx`,
 * `string.quoted.double.py`), so these are matched as *prefixes* rather than
 * exact names. Order is significant: each token is tested against these families
 * top to bottom and the first family present anywhere in its scope stack wins.
 *
 * That "anywhere in the stack" rule matters. A quote character carries both
 * `punctuation.definition.string.begin.tsx` and `string.quoted.double.tsx`; a
 * prefix scan that only inspected the most specific scope would colour the quote
 * as punctuation and leave the rest of the literal unstyled.
 */
const TOKEN_FAMILIES: ReadonlyArray<{ prefixes: readonly string[]; className: string }> = [
  { prefixes: ['comment'], className: 'text-[var(--text-3)] italic' },
  { prefixes: ['string'], className: 'text-[var(--green)]' },
  {
    prefixes: ['constant.numeric', 'constant.language', 'variable.other.constant'],
    className: 'text-[var(--amber)]',
  },
  { prefixes: ['entity.name.tag'], className: 'text-[var(--green)] font-medium' },
  { prefixes: ['entity.other.attribute-name'], className: 'text-[var(--info)]' },
  {
    prefixes: ['entity.name.type', 'support.type', 'entity.name.class'],
    className: 'text-[var(--info)]',
  },
  {
    prefixes: ['entity.name.function', 'support.function', 'meta.function-call', 'variable.function'],
    className: 'text-[var(--amber)]',
  },
  { prefixes: ['keyword.operator'], className: 'text-[var(--text-2)]' },
  { prefixes: ['keyword', 'storage.type', 'storage.modifier'], className: 'text-[var(--info)] font-semibold' },
  { prefixes: ['punctuation'], className: 'text-[var(--text-2)]' },
];

function classForToken(token: ThemedToken): string {
  const scopes = token.explanation?.[0]?.scopes;
  if (!scopes || scopes.length === 0) return '';

  for (const family of TOKEN_FAMILIES) {
    for (const { scopeName } of scopes) {
      if (family.prefixes.some((prefix) => scopeName.startsWith(prefix))) {
        return family.className;
      }
    }
  }
  return '';
}

interface CodeViewerProps {
  path: string;
  code: string;
  className?: string;
  /** Hides the line-number gutter — useful for inline snippets. */
  showLineNumbers?: boolean;
}

export function CodeViewer({
  path,
  code,
  className,
  showLineNumbers = true,
}: CodeViewerProps) {
  const language = useMemo(() => languageForPath(path), [path]);
  const [result, setResult] = useState<{
    code: string;
    language: BundledLanguage;
    tokens: ThemedToken[][] | null;
    failed: boolean;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;

    // A concrete theme is required even though `token.color` is never read.
// With `theme: 'none'` every token shares the same absent style, so shiki
// merges each whole line into a single token and reports no scopes at all —
// the viewer would render unhighlighted blocks. The theme is used purely as
// the tokenisation engine; colours come from TOKEN_FAMILIES above.
codeToTokens(code, {
        lang: language,
        theme: TOKENIZATION_THEME,
        includeExplanation: true,
      })
      .then((result) => {
        if (!cancelled) setResult({ code, language, tokens: result.tokens, failed: false });
      })
      .catch(() => {
        // An unknown or malformed language must not blank the viewer.
        if (!cancelled) setResult({ code, language, tokens: null, failed: true });
      });

    return () => {
      cancelled = true;
    };
  }, [code, language]);

  const current = result?.code === code && result.language === language ? result : null;

  if (current?.failed) {
    return (
      <pre
        className={`overflow-auto text-[13px] leading-relaxed tab-size-2 ${className ?? ''}`}
      >
        <code className="text-[var(--text-1)]">{code}</code>
      </pre>
    );
  }

  if (!current?.tokens) {
    return (
      <div
        className={`flex items-center justify-center py-16 ${className ?? ''}`}
        aria-busy="true"
      >
        <Loader2 className="h-5 w-5 animate-spin text-[var(--text-3)]" />
      </div>
    );
  }

  return (
    <div className={`flex font-mono text-[13px] leading-relaxed tab-size-2 ${className ?? ''}`}>
      {showLineNumbers && (
        <div
          aria-hidden="true"
          className="w-11 shrink-0 select-none border-r border-[var(--border)] pr-3 text-right text-[var(--text-3)]"
        >
          {current.tokens.map((line, i) => (
            <div key={i}>{i + 1}</div>
          ))}
        </div>
      )}
      <pre className="m-0 min-w-0 flex-1 overflow-auto text-[var(--text-1)]">
        <code>
          {current.tokens.map((line, i) => (
            <div key={i} className="whitespace-pre">
              {line.length === 0 ? (
                ' '
              ) : (
                line.map((token, j) => (
                  <span key={j} className={classForToken(token)}>
                    {token.content}
                  </span>
                ))
              )}
            </div>
          ))}
        </code>
      </pre>
    </div>
  );
}
