'use client';

import React, { useState } from 'react';
import { Check, Copy } from 'lucide-react';

interface MarkdownRendererProps {
    content: string;
    className?: string;
}

export default function MarkdownRenderer({ content, className = '' }: MarkdownRendererProps) {
    if (!content) return null;

    // Split content into code blocks and text segments
    const blocks = parseMarkdownBlocks(content);

    return (
        <div className={`space-y-4 text-[13px] leading-relaxed text-[var(--sutra-charcoal)] font-light ${className}`}>
            {blocks.map((block, i) => {
                if (block.type === 'code') {
                    return <CodeBlock key={i} language={block.language} code={block.content} />;
                }
                if (block.type === 'table') {
                    return <TableBlock key={i} headers={block.headers} rows={block.rows} />;
                }
                return <TextGroup key={i} text={block.content} />;
            })}
        </div>
    );
}

function CodeBlock({ language, code }: { language: string; code: string }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="my-4 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] overflow-hidden font-mono text-[12px] shadow-sm">
            <div className="flex items-center justify-between px-4 py-2 bg-[var(--bg)] border-b border-[var(--border)] text-[10px] text-[var(--text-3)]">
                <span className="font-bold uppercase tracking-widest text-[var(--sutra-charcoal)]">{language || 'code'}</span>
                <button
                    onClick={handleCopy}
                    className="flex items-center gap-1.5 text-[var(--text-3)] hover:text-[var(--sutra-charcoal)] transition-colors uppercase tracking-widest font-bold"
                >
                    {copied ? <Check className="w-3 h-3 text-[var(--green)]" /> : <Copy className="w-3 h-3" />}
                    <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
            </div>
            <pre className="p-4 overflow-x-auto text-[var(--sutra-charcoal)] leading-relaxed select-text font-mono text-[12px]">
                {code}
            </pre>
        </div>
    );
}

