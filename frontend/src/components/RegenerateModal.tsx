'use client';

import React, { useState, useEffect } from 'react';
import {
  Lightbulb,
  ArrowClockwise,
  CircleNotch,
  WarningCircle,
  ClockCounterClockwise,
  CreditCard
} from '@phosphor-icons/react/dist/ssr';
import { artifactApi } from '@/lib/api';
import { Artifact, ArtifactType } from '@/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';

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
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<Artifact[]>([]);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setHistoryLoading(true);
    setHistoryError(null);
    artifactApi
      .getHistory(solutionId, artifactType)
      .then((hist) => {
        if (!cancelled) setHistory(hist);
      })
      .catch((err) => {
        if (cancelled) return;
        setHistory([]);
        setHistoryError(err instanceof Error ? err.message : 'Could not load version history.');
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
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
      setError('Regeneration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <div className="p-2 rounded bg-primary/20 text-primary">
              <ArrowClockwise className="w-4 h-4" />
            </div>
            Scoped Artifact Regeneration
          </DialogTitle>
          <DialogDescription>
            Refine <strong>{currentTitle}</strong> without re-running the full pipeline
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-5">
          {error && (
            <div className="p-3 rounded bg-destructive/10 border border-destructive/20 text-destructive text-xs flex items-center gap-2">
              <WarningCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleRegenerate} className="flex flex-col gap-4">
            <div>
              <label className="block text-xs font-semibold text-muted-foreground mb-1.5">
                Instruction & Customization Feedback
              </label>
              <Textarea
                rows={3}
                required
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="e.g. 'Add real-time webhook sync for inventory updates', 'Include discount coupons in checkout schema'..."
                className="text-xs"
              />
            </div>

            <Card className="bg-primary/5 border-primary/20">
              <CardContent className="p-3 flex items-center justify-between text-xs text-primary">
                <div className="flex items-center gap-2">
                  <CreditCard className="w-4 h-4 text-primary" />
                  <span>Scoped Regeneration Cost:</span>
                </div>
                <span className="font-bold text-foreground">50 Credits (75% savings)</span>
              </CardContent>
            </Card>

            <div className="flex items-center justify-end gap-2">
              <Button type="button" variant="outline" size="sm" onClick={onClose}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant="default"
                size="sm"
                disabled={loading || !feedback.trim()}
              >
                {loading ? <CircleNotch className="w-3.5 h-3.5 animate-spin" /> : <Lightbulb className="w-3.5 h-3.5" />}
                <span>Regenerate Component</span>
              </Button>
            </div>
          </form>

          <Separator />

          <div className="flex flex-col gap-2">
            <h4 className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5 uppercase tracking-wider">
              <ClockCounterClockwise className="w-3.5 h-3.5 text-muted-foreground" />
              <span>Version History</span>
            </h4>

            <div className="flex flex-col gap-1.5 max-h-32 overflow-y-auto">
              {historyLoading ? (
                <>
                  <div className="h-9 animate-pulse rounded bg-secondary" />
                  <div className="h-9 animate-pulse rounded bg-secondary" />
                </>
              ) : historyError ? (
                <p className="text-xs text-destructive">{historyError}</p>
              ) : history.length === 0 ? (
                <p className="text-xs text-muted-foreground">No saved versions yet.</p>
              ) : history.map((item) => (
                <Card key={item.id} className="bg-card border-border">
                  <CardContent className="p-2.5 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-[10px] font-mono font-bold px-2 py-0.5">
                        v{item.version}
                      </Badge>
                      <span className="text-muted-foreground truncate max-w-xs">{item.title}</span>
                    </div>
                    <span className="text-[10px] text-muted-foreground">
                      {new Date(item.created_at).toLocaleDateString()}
                    </span>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
