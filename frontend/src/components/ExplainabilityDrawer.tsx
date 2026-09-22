'use client';

import React, { useEffect, useState } from 'react';

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
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
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
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-xs transition-opacity animate-in fade-in">
      <div className="relative w-full max-w-md h-full bg-slate-900 border-l border-slate-800 p-6 flex flex-col overflow-y-auto text-slate-100 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 font-semibold text-lg">💡 Architectural Why?</span>
            {data && (
              <span className="px-2 py-0.5 text-xs font-mono rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800">
                {Math.round(data.confidence * 100)}% Confidence
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex items-center justify-center py-16 text-slate-400 text-sm">
            Tracing decisions and evidence citations...
          </div>
        ) : data ? (
          <div className="space-y-6 pt-4">
            {/* Decisions */}
            <div>
              <h4 className="text-xs uppercase tracking-wider text-slate-400 font-semibold mb-3">
                Key Decisions ({data.decisions.length})
              </h4>
              <div className="space-y-3">
                {data.decisions.map((dec) => (
                  <div
                    key={dec.id}
                    className="p-3.5 rounded-lg bg-slate-800/80 border border-slate-700/60 text-sm space-y-2"
                  >
                    <div className="flex justify-between items-start">
                      <span className="font-medium text-slate-200">{dec.topic}</span>
                      <span className="text-xs px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                        {dec.choice}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">{dec.rationale}</p>

                    {dec.alternatives?.length > 0 && (
                      <div className="text-xs text-slate-500">
                        <span className="text-slate-400">Alternatives evaluated: </span>
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
                <h4 className="text-xs uppercase tracking-wider text-slate-400 font-semibold mb-2">
                  Underlying Assumptions
                </h4>
                <ul className="space-y-2">
                  {data.assumptions.map((asm, idx) => (
                    <li
                      key={idx}
                      className="p-2.5 rounded bg-slate-950/60 border border-slate-800 text-xs text-slate-300 flex justify-between items-center"
                    >
                      <span>{asm}</span>
                      {onAssumptionEdit && (
                        <button
                          onClick={() => onAssumptionEdit(asm)}
                          className="text-[11px] text-indigo-400 hover:text-indigo-300 ml-2"
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
                <h4 className="text-xs uppercase tracking-wider text-slate-400 font-semibold mb-2">
                  Evidence Citations ({data.evidence.length})
                </h4>
                <div className="space-y-2">
                  {data.evidence.map((ev, idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded bg-slate-950/40 border border-slate-800/80 text-xs"
                    >
                      <span className="font-mono text-emerald-400 text-[11px]">[{ev.source}]</span>
                      <p className="text-slate-400 italic mt-0.5">&ldquo;{ev.excerpt}&rdquo;</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="py-12 text-center text-sm text-slate-500">
            No explainability records found for this artifact.
          </div>
        )}
      </div>
    </div>
  );
}