function TableBlock({ headers, rows }: { headers: string[]; rows: string[][] }) {
    return (
        <div className="my-4 border border-[var(--border)] rounded-sm overflow-hidden bg-[var(--bg)] shadow-sm">
            <div className="overflow-x-auto">
                <table className="w-full text-left text-[12px] text-[var(--sutra-charcoal)]">
                    <thead className="bg-[var(--bg-2)] text-[var(--sutra-charcoal)] font-bold text-[10px] uppercase tracking-widest border-b border-[var(--border)]">
                        <tr>
                            {headers.map((h, idx) => (
                                <th key={idx} className="p-3">{renderInline(h.trim())}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                        {rows.map((row, rIdx) => (
                            <tr key={rIdx} className="hover:bg-[var(--bg-2)] transition-colors">
                                {row.map((cell, cIdx) => (
                                    <td key={cIdx} className="p-3 text-[var(--text-2)] font-light">{renderInline(cell.trim())}</td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function TextGroup({ text }: { text: string }) {
    const lines = text.split('\n');
    return (
        <>
            {lines.map((line, i) => {
                const trimmed = line.trim();

                if (!trimmed) {
                    return <div key={i} className="h-2" />;
                }

                if (trimmed.startsWith('#### ')) {
                    return (
                        <h4 key={i} className="text-[11px] font-bold text-[var(--sutra-charcoal)] uppercase tracking-widest mt-5 mb-2">
                            {renderInline(trimmed.slice(5))}
                        </h4>
                    );
                }
                if (trimmed.startsWith('### ')) {
                    return (
                        <h3 key={i} className="text-sm font-semibold text-[var(--sutra-charcoal)] mt-5 mb-2 uppercase tracking-wide">
                            {renderInline(trimmed.slice(4))}
                        </h3>
                    );
                }
                if (trimmed.startsWith('## ')) {
                    return (
                        <h2 key={i} className="text-lg font-serif text-[var(--sutra-charcoal)] mt-6 mb-3 pb-2 border-b border-[var(--border)]">
                            {renderInline(trimmed.slice(3))}
                        </h2>
                    );
                }
                if (trimmed.startsWith('# ')) {
                    return (
                        <h1 key={i} className="text-xl font-serif text-[var(--sutra-charcoal)] mt-8 mb-4">
                            {renderInline(trimmed.slice(2))}
                        </h1>
                    );
                }

                if (trimmed.startsWith('> ')) {
                    return (
                        <blockquote key={i} className="pl-4 py-2 my-3 border-l-2 border-[var(--sutra-muted-gold)] text-[var(--text-2)] bg-[var(--bg-2)] text-[12px] italic">
                            {renderInline(trimmed.slice(2))}
                        </blockquote>
                    );
                }

                if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                    return (
                        <li key={i} className="ml-5 list-disc text-[var(--sutra-charcoal)] my-1.5 pl-1 marker:text-[var(--sutra-muted-gold)]">
                            {renderInline(trimmed.slice(2))}
                        </li>
                    );
                }

                const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
                if (numMatch) {
                    return (
                        <li key={i} className="ml-5 list-decimal text-[var(--sutra-charcoal)] my-1.5 pl-1 marker:text-[var(--sutra-muted-gold)]">
                            {renderInline(numMatch[2])}
                        </li>
                    );
                }

                return (
                    <p key={i} className="my-2 text-[var(--sutra-charcoal)] leading-relaxed">
                        {renderInline(line)}
                    </p>
                );
            })}
        </>
    );
}

function renderInline(text: string) {
    // Split inline code blocks (`code`)
    const codeParts = text.split(/(`[^`]+`)/g);
    return codeParts.map((part, idx) => {
        if (part.startsWith('`') && part.endsWith('`')) {
            return (
                <code key={idx} className="px-1.5 py-0.5 mx-0.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] text-[var(--sutra-charcoal)] font-mono text-[12px]">
                    {part.slice(1, -1)}
                </code>
            );
        }
        // Handle bold (**text**)
        const boldParts = part.split(/(\*\*.*?\*\*)/g);
        return boldParts.map((p, j) => {
            if (p.startsWith('**') && p.endsWith('**')) {
                return (
                    <strong key={`${idx}-${j}`} className="text-[var(--sutra-charcoal)] font-semibold">
                        {p.slice(2, -2)}
                    </strong>
                );
            }
            return <span key={`${idx}-${j}`}>{p}</span>;
        });
    });
}

type Block =
    | { type: 'code'; language: string; content: string }
    | { type: 'table'; headers: string[]; rows: string[][] }
    | { type: 'text'; content: string };

function parseMarkdownBlocks(raw: string): Block[] {
    const blocks: Block[] = [];
    const lines = raw.split('\n');
    let i = 0;

    while (i < lines.length) {
        const line = lines[i];

        // Detect Code Block (```lang)
        if (line.trim().startsWith('```')) {
            const language = line.trim().slice(3).trim();
            i++;
            const codeLines: string[] = [];
            while (i < lines.length && !lines[i].trim().startsWith('```')) {
                codeLines.push(lines[i]);
                i++;
            }
            if (i < lines.length) i++; // skip closing ```
            blocks.push({ type: 'code', language, content: codeLines.join('\n') });
            continue;
        }

        // Detect Table (| col | col |)
        if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
            const tableLines: string[] = [];
            while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
                tableLines.push(lines[i].trim());
                i++;
            }
            if (tableLines.length >= 2) {
                const headers = tableLines[0]
                    .slice(1, -1)
                    .split('|')
                    .map((h) => h.trim());
                const rowLines = tableLines.slice(2); // skip separator row (|---|---|)
                const rows = rowLines.map((rl) =>
                    rl
                        .slice(1, -1)
                        .split('|')
                        .map((c) => c.trim())
                );
                blocks.push({ type: 'table', headers, rows });
                continue;
            }
        }

        // Text block
        const textLines: string[] = [];
        while (
            i < lines.length &&
            !lines[i].trim().startsWith('```') &&
            !(lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|'))
        ) {
            textLines.push(lines[i]);
            i++;
        }
        if (textLines.length > 0) {
            blocks.push({ type: 'text', content: textLines.join('\n') });
        }
    }

    return blocks;
}
