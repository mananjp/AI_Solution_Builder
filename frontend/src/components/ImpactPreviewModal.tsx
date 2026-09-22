'use client';

import React, { useEffect, useState } from 'react';

interface ImpactPreviewModalProps {
  isOpen: boolean;
  solutionId: string;
  targetArtifact: string;
  onClose: () => void;
  onConfirmRegenerate: (cascade: boolean) => void;
}

export function ImpactPreviewModal({
  isOpen,
  solutionId,
  targetArtifact,
  onClose,
  onConfirmRegenerate,
}: ImpactPreviewModalProps) {
  const [cascade, setCascade] = useState(true);
  const [affected, setAffected] = useState<string[]>([]);
  const [estimatedCredits, setEstimatedCredits] = useState<number>(2);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isOpen || !solutionId || !targetArtifact) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

    fetch(`/api/v1/solutions/${solutionId}/regenerate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        targets: [targetArtifact],
        feedback: 'Impact evaluation',
        cascade: cascade,
      }),
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setAffected(data.affected_artifacts || [targetArtifact]);
          setEstimatedCredits(data.estimated_credits || 2);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [isOpen, solutionId, targetArtifact, cascade]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in">
      <div className="w-full max-w-lg rounded-2xl bg-slate-900 border border-slate-800 p-6 shadow-2xl text-slate-100 space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <span>⚡</span> Impact Preview & Credit Quote
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Preview how modifying <span className="font-mono text-indigo-400 font-semibold">{targetArtifact}</span> cascades to dependent artifacts.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800"
          >
            ✕
          </button>
        </div>

        {/* Toggle Cascade */}
        <div className="p-3.5 rounded-xl bg-slate-800/60 border border-slate-700/50 flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-slate-200">Cascade Regeneration</span>
            <p className="text-xs text-slate-400">
              Automatically keep downstream schemas, APIs, and code aligned.
            </p>
          </div>
          <input
            type="checkbox"
            checked={cascade}
            onChange={(e) => setCascade(e.target.checked)}
            className="w-4 h-4 accent-indigo-600 rounded cursor-pointer"
          />
        </div>

        {/* Affected Artifacts */}
        <div className="space-y-2">
          <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">
            Affected Artifacts ({affected.length})
          </span>
          {loading ? (
            <div className="py-6 text-center text-xs text-slate-500">Calculating dependency cascade...</div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {affected.map((item) => (
                <span
                  key={item}
                  className={`px-2.5 py-1 rounded-md text-xs font-mono border ${
                    item === targetArtifact
                      ? 'bg-indigo-950 text-indigo-300 border-indigo-700'
                      : 'bg-amber-950/40 text-amber-300 border-amber-800/60'
                  }`}
                >
                  {item} {item === targetArtifact ? '(Source)' : '(Cascaded)'}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Upfront Credit Quote */}
        <div className="p-3.5 rounded-xl bg-indigo-950/40 border border-indigo-800/60 flex items-center justify-between">
          <div className="space-y-0.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-300">
              Pre-Flight Credit Cost
            </span>
            <div className="text-xs text-slate-400">
              {affected.length} node(s) × 2 credits per node
            </div>
          </div>
          <span className="text-xl font-bold font-mono text-indigo-200">
            {estimatedCredits} Credits
          </span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirmRegenerate(cascade)}
            className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/30 transition-all"
          >
            Regenerate ({estimatedCredits} Credits)
          </button>
        </div>
      </div>
    </div>
  );
}
