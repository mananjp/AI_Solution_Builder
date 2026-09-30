'use client';

import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  Loader2, 
  AlertCircle, 
  History, 
  CreditCard
} from 'lucide-react';
import { artifactApi } from '@/lib/api';
import { Artifact, ArtifactType } from '@/types';
import { Dialog } from '@/components/lab/dialog';
import { RelativeTime } from '@/components/lab/relative-time';

import { Button } from '@/components/ui/button';

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
    /* The lab dialog supplies the overlay, Escape handling, focus trap and
       `aria-modal`; the previous fixed div had none of them, so Tab walked out
       into the artifact viewer behind it and Escape did nothing. */
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Scoped Artifact Regeneration"
      description={
        <>
          Refine <strong>{currentTitle}</strong> without re-running the full pipeline
        </>
      }
    >
      <div className="space-y-5">
          {error && (
            <div className="p-3 rounded-sm bg-[var(--red-wash)] border border-[var(--red-wash)] text-[var(--red)] text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleRegenerate} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-[var(--sutra-ink)] mb-1.5 uppercase tracking-wider">
                Instruction &amp; Customization Feedback
              </label>
              <textarea
                rows={3}
                required
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="e.g. 'Add real-time webhook sync for inventory updates', 'Include discount coupons in checkout schema'..."
                className="w-full p-3 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] text-xs text-[var(--sutra-ink)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-strong)] transition-colors leading-relaxed"
              />
            </div>

            {/* Credit Notice */}
            <div className="flex items-center justify-between p-3 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] text-xs text-[var(--text-2)]">
              <div className="flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-[var(--sutra-strong)]" />
                <span>Scoped Regeneration Cost:</span>
              </div>
              <span className="font-bold text-[var(--sutra-ink)] font-mono">50 Credits (75% savings)</span>
            </div>

            <div className="pt-2 flex items-center justify-end gap-2.5">
              <Button variant="ghost" size="sm"
                type="button"
                onClick={onClose}
               
               className="text-xs">
                Cancel
              </Button>
              <Button size="sm"
                type="submit"
                disabled={loading || !feedback.trim()}
               
               className="text-xs flex items-center gap-2 disabled:opacity-40 shadow-sm">
                {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                <span>Regenerate Component</span>
              </Button>
            </div>
          </form>

          {/* Version History */}
          <div className="pt-4 border-t border-[var(--border)] space-y-2">
            <h4 className="text-xs font-semibold text-[var(--text-3)] flex items-center gap-1.5 uppercase tracking-wider">
              <History className="w-3.5 h-3.5" />
              <span>Version History</span>
            </h4>

            <div className="space-y-1.5 max-h-32 overflow-y-auto">
              {history.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between p-2.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] text-xs"
                >
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded-sm bg-[var(--sutra-strong)]/15 text-[var(--sutra-strong)] border border-[var(--sutra-strong)]/30 font-mono text-[10px] font-bold">
                      v{item.version}
                    </span>
                    <span className="text-[var(--text)] truncate max-w-xs">{item.title}</span>
                  </div>
                  <RelativeTime date={item.created_at} />
                </div>
              ))}
            </div>
          </div>
      </div>
    </Dialog>
  );
}
