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
      // Direct link fallback
      window.open(exportApi.getExportUrl(solutionId, format), '_blank');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-fade-in">
      <div className="w-full max-w-xl bg-slate-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="p-5 border-b border-white/5 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/20 text-cyan-400">
              <Download className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-white text-base">Export Engineering Blueprint</h3>
              <p className="text-xs text-slate-400 mt-0.5">Choose your target format or deployment bundle</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Formats Grid */}
        <div className="p-6 space-y-3">
          {exportFormats.map((fmt) => {
            const Icon = fmt.icon;
            const isBusy = downloading === fmt.id;

            return (
              <div
                key={fmt.id}
                className="p-4 rounded-xl bg-slate-950 border border-white/5 hover:border-indigo-500/30 transition-all flex items-start justify-between gap-4 group"
              >
                <div className="flex items-start gap-3">
                  <div className="p-2.5 rounded-xl bg-white/5 group-hover:bg-indigo-500/20 text-indigo-400 transition-colors mt-0.5">
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-sm text-white">{fmt.name}</h4>
                      <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-white/5 text-slate-400">
                        {fmt.badge}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed max-w-sm">
                      {fmt.desc}
                    </p>
                  </div>
                </div>

                <button
                  onClick={fmt.handler}
                  disabled={isBusy}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all hover:scale-105 whitespace-nowrap disabled:opacity-50"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>{isBusy ? 'Exporting...' : `Download ${fmt.ext}`}</span>
                </button>
              </div>
            );
          })}

          {/* One-Click Deployer Note */}
          <div className="p-3.5 rounded-xl bg-gradient-to-r from-indigo-950/40 to-slate-950 border border-indigo-500/20 flex items-center justify-between text-xs text-slate-300">
            <div className="flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-emerald-400" />
              <span>Direct GitHub repo deployment supported via ZIP manifest</span>
            </div>
            <span className="text-[10px] text-emerald-400 font-semibold uppercase">CI/CD Included</span>
          </div>
        </div>
      </div>
    </div>
  );
}
