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
        <div className={`space-y-3 text-[13px] leading-relaxed text-[#d1d1d1] ${className}`}>
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
        <div className="my-3 rounded-lg bg-[#0a0a0a] border border-[#242424] overflow-hidden font-mono text-xs">
            <div className="flex items-center justify-between px-3 py-1.5 bg-[#141414] border-b border-[#242424] text-[11px] text-[#666]">
                <span className="font-semibold uppercase text-[#818cf8] tracking-wider">{language || 'code'}</span>
                <button
                    onClick={handleCopy}
                    className="flex items-center gap-1 text-[#666] hover:text-white transition-colors"
                >
                    {copied ? <Check className="w-3 h-3 text-[#4ade80]" /> : <Copy className="w-3 h-3" />}
                    <span>{copied ? 'Copied' : 'Copy'}</span>
                </button>
            </div>
            <pre className="p-3.5 overflow-x-auto text-[#e2e8f0] leading-relaxed select-text font-mono text-[12px]">
                {code}
            </pre>
        </div>
    );
}

function TableBlock({ headers, rows }: { headers: string[]; rows: string[][] }) {
    return (
        <div className="my-3 border border-[#242424] rounded-lg overflow-hidden bg-[#0a0a0a]">
            <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-[#d1d1d1]">
                    <thead className="bg-[#141414] text-[#818cf8] font-semibold text-[11px] uppercase tracking-wider border-b border-[#242424]">
                        <tr>
                            {headers.map((h, idx) => (
                                <th key={idx} className="p-2.5">{renderInline(h.trim())}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1e1e1e]">
                        {rows.map((row, rIdx) => (
                            <tr key={rIdx} className="hover:bg-[#111] transition-colors">
                                {row.map((cell, cIdx) => (
                                    <td key={cIdx} className="p-2.5 text-[#a1a1a1]">{renderInline(cell.trim())}</td>
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
                    return <div key={i} className="h-1" />;
                }

                if (trimmed.startsWith('#### ')) {
                    return (
                        <h4 key={i} className="text-xs font-semibold text-[#818cf8] uppercase tracking-wider mt-4 mb-1">
                            {renderInline(trimmed.slice(5))}
                        </h4>
                    );
                }
                if (trimmed.startsWith('### ')) {
                    return (
                        <h3 key={i} className="text-sm font-semibold text-white mt-4 mb-1">
                            {renderInline(trimmed.slice(4))}
                        </h3>
                    );
                }
                if (trimmed.startsWith('## ')) {
                    return (
                        <h2 key={i} className="text-base font-bold text-white mt-5 mb-2 pb-1 border-b border-[#242424]">
                            {renderInline(trimmed.slice(3))}
                        </h2>
                    );
                }
                if (trimmed.startsWith('# ')) {
                    return (
                        <h1 key={i} className="text-lg font-extrabold text-white mt-6 mb-2">
                            {renderInline(trimmed.slice(2))}
                        </h1>
                    );
                }

                if (trimmed.startsWith('> ')) {
                    return (
                        <blockquote key={i} className="pl-3 py-1 my-2 border-l-2 border-[#6366f1] text-[#a1a1a1] bg-[#111] rounded-r-lg text-xs italic">
                            {renderInline(trimmed.slice(2))}
                        </blockquote>
                    );
                }

                if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                    return (
                        <li key={i} className="ml-4 list-disc text-[#d1d1d1] my-1">
                            {renderInline(trimmed.slice(2))}
                        </li>
                    );
                }

                const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
                if (numMatch) {
                    return (
                        <li key={i} className="ml-4 list-decimal text-[#d1d1d1] my-1">
                            {renderInline(numMatch[2])}
                        </li>
                    );
                }

                return (
                    <p key={i} className="my-1 text-[#d1d1d1]">
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
                <code key={idx} className="px-1.5 py-0.5 rounded bg-[#181818] border border-[#2a2a2a] text-[#818cf8] font-mono text-[11px]">
                    {part.slice(1, -1)}
                </code>
            );
        }
        // Handle bold (**text**)
        const boldParts = part.split(/(\*\*.*?\*\*)/g);
        return boldParts.map((p, j) => {
            if (p.startsWith('**') && p.endsWith('**')) {
                return (
                    <strong key={`${idx}-${j}`} className="text-white font-semibold">
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
