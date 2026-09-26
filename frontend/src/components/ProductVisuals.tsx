'use client';

import React, { useEffect, useState } from 'react';
import { AlertTriangle, ImageOff, Loader2, Sparkles } from 'lucide-react';
import { artifactApi } from '@/lib/api';
import type { Artifact } from '@/types';

interface ImageMeta {
  storage_key?: string;
  mime_type?: string;
  bytes?: number;
  aspect_ratio?: string;
}

interface VisualEntry {
  artifact: Artifact;
  meta: ImageMeta;
  prompt: string;
  model: string;
}

function readEntry(artifact: Artifact): VisualEntry {
  const content = (artifact.content || {}) as {
    image?: ImageMeta;
    prompt?: string;
    model?: string;
  };
  return {
    artifact,
    meta: content.image || {},
    prompt: typeof content.prompt === 'string' ? content.prompt : '',
    model: typeof content.model === 'string' ? content.model : '',
  };
}

function formatBytes(n?: number): string {
  if (!n || n <= 0) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

const KIND_LABEL: Record<string, string> = {
  hero_image: 'Hero Visual',
  ui_mockup: 'UI Mockup',
  app_icon: 'App Icon',
};

function VisualCard({ entry }: { entry: VisualEntry }) {
  const { artifact, meta, prompt, model } = entry;
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    artifactApi
      .getImageObjectUrl(artifact.id)
      .then((u) => {
        if (cancelled) {
          URL.revokeObjectURL(u);
          return;
        }
        objectUrl = u;
        setUrl(u);
      })
      .catch(() => {
        if (!cancelled) setError('unavailable');
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [artifact.id]);

  return (
    <div className="sutra-card overflow-hidden flex flex-col">
      <div className="relative bg-[var(--bg-3)] border-b border-[var(--border)] flex items-center justify-center min-h-[220px]">
        {error ? (
          <div className="flex flex-col items-center gap-2 py-12 text-[var(--text-3)]">
            <ImageOff className="w-6 h-6" />
            <span className="text-[10px] uppercase tracking-widest">Image unavailable</span>
          </div>
        ) : url ? (
          // Generated art is untrusted-by-origin; plain <img> (not next/image)
          // keeps the blob: URL working without remote-loader configuration.
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={url}
            alt={artifact.title}
            className="w-full h-auto max-h-[520px] object-contain"
          />
        ) : (
          <div className="flex flex-col items-center gap-2 py-12 text-[var(--text-3)]">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-[10px] uppercase tracking-widest">Loading</span>
          </div>
        )}
      </div>

      <div className="p-4 space-y-3 flex-1 flex flex-col">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Sparkles className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)] shrink-0" />
            <h4 className="font-serif text-[var(--sutra-charcoal)] text-sm leading-tight">
              {KIND_LABEL[artifact.artifact_type] || artifact.title}
            </h4>
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] uppercase tracking-widest text-[var(--text-3)] font-semibold">
            <span>v{artifact.version}</span>
            {meta.aspect_ratio && <span>{meta.aspect_ratio}</span>}
            {formatBytes(meta.bytes) && <span>{formatBytes(meta.bytes)}</span>}
            {model && <span className="truncate max-w-[180px]">{model}</span>}
          </div>
        </div>

        {prompt && (
          <div className="mt-auto">
            <button
              onClick={() => setShowPrompt((v) => !v)}
              className="text-[10px] uppercase tracking-widest font-semibold text-[var(--sutra-muted-gold)] hover:underline"
            >
              {showPrompt ? '− Hide prompt' : '+ Generation prompt'}
            </button>
            {showPrompt && (
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words bg-[var(--bg-2)] border border-[var(--border)] p-3 text-[10px] leading-relaxed text-[var(--text-2)] font-mono">
                {prompt}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ProductVisuals({ artifacts }: { artifacts: Artifact[] }) {
  if (artifacts.length === 0) {
    return (
      <div className="h-[50vh] flex flex-col items-center justify-center text-center space-y-4 text-[var(--text-2)] p-8">
        <div className="p-4 border border-[var(--border)] bg-[var(--bg-2)]">
          <ImageOff className="w-8 h-8 text-[var(--sutra-muted-gold)] opacity-80" />
        </div>
        <div>
          <p className="text-[13px] font-medium text-[var(--sutra-charcoal)]">
            No visuals generated yet.
          </p>
          <p className="text-[11px] text-[var(--text-2)] max-w-sm mx-auto mt-2 font-light">
            Product visuals are generated during the build once a Gemini image key is configured.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between pb-4 border-b border-[var(--border)]">
        <div>
          <h3 className="text-xl font-serif text-[var(--sutra-charcoal)]">Product Visuals</h3>
          <p className="text-[11px] text-[var(--text-2)] mt-2 font-light">
            Generated from the domain specification during the build. Each visual keeps the exact
            prompt that produced it.
          </p>
        </div>
        <span className="badge badge-gray text-[10px] uppercase tracking-widest shrink-0">
          {artifacts.length} visual{artifacts.length === 1 ? '' : 's'}
        </span>
      </div>

      {artifacts.some((a) => !a.content || !(a.content as { image?: unknown }).image) && (
        <div className="flex items-start gap-2 text-[11px] text-[var(--text-2)] bg-[var(--bg-2)] border border-[var(--border)] p-3">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-[var(--sutra-muted-gold)]" />
          <span>Some visuals have no stored image payload and cannot be displayed.</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {artifacts.map((artifact) => (
          <VisualCard key={artifact.id} entry={readEntry(artifact)} />
        ))}
      </div>
    </div>
  );
}
