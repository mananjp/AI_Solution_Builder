'use client';

import React, { useState } from 'react';
import {
  Download,
  FileCode,
  FileText,
  Package,
  GitBranch
} from 'lucide-react';
import { exportApi } from '@/lib/api';
import { Dialog } from '@/components/lab/dialog';

import { Button } from '@/components/ui/button';

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
    /* The lab dialog owns the overlay, the Escape key, the focus trap and
       `aria-modal`. The previous version was a bare fixed div, so Tab walked
       out of the dialog into the page behind it and Escape did nothing. */
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title="Export Engineering Blueprint"
      description="Choose target format or deployment bundle"
    >
      <div className="space-y-3">
        {exportFormats.map((fmt) => {
          const Icon = fmt.icon;
          const isBusy = downloading === fmt.id;

          return (
            <div
              key={fmt.id}
              className="p-3.5 rounded-sm bg-[var(--bg-2)] border border-[var(--border)] hover:border-[var(--sutra-strong)]/40 transition-colors flex items-start justify-between gap-3"
            >
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-sm bg-[var(--sutra-strong)]/15 text-[var(--sutra-strong)] mt-0.5">
                  <Icon className="w-4 h-4" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="font-semibold text-xs text-[var(--sutra-ink)]">{fmt.name}</h4>
                    <span className="px-2 py-0.5 text-[9px] font-mono uppercase rounded-sm bg-[var(--sutra-strong)]/15 text-[var(--sutra-strong)] border border-[var(--sutra-strong)]/30">
                      {fmt.badge}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--text-2)] mt-1 leading-relaxed max-w-sm font-light">
                    {fmt.desc}
                  </p>
                </div>
              </div>

              <Button type="button" size="xs"
                onClick={fmt.handler}
                disabled={isBusy}
               
               className="text-xs font-medium whitespace-nowrap disabled:opacity-50 flex items-center gap-1.5">
                <Download className="w-3.5 h-3.5" />
                <span>{isBusy ? 'Exporting...' : `Download ${fmt.ext}`}</span>
              </Button>
            </div>
          );
        })}

        <div className="p-3 rounded-sm bg-[var(--bg-3)] border border-[var(--border)] flex items-center justify-between text-xs text-[var(--text-2)]">
          <div className="flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-[var(--green)]" />
            <span>Direct GitHub repo deployment supported via ZIP manifest</span>
          </div>
          <span className="text-[10px] text-[var(--green)] font-semibold uppercase">CI/CD Included</span>
        </div>
        {error && (
          <div className="p-3 rounded-sm bg-[var(--red-wash)] border border-[var(--red-wash)] text-xs text-[var(--red)]">
            {error}
          </div>
        )}
      </div>
    </Dialog>
  );
}
