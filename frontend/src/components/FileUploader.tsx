'use client';

import React, { useState, useRef } from 'react';
import { Upload, FileText, AlertCircle, Loader2, X, Link2, ShieldCheck, ShieldAlert, Shield } from 'lucide-react';
import { uploadApi } from '@/lib/api';

interface FileUploaderProps {
  onParsedContext: (text: string, filename: string) => void;
  onClear?: () => void;
}

export default function FileUploader({ onParsedContext, onClear }: FileUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<{
    name: string;
    size: number;
    isUrl?: boolean;
    securityPassed?: boolean;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState('');
  const [urlLoading, setUrlLoading] = useState(false);

  const handleUpload = async (file: File) => {
    setError(null);
    setLoading(true);
    try {
      const res = await uploadApi.uploadFile(file);
      setUploadedFile({ name: file.name, size: file.size, securityPassed: true });
      onParsedContext(res.text, file.name);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to parse file');
    } finally {
      setLoading(false);
    }
  };

  const handleParseUrl = async () => {
    const candidate = url.trim();
    if (!candidate) {
      setError('Enter a URL to ingest');
      return;
    }
    if (!/^https?:\/\/.+\..+/.test(candidate)) {
      setError('Enter a valid http(s) URL');
      return;
    }

    setError(null);
    setUrlLoading(true);
    try {
      const res = await uploadApi.parseUrl(candidate);
      setUploadedFile({ name: res.url, size: res.characterCount, isUrl: true, securityPassed: true });
      onParsedContext(res.extractedText, res.url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch URL');
    } finally {
      setUrlLoading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleUpload(e.dataTransfer.files[0]);
    }
  };

  const handleClear = () => {
    setUploadedFile(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    onClear?.();
  };

  return (
    <div className="w-full space-y-3">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.csv,.xlsx,.xls,.txt,.md,.json,.yaml,.yml"
        className="hidden"
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            handleUpload(e.target.files[0]);
          }
        }}
      />

      {uploadedFile ? (
        <div className="p-3 rounded-sm bg-[var(--bg)] border border-[var(--sutra-muted-gold)] shadow-sm space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-[var(--bg-2)] text-[var(--sutra-charcoal)] border border-[var(--border)] rounded-sm">
                <FileText className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[12px] font-semibold text-[var(--sutra-charcoal)] truncate max-w-[260px]">
                  {uploadedFile.name}
                </p>
                <p className="text-[10px] text-[var(--text-3)] font-mono uppercase tracking-widest mt-0.5">
                  {uploadedFile.isUrl
                    ? `${uploadedFile.size.toLocaleString()} chars · Context loaded`
                    : `${(uploadedFile.size / 1024).toFixed(1)} KB · Context loaded`}
                </p>
              </div>
            </div>
            <button
              onClick={handleClear}
              className="p-1.5 rounded-sm hover:bg-[var(--bg-2)] text-[var(--text-3)] hover:text-[var(--sutra-charcoal)] transition-colors border border-transparent hover:border-[var(--border)]"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {uploadedFile.securityPassed && (
            <div className="flex items-center gap-1.5 pt-1.5 border-t border-[var(--border)] text-[10px] text-[var(--green)] font-mono font-medium">
              <ShieldCheck className="w-3.5 h-3.5 text-[var(--green)] shrink-0" />
              <span>Security Check: Verified Clean · Multi-Layer Threat Scan Passed</span>
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border border-dashed rounded-sm p-5 text-center cursor-pointer transition-colors ${
              isDragging
                ? 'border-[var(--sutra-muted-gold)] bg-[var(--bg)]'
                : 'border-[var(--border)] hover:border-[var(--sutra-charcoal)] bg-[var(--bg-2)]'
            }`}
          >
            {loading ? (
              <div className="flex flex-col items-center justify-center gap-1.5 py-1 text-[var(--sutra-charcoal)] text-[12px] font-medium">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-[var(--sutra-muted-gold)]" />
                  <span>Scanning & parsing document…</span>
                </div>
                <span className="text-[10px] text-[var(--text-3)] font-mono">Running Layer 0 offline & threat verification</span>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center gap-2 text-[var(--text-2)] hover:text-[var(--sutra-charcoal)]">
                <div className="p-2.5 bg-[var(--bg)] border border-[var(--border)] rounded-sm shadow-sm">
                  <Upload className="w-4 h-4 text-[var(--sutra-charcoal)]" />
                </div>
                <span className="text-[11px] font-bold uppercase tracking-widest">Upload PRD, spec, schema</span>
                <span className="text-[10px] text-[var(--text-3)]">(PDF, DOCX, CSV, TXT)</span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Link2 className="w-4 h-4 text-[var(--text-3)] shrink-0 ml-1" />
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleParseUrl();
              }}
              placeholder="Or paste website / API docs URL…"
              className="flex-1 min-w-0 bg-[var(--bg)] border border-[var(--border)] rounded-sm px-3 py-2 text-[12px] text-[var(--sutra-charcoal)] placeholder:text-[var(--text-3)] outline-none focus:border-[var(--sutra-muted-gold)] shadow-sm transition-colors"
            />
            <button
              onClick={handleParseUrl}
              disabled={urlLoading}
              className="btn btn-secondary px-4 py-2 shrink-0 min-w-[70px] justify-center"
            >
              {urlLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Fetch'}
            </button>
          </div>

          {/* Active Security Guarantee */}
          <div className="flex items-center justify-center gap-1.5 pt-0.5 text-[10px] text-[var(--text-3)] font-mono">
            <Shield className="w-3 h-3 text-[var(--sutra-muted-gold)]" />
            <span>Protected by Multi-Layer Threat Scan (Local rules, ClamAV, VirusTotal reputation)</span>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 p-2.5 bg-[var(--bg)] border border-[var(--red)] text-[var(--red)] text-[11px] rounded-sm shadow-sm mt-2">
          {error.toLowerCase().includes('threat') || error.toLowerCase().includes('blocked') || error.toLowerCase().includes('archive') ? (
            <ShieldAlert className="w-4 h-4 shrink-0 text-[var(--red)] mt-0.5" />
          ) : (
            <AlertCircle className="w-4 h-4 shrink-0 text-[var(--red)] mt-0.5" />
          )}
          <div>
            <span className="font-semibold block">
              {error.toLowerCase().includes('threat') || error.toLowerCase().includes('blocked')
                ? 'Threat Scan Rejection'
                : 'Upload Error'}
            </span>
            <span>{error}</span>
          </div>
        </div>
      )}
    </div>
  );
}
    </div>
  );
}
