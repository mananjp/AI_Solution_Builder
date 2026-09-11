'use client';

import React, { useState, useRef } from 'react';
import { Upload, FileText, AlertCircle, Loader2, X } from 'lucide-react';
import { uploadApi } from '@/lib/api';

interface FileUploaderProps {
  onParsedContext: (text: string, filename: string) => void;
  onClear?: () => void;
}

export default function FileUploader({ onParsedContext, onClear }: FileUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<{ name: string; size: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    <div className="w-full">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.doc,.csv,.xlsx,.xls,.txt"
        className="hidden"
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            handleUpload(e.target.files[0]);
          }
        }}
      />

      {uploadedFile ? (
        <div className="flex items-center justify-between p-3 rounded-xl bg-indigo-950/40 border border-indigo-500/30">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-500/20 text-indigo-400">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <p className="text-xs font-medium text-slate-200">{uploadedFile.name}</p>
              <p className="text-[10px] text-slate-400">
                {(uploadedFile.size / 1024).toFixed(1)} KB • Extracted into AI Context
              </p>
            </div>
          </div>
          <button
            onClick={handleClear}
            className="p-1 rounded-lg hover:bg-white/10 text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`border border-dashed rounded-xl p-3 text-center cursor-pointer transition-all ${
            isDragging
              ? 'border-indigo-500 bg-indigo-950/30'
              : 'border-white/10 hover:border-indigo-500/50 bg-white/[0.01]'
          }`}
        >
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-1 text-indigo-400 text-xs font-medium">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Parsing document with PyMuPDF & pandas...</span>
            </div>
          ) : (
            <div className="flex items-center justify-center gap-2 text-slate-400 hover:text-slate-300 text-xs">
              <Upload className="w-3.5 h-3.5 text-indigo-400" />
              <span>
                Upload requirements doc, PRD, or schema (PDF, DOCX, CSV, Excel)
              </span>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="mt-2 flex items-center gap-1.5 text-rose-400 text-xs">
          <AlertCircle className="w-3.5 h-3.5" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
