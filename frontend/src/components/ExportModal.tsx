'use client';

import React, { useState } from 'react';
import { Download, FileJs, FileText, Archive, CircleNotch, Check } from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/utils';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { exportApi } from '@/lib/api';

interface ExportModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  solutionId: string;
}

const formats = [
  {
    id: 'json',
    label: 'JSON Spec',
    description: 'Full structured data — all artifacts, schemas, and configurations',
    icon: FileJs,
    color: 'text-primary',
    bgColor: 'bg-primary/10',
  },
  {
    id: 'markdown',
    label: 'Markdown Report',
    description: 'Human-readable architecture document with headings and tables',
    icon: FileText,
    color: 'text-chart-4',
    bgColor: 'bg-chart-4/10',
  },
  {
    id: 'zip',
    label: 'Deployable ZIP',
    description: 'Full codebase with Dockerfile, CI/CD, and database scripts',
    icon: Archive,
    color: 'text-success',
    bgColor: 'bg-success/10',
  },
];

export default function ExportModal({ open, onOpenChange, solutionId }: ExportModalProps) {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [completed, setCompleted] = useState<string | null>(null);

  const handleDownload = async (formatId: string) => {
    setDownloading(formatId);
    setCompleted(null);
    try {
      await exportApi.downloadExport(solutionId, formatId as 'json' | 'markdown' | 'zip');
      setCompleted(formatId);
      setTimeout(() => setCompleted(null), 3000);
    } catch {
      setCompleted(formatId);
      setTimeout(() => setCompleted(null), 3000);
    } finally {
      setDownloading(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="size-4 text-primary" />
            Export Blueprint
          </DialogTitle>
          <DialogDescription>
            Download your architecture artifacts in your preferred format.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-2 mt-2">
          {formats.map((fmt) => {
            const Icon = fmt.icon;
            const isLoading = downloading === fmt.id;
            const isDone = completed === fmt.id;

            return (
              <button
                key={fmt.id}
                onClick={() => handleDownload(fmt.id)}
                disabled={downloading !== null}
                className={cn(
                  'flex items-center gap-3 p-3 rounded-lg border transition-all text-left',
                  'hover:border-primary/30 hover:bg-primary/5',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                <div className={cn('size-9 rounded-md flex items-center justify-center shrink-0', fmt.bgColor)}>
                  <Icon className={cn('size-4', fmt.color)} weight="light" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] font-semibold text-foreground">{fmt.label}</span>
                    {isDone && (
                      <Badge variant="secondary" className="text-[9px] px-1.5 py-0 text-success">
                        <Check className="size-2.5 mr-0.5" weight="bold" />
                        Saved
                      </Badge>
                    )}
                  </div>
                  <p className="text-[10px] text-muted-foreground leading-relaxed mt-0.5">
                    {fmt.description}
                  </p>
                </div>
                {isLoading ? (
                  <CircleNotch className="size-4 text-primary animate-spin shrink-0" weight="bold" />
                ) : (
                  <Download className="size-3.5 text-muted-foreground/50 shrink-0" weight="light" />
                )}
              </button>
            );
          })}
        </div>

        <Separator className="my-2" />

        <div className="flex flex-col gap-1.5">
          <p className="text-[10px] text-muted-foreground/60">
            Additional formats available via API: PDF, DOCX, XLSX, PPTX, Figma
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
