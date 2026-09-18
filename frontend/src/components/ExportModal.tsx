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
    try {
      await exportApi.downloadExport(
        solutionId,
        format,
        `${solutionTitle.toLowerCase().replace(/[^a-z0-9]/g, '_')}_export.${format === 'zip' ? 'zip' : format === 'json' ? 'json' : 'md'}`
      );
    } catch {
      window.open(exportApi.getExportUrl(solutionId, format), '_blank');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="w-full max-w-xl bg-[#111] border border-[#1a1a1a] rounded-xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-[#1a1a1a] flex items-center justify-between bg-[#0a0a0a]">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md bg-[#161616] border border-[#242424] text-[#818cf8]">
              <Download className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-semibold text-white text-sm">Export Engineering Blueprint</h3>
              <p className="text-xs text-[#555]">Choose target format or deployment bundle</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-[#1f1f1f] text-[#555] hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Formats Grid */}
        <div className="p-5 space-y-3">
          {exportFormats.map((fmt) => {
            const Icon = fmt.icon;
            const isBusy = downloading === fmt.id;

            return (
              <div
                key={fmt.id}
                className="p-3.5 rounded-lg bg-[#0a0a0a] border border-[#1a1a1a] hover:border-[#2e2e2e] transition-colors flex items-start justify-between gap-3"
              >
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-[#161616] text-[#818cf8] mt-0.5">
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-semibold text-xs text-white">{fmt.name}</h4>
                      <span className="badge badge-gray text-[9px]">
                        {fmt.badge}
                      </span>
                    </div>
                    <p className="text-xs text-[#555] mt-1 leading-relaxed max-w-sm">
                      {fmt.desc}
                    </p>
                  </div>
                </div>

                <button
                  onClick={fmt.handler}
                  disabled={isBusy}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#6366f1] hover:bg-[#5558dd] text-white text-xs font-medium transition-colors whitespace-nowrap disabled:opacity-50"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>{isBusy ? 'Exporting...' : `Download ${fmt.ext}`}</span>
                </button>
              </div>
            );
          })}

          <div className="p-3 rounded-lg bg-[#0a0a0a] border border-[#1a1a1a] flex items-center justify-between text-xs text-[#a1a1a1]">
            <div className="flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-[#4ade80]" />
              <span>Direct GitHub repo deployment supported via ZIP manifest</span>
            </div>
            <span className="text-[10px] text-[#4ade80] font-semibold uppercase">CI/CD Included</span>
          </div>
        </div>
      </div>
    </div>
  );
}
