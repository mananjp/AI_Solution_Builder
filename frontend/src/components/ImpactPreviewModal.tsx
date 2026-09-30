'use client';

import React, { useEffect, useState } from 'react';
import { solutionApi } from '@/lib/api';
import { Dialog } from '@/components/lab/dialog';

import { Button } from '@/components/ui/button';

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
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !solutionId || !targetArtifact) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setConfirmError(null);

    // dry_run only computes the dependency impact + credit quote — it must NOT
    // mark artifacts stale just because the user opened the preview.
    solutionApi
      .regenerateCascade(solutionId, [targetArtifact], 'Impact evaluation', cascade, true)
      .then((data) => {
        setAffected(data.affected_artifacts || [targetArtifact]);
        setEstimatedCredits(data.estimated_credits || 2);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [isOpen, solutionId, targetArtifact, cascade]);

  const handleConfirmRegenerate = async () => {
    setConfirming(true);
    setConfirmError(null);
    try {
      // Real (non-dry-run) pass: marks downstream artifacts stale so they can be
      // regenerated, and returns the same impact list for confirmation.
      await solutionApi.regenerateCascade(
        solutionId,
        [targetArtifact],
        'Regeneration confirmed from impact preview',
        cascade,
        false
      );
      onConfirmRegenerate(cascade);
    } catch {
      setConfirmError('Regeneration failed. Please close and try again.');
      setConfirming(false);
    }
  };

  if (!isOpen) return null;

  return (
    /* The lab dialog supplies the overlay, Escape handling, focus trap and
       `aria-modal`, none of which the previous fixed div had. */
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={
        <span className="flex items-center gap-2">
          <span className="text-[var(--sutra-strong)]">⚡</span> Impact Preview &amp; Credit
          Quote
        </span>
      }
      description={
        <>
          Preview how modifying{' '}
          <span className="font-mono text-[var(--sutra-strong)] font-semibold">
            {targetArtifact}
          </span>{' '}
          cascades to dependent artifacts.
        </>
      }
    >
      <div className="space-y-5">
        {/* Toggle Cascade */}
        <div className="p-3.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] flex items-center justify-between">
          <div>
            <span className="text-sm font-medium text-[var(--sutra-ink)]">Cascade Regeneration</span>
            <p className="text-xs text-[var(--text-2)] font-light">
              Automatically keep downstream schemas, APIs, and code aligned.
            </p>
          </div>
          <input
            type="checkbox"
            checked={cascade}
            onChange={(e) => setCascade(e.target.checked)}
            className="w-4 h-4 accent-[var(--sutra-strong)] rounded-xs cursor-pointer"
          />
        </div>

        {/* Affected Artifacts */}
        <div className="space-y-2">
          <span className="text-xs uppercase tracking-wider font-semibold text-[var(--text-2)]">
            Affected Artifacts ({affected.length})
          </span>
          {loading ? (
            <div className="py-6 text-center text-xs text-[var(--text-3)] font-mono">
              Calculating dependency cascade...
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {affected.map((item) => (
                <span
                  key={item}
                  className={`px-2.5 py-1 rounded-sm text-xs font-mono border ${
                    item === targetArtifact
                      ? 'bg-[var(--sutra-strong)]/15 text-[var(--sutra-strong)] border-[var(--sutra-strong)]/40 font-semibold'
                      : 'bg-[var(--bg-3)] text-[var(--text)] border-[var(--border)]'
                  }`}
                >
                  {item} {item === targetArtifact ? '(Source)' : '(Cascaded)'}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Upfront Credit Quote */}
        <div className="p-3.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] flex items-center justify-between">
          <div className="space-y-0.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--sutra-strong)]">
              Pre-Flight Credit Cost
            </span>
            <div className="text-xs text-[var(--text-2)]">
              {affected.length} node(s) × 2 credits per node
            </div>
          </div>
          <span className="text-xl font-bold font-mono text-[var(--sutra-ink)]">
            {estimatedCredits} Credits
          </span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-2">
          {confirmError && (
            <div className="p-3 rounded-sm bg-[var(--red-wash)] border border-[var(--red-wash)] text-xs text-[var(--red)]">
              {confirmError}
            </div>
          )}
          <Button type="button" variant="ghost" size="sm" onClick={onClose} className="text-xs">
            Cancel
          </Button>
          <Button type="button" size="sm"
            onClick={handleConfirmRegenerate}
            disabled={confirming || loading}
           
           className="text-xs font-semibold shadow-sm transition-all disabled:opacity-50">
            {confirming ? 'Regenerating...' : `Regenerate (${estimatedCredits} Credits)`}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
