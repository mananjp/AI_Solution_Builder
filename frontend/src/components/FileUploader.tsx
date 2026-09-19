'use client';

import React, { useState, useRef } from 'react';
import { Upload, FileText, AlertCircle, Loader2, X, Link2 } from 'lucide-react';
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
      setUploadedFile({ name: file.name, size: file.size });
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
      setUploadedFile({ name: res.url, size: res.characterCount, isUrl: true });
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
    <div className="w-full space-y-2">
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
        <div className="flex items-center justify-between p-2.5 rounded-lg bg-[#0a0a0a] border border-[#242424]">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded bg-[#161616] text-[#6366f1]">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-medium text-white truncate max-w-[260px]">
                {uploadedFile.name}
              </p>
              <p className="text-[10px] text-[#555]">
                {uploadedFile.isUrl
                  ? `${uploadedFile.size.toLocaleString()} chars · Context loaded`
                  : `${(uploadedFile.size / 1024).toFixed(1)} KB · Context loaded`}
              </p>
            </div>
          </div>
          <button
            onClick={handleClear}
            className="p-1 rounded hover:bg-[#161616] text-[#555] hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border border-dashed rounded-lg p-3 text-center cursor-pointer transition-colors ${isDragging
                ? 'border-[#6366f1] bg-[#6366f10a]'
                : 'border-[#242424] hover:border-[#3a3a3a] bg-[#0a0a0a]'
              }`}
          >
            {loading ? (
              <div className="flex items-center justify-center gap-2 py-0.5 text-[#6366f1] text-xs font-medium">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Parsing document…</span>
              </div>
            ) : (
              <div className="flex items-center justify-center gap-2 text-[#666] hover:text-[#a1a1a1] text-xs">
                <Upload className="w-3.5 h-3.5 text-[#6366f1]" />
                <span>Upload PRD, spec, schema (PDF, DOCX, CSV, TXT)</span>
              </div>
            )}
          </div>

          <div className="mt-2 flex items-center gap-2">
            <Link2 className="w-3.5 h-3.5 text-[#555] shrink-0" />
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleParseUrl();
              }}
              placeholder="Or paste website / API docs URL…"
              className="flex-1 bg-[#0a0a0a] border border-[#242424] rounded-lg px-2.5 py-1 text-xs text-white placeholder:text-[#444] outline-none focus:border-[#6366f1]"
            />
            <button
              onClick={handleParseUrl}
              disabled={urlLoading}
              className="px-2.5 py-1 rounded-lg bg-[#161616] hover:bg-[#1f1f1f] text-white text-xs font-medium border border-[#2a2a2a] transition-colors disabled:opacity-40 shrink-0"
            >
              {urlLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Fetch'}
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-1.5 text-[#f87171] text-xs">
          <AlertCircle className="w-3.5 h-3.5" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
