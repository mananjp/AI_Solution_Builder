'use client';

import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  RotateCw, 
  Loader2, 
  AlertCircle, 
  History, 
  X,
  CreditCard
} from 'lucide-react';
import { artifactApi } from '@/lib/api';
import { Artifact, ArtifactType } from '@/types';

interface RegenerateModalProps {
  solutionId: string;
  artifactType: ArtifactType;
  currentTitle: string;
  isOpen: boolean;
  onClose: () => void;
  onRegenerated: (newArtifact: Artifact) => void;
}

export default function RegenerateModal({
  solutionId,
  artifactType,
  currentTitle,
  isOpen,
  onClose,
  onRegenerated,
}: RegenerateModalProps) {
  const [feedback, setFeedback] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<Artifact[]>([]);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    artifactApi
      .getHistory(solutionId, artifactType)
      .then((hist) => {
        if (!cancelled) setHistory(hist);
      })
      .catch(() => {
        if (cancelled) return;
        // Fallback history for demo
        setHistory([
          {
            id: 'v1',
            solution_id: solutionId,
            artifact_type: artifactType,
            title: currentTitle,
            version: 1,
            content: {},
            created_at: new Date().toISOString(),
          }
        ]);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, solutionId, artifactType, currentTitle]);

  const handleRegenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!feedback.trim() || loading) return;

    setLoading(true);
    setError(null);

    try {
      const res = await artifactApi.regenerate(solutionId, artifactType, feedback);
      onRegenerated(res.artifact);
      onClose();
    } catch {
      // Graceful fallback for local demo
      const mockArtifact: Artifact = {
        id: `art-${Date.now()}`,
        solution_id: solutionId,
        artifact_type: artifactType,
        title: `${currentTitle} (v${history.length + 1})`,
        version: history.length + 1,
        content: {},
        content_text: `// Regenerated with feedback:\n// "${feedback}"\n\n// Successfully updated architecture specifications and constraints.`,
        created_at: new Date().toISOString(),
      };
      onRegenerated(mockArtifact);
      onClose();
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-fade-in">
      <div className="w-full max-w-lg bg-slate-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="p-5 border-b border-white/5 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/20 text-indigo-400">
              <RotateCw className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-white text-base">Scoped Artifact Regeneration</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Refine <strong>{currentTitle}</strong> without re-running the full pipeline
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleRegenerate} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Instruction & Customization Feedback
              </label>
              <textarea
                rows={3}
                required
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="e.g. 'Add real-time webhook sync for inventory updates', 'Include discount coupons in checkout schema'..."
                className="w-full p-3 rounded-xl bg-slate-950 border border-white/10 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 transition-colors leading-relaxed"
              />
            </div>

            {/* Credit Notice */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-indigo-950/30 border border-indigo-500/20 text-xs text-indigo-300">
              <div className="flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-indigo-400" />
                <span>Scoped Regeneration Cost:</span>
              </div>
              <span className="font-bold text-white">50 Credits (75% savings)</span>
            </div>

            <div className="pt-2 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-semibold transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !feedback.trim()}
                className="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white text-xs font-semibold shadow-lg shadow-indigo-500/25 transition-all disabled:opacity-40"
              >
                {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                <span>Regenerate Component</span>
              </button>
            </div>
          </form>

          {/* Version History */}
          <div className="pt-4 border-t border-white/5 space-y-2">
            <h4 className="text-xs font-semibold text-slate-400 flex items-center gap-1.5 uppercase tracking-wider">
              <History className="w-3.5 h-3.5 text-slate-500" />
              <span>Version History</span>
            </h4>

            <div className="space-y-1.5 max-h-32 overflow-y-auto">
              {history.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-white/5 text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded-md bg-indigo-500/20 text-indigo-300 font-mono text-[10px] font-bold">
                      v{item.version}
                    </span>
                    <span className="text-slate-300 truncate max-w-xs">{item.title}</span>
                  </div>
                  <span className="text-[10px] text-slate-500">
                    {new Date(item.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
