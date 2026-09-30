'use client';

import React, { useEffect, useState } from 'react';
import { artifactApi } from '@/lib/api';
import { errorMessage } from '@/lib/errors';
import { Dialog } from '@/components/lab/dialog';
import type { ArtifactExplainability } from '@/types';
import { Button } from "@/components/ui/button";

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
  const [request, setRequest] = useState<{
    artifactId: string;
    data: ArtifactExplainability | null;
    error: string | null;
    loading: boolean;
  } | null>(null);

  useEffect(() => {
    if (!isOpen || !artifactId) return;

    // Aborted on close/unmount so a slow response cannot write to state we no
    // longer render. The previous version also collapsed every non-OK response
    // to `null`, which made a 401 or a 500 indistinguishable from "no data".
    const controller = new AbortController();

    artifactApi
      .explain(artifactId, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return;
        setRequest({ artifactId, data: result, error: null, loading: false });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setRequest({ artifactId, data: null, error: errorMessage(err), loading: false });
      });

    return () => controller.abort();
  }, [artifactId, isOpen]);

  const currentRequest = request?.artifactId === artifactId ? request : null;
  const data = currentRequest?.data ?? null;
  const error = currentRequest?.error ?? null;
  const loading = isOpen && (!currentRequest || currentRequest.loading);

  if (!isOpen) return null;

  return (
    /* Side-anchored rather than centred: this is a drawer the user pulls over
       the page they are reading, so it keeps the source visible. The lab dialog
       supplies Escape handling, a focus trap and `aria-modal`, none of which
       the previous fixed div had. */
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      className="sm:max-w-md"
      title={
        <span className="flex items-center gap-2">
          <span className="text-[var(--sutra-strong)]">💡</span> Architectural Why?
        </span>
      }
      description={
        data ? `${Math.round(data.confidence * 100)}% confidence in this artifact's reasoning` : undefined
      }
    >
      <div className="max-h-[60vh] overflow-y-auto pr-1">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-[var(--text-3)] text-xs font-mono">
            Tracing decisions and evidence citations...
          </div>
        ) : error ? (
          <div
            role="alert"
            className="rounded-sm border border-[var(--red-edge)] bg-[var(--red-wash)] p-4 text-xs text-[var(--red)]"
          >
            <p className="font-semibold uppercase tracking-wider">Could not load explainability</p>
            <p className="mt-1 font-mono font-light">{error}</p>
          </div>
        ) : data && data.decisions.length === 0 ? (
          <div className="py-12 text-center text-xs text-[var(--text-3)] font-mono">
            No reasoning was recorded for this artifact.
          </div>
        ) : data ? (
          <div className="space-y-6">
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
                      <span className="font-medium text-[var(--sutra-ink)]">{dec.topic}</span>
                      <span className="text-xs px-2 py-0.5 rounded-sm bg-[var(--sutra-strong)]/15 text-[var(--sutra-strong)] border border-[var(--sutra-strong)]/30 font-semibold font-mono whitespace-nowrap">
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
                      className="p-2.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] text-xs text-[var(--sutra-ink)] flex justify-between items-center"
                    >
                      <span className="font-light">{asm}</span>
                      {onAssumptionEdit && (
                        <Button variant="ghost" size="default"
                          onClick={() => onAssumptionEdit(asm)}
                          className="text-[11px] text-[var(--sutra-strong)] hover:underline ml-2 font-medium"
                        >
                          Edit
                        </Button>
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
                      <span className="font-mono text-[var(--green)] text-[11px] font-semibold">[{ev.source}]</span>
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
    </Dialog>
  );
}
