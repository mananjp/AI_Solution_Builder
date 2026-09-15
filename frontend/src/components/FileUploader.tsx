'use client';

import React, { useState, useRef } from 'react';
import { Upload, FileText, WarningCircle, CircleNotch, X, Link } from '@phosphor-icons/react/dist/ssr';
import { uploadApi } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

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
    <div className="w-full">
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
        <Card className="bg-primary/5 border-primary/30">
          <CardContent className="p-3 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-primary/20 text-primary">
                <FileText className="w-4 h-4" />
              </div>
              <div>
                <p className="text-xs font-medium text-foreground truncate max-w-[260px]">
                  {uploadedFile.name}
                </p>
                <p className="text-[10px] text-muted-foreground">
                  {uploadedFile.isUrl
                    ? `${uploadedFile.size.toLocaleString()} characters • Extracted into AI Context`
                    : `${(uploadedFile.size / 1024).toFixed(1)} KB • Extracted into AI Context`}
                </p>
              </div>
            </div>
            <Button variant="ghost" size="icon-xs" onClick={handleClear} className="text-muted-foreground hover:text-foreground">
              <X className="w-4 h-4" />
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div>
          <Card
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              'border-dashed cursor-pointer transition-all',
              isDragging
                ? 'border-primary bg-primary/10'
                : 'border-border hover:border-primary/50 bg-muted/10'
            )}
          >
            <CardContent className="p-3">
              {loading ? (
                <div className="flex items-center justify-center gap-2 py-1 text-primary text-xs font-medium">
                  <CircleNotch className="w-4 h-4 animate-spin" />
                  <span>Parsing document with PyMuPDF & pandas...</span>
                </div>
              ) : (
                <div className="flex items-center justify-center gap-2 text-muted-foreground text-xs">
                  <Upload className="w-3.5 h-3.5 text-primary" />
                  <span>
                    Upload requirements doc, PRD, or schema (PDF, DOCX, CSV, Excel)
                  </span>
                </div>
              )}
            </CardContent>
          </Card>

          {loading && (
            <Progress value={null} className="mt-2" />
          )}

          <div className="mt-2.5 flex items-center gap-2">
            <Link className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
            <Input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleParseUrl();
              }}
              placeholder="Or paste a website URL (docs, API reference)…"
              className="flex-1 text-xs"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={handleParseUrl}
              disabled={urlLoading}
              className="shrink-0"
            >
              {urlLoading ? (
                <CircleNotch className="w-3.5 h-3.5 animate-spin" />
              ) : (
                'Fetch'
              )}
            </Button>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-2 flex items-center gap-1.5 text-destructive text-xs">
          <WarningCircle className="w-3.5 h-3.5" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
