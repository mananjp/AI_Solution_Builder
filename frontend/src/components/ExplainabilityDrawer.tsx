'use client';

import React, { useEffect, useState } from 'react';
import { getAuthToken } from '@/lib/api';

interface Decision {
  id: string;
  topic: string;
  choice: string;
  rationale: string;
  alternatives: string[];
  assumptions: string[];
  evidence: Array<{ source: string; excerpt: string }>;
  confidence: number;
  impact: string;
}

interface ExplainabilityData {
  artifact_id: string;
  artifact_type: string;
  title: string;
  decisions: Decision[];
  assumptions: string[];
  evidence: Array<{ source: string; excerpt: string }>;
  confidence: number;
}

interface ExplainabilityDrawerProps {
  artifactId: string;
  isOpen: boolean;
  onClose: () => void;
  onAssumptionEdit?: (assumption: string) => void;
}

export function ExplainabilityDrawer({
  artifactId,
  isOpen,
  onClose,
  onAssumptionEdit,
}: ExplainabilityDrawerProps) {
  const [data, setData] = useState<ExplainabilityData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen || !artifactId) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    const token = getAuthToken();
    fetch(`/api/v1/artifacts/${artifactId}/explain`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [artifactId, isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-xs transition-opacity animate-in fade-in">
      <div className="relative w-full max-w-md h-full bg-[var(--bg)] border-l border-[var(--border)] p-6 flex flex-col overflow-y-auto text-[var(--sutra-charcoal)] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[var(--border)]">
          <div className="flex items-center gap-2">
            <span className="font-serif font-bold text-base text-[var(--sutra-charcoal)] flex items-center gap-1.5">
              <span className="text-[var(--sutra-muted-gold)]">💡</span> Architectural Why?
            </span>
            {data && (
              <span className="px-2 py-0.5 text-xs font-mono rounded-sm bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                {Math.round(data.confidence * 100)}% Confidence
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-sm text-[var(--text-3)] hover:text-[var(--text)] hover:bg-[var(--bg-3)] transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-16 text-[var(--text-3)] text-xs font-mono">
            Tracing decisions and evidence citations...
          </div>
        ) : data ? (
          <div className="space-y-6 pt-4">
            {/* Decisions */}
            <div>
              <h4 className="text-xs uppercase tracking-wider text-[var(--text-2)] font-semibold mb-3">
                Key Decisions ({data.decisions.length})
              </h4>
              <div className="space-y-3">
                {data.decisions.map((dec) => (
                  <div
                    key={dec.id}
                    className="p-3.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] text-xs space-y-2 shadow-2xs"
                  >
                    <div className="flex justify-between items-start gap-2">
                      <span className="font-medium text-[var(--sutra-charcoal)]">{dec.topic}</span>
                      <span className="text-xs px-2 py-0.5 rounded-sm bg-[var(--sutra-muted-gold)]/15 text-[var(--sutra-deep-gold)] border border-[var(--sutra-muted-gold)]/30 font-semibold font-mono whitespace-nowrap">
                        {dec.choice}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-2)] leading-relaxed font-light">{dec.rationale}</p>

                    {dec.alternatives?.length > 0 && (
                      <div className="text-xs text-[var(--text-3)]">
                        <span className="text-[var(--text-2)] font-medium">Alternatives evaluated: </span>
                        {dec.alternatives.join(', ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Assumptions */}
            {data.assumptions?.length > 0 && (
              <div>
                <h4 className="text-xs uppercase tracking-wider text-[var(--text-2)] font-semibold mb-2">
                  Underlying Assumptions
                </h4>
                <ul className="space-y-2">
                  {data.assumptions.map((asm, idx) => (
                    <li
                      key={idx}
                      className="p-2.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] text-xs text-[var(--sutra-charcoal)] flex justify-between items-center"
                    >
                      <span className="font-light">{asm}</span>
                      {onAssumptionEdit && (
                        <button
                          onClick={() => onAssumptionEdit(asm)}
                          className="text-[11px] text-[var(--sutra-muted-gold)] hover:underline ml-2 font-medium"
                        >
                          Edit
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Evidence Sources */}
            {data.evidence?.length > 0 && (
              <div>
                <h4 className="text-xs uppercase tracking-wider text-[var(--text-2)] font-semibold mb-2">
                  Evidence Citations ({data.evidence.length})
                </h4>
                <div className="space-y-2">
                  {data.evidence.map((ev, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] text-xs"
                    >
                      <span className="font-mono text-emerald-700 text-[11px] font-semibold">[{ev.source}]</span>
                      <p className="text-[var(--text-2)] italic mt-0.5 font-light">&ldquo;{ev.excerpt}&rdquo;</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="py-12 text-center text-xs text-[var(--text-3)] font-mono">
            No explainability records found for this artifact.
          </div>
        )}
      </div>
    </div>
  );
}
