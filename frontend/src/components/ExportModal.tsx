'use client';

import React, { useState } from 'react';
import {
  Download,
  FileCode,
  FileText,
  Package,
  X,
  GitBranch
} from 'lucide-react';
import { exportApi } from '@/lib/api';

interface ExportModalProps {
  solutionId: string;
  solutionTitle: string;
  isOpen: boolean;
  onClose: () => void;
}

export default function ExportModal({
  solutionId,
  solutionTitle,
  isOpen,
  onClose,
}: ExportModalProps) {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const exportFormats = [
    {
      id: 'zip',
      name: 'Deployable Code Package',
      ext: '.zip',
      desc: 'Complete project scaffold with Dockerfile, docker-compose.yml, init.sql, and GitHub Actions CI/CD.',
      icon: Package,
      badge: 'Production Ready',
      handler: () => handleDownload('zip'),
    },
    {
      id: 'markdown',
      name: 'Architecture Report',
      ext: '.md',
      desc: 'Comprehensive engineering document containing HLD, LLD, roadmap, and design requirements.',
      icon: FileText,
      badge: 'Documentation',
      handler: () => handleDownload('markdown'),
    },
    {
      id: 'json',
      name: 'Full Solution Specification',
      ext: '.json',
      desc: 'Machine-readable declarative JSON schema of all state, modules, wireframes, and database models.',
      icon: FileCode,
      badge: 'Declarative',
      handler: () => handleDownload('json'),
    },
  ];

  const handleDownload = async (format: 'json' | 'markdown' | 'zip') => {
    setDownloading(format);
    setError(null);
    try {
      await exportApi.downloadExport(
        solutionId,
        format,
        `${solutionTitle.toLowerCase().replace(/[^a-z0-9]/g, '_')}_export.${format === 'zip' ? 'zip' : format === 'json' ? 'json' : 'md'}`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed. Please try again.');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-xs z-50 flex items-center justify-center p-4 animate-in fade-in">
      <div className="w-full max-w-xl bg-[var(--bg)] border border-[var(--border)] rounded-sm shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-[var(--border)] flex items-center justify-between bg-[var(--bg-2)]">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-sm bg-[var(--sutra-muted-gold)]/15 text-[var(--sutra-muted-gold)] border border-[var(--sutra-muted-gold)]/30">
              <Download className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-serif font-bold text-[var(--sutra-charcoal)] text-sm">Export Engineering Blueprint</h3>
              <p className="text-xs text-[var(--text-2)] font-light">Choose target format or deployment bundle</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-sm hover:bg-[var(--bg-3)] text-[var(--text-3)] hover:text-[var(--text)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Formats Grid */}
        <div className="p-5 space-y-3 bg-[var(--bg)]">
          {exportFormats.map((fmt) => {
            const Icon = fmt.icon;
            const isBusy = downloading === fmt.id;

            return (
              <div
                key={fmt.id}
                className="p-3.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)]/40 transition-colors flex items-start justify-between gap-3"
              >
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-sm bg-[var(--sutra-muted-gold)]/15 text-[var(--sutra-muted-gold)] mt-0.5">
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-semibold text-xs text-[var(--sutra-charcoal)]">{fmt.name}</h4>
                      <span className="px-2 py-0.5 text-[9px] font-mono uppercase rounded-sm bg-[var(--sutra-muted-gold)]/15 text-[var(--sutra-deep-gold)] border border-[var(--sutra-muted-gold)]/30">
                        {fmt.badge}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--text-2)] mt-1 leading-relaxed max-w-sm font-light">
                      {fmt.desc}
                    </p>
                  </div>
                </div>

                <button
                  onClick={fmt.handler}
                  disabled={isBusy}
                  className="btn btn-primary px-3 py-1.5 text-xs font-medium whitespace-nowrap disabled:opacity-50 flex items-center gap-1.5"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>{isBusy ? 'Exporting...' : `Download ${fmt.ext}`}</span>
                </button>
              </div>
            );
          })}

          <div className="p-3 rounded-sm bg-[var(--bg-3)] border border-[var(--border)] flex items-center justify-between text-xs text-[var(--text-2)]">
            <div className="flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-emerald-600" />
              <span>Direct GitHub repo deployment supported via ZIP manifest</span>
            </div>
            <span className="text-[10px] text-emerald-600 font-semibold uppercase">CI/CD Included</span>
          </div>
          {error && (
            <div className="p-3 rounded-sm bg-rose-500/10 border border-rose-500/20 text-xs text-rose-600">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
