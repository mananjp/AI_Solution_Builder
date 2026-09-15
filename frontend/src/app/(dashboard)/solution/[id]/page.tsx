'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Download,
  ArrowClockwise,
  Compass,
  List,
  Layout,
  Database,
  Code,
  CalendarBlank,
  FlowArrow,
  Rocket,
  Copy,
  Check,
  House,
  PencilSimple,
  FloppyDisk,
} from '@phosphor-icons/react/dist/ssr';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import ExportModal from '@/components/ExportModal';
import RegenerateModal from '@/components/RegenerateModal';
import WireframeCanvas from '@/components/WireframeCanvas';
import BpmnViewer from '@/components/BpmnViewer';
import { solutionApi } from '@/lib/api';
import { Solution, Artifact, ArtifactType } from '@/types';

interface ArtifactTab {
  value: ArtifactType;
  label: string;
  icon: React.ComponentType<Record<string, unknown>>;
}

const ARTIFACT_TABS: ArtifactTab[] = [
  { value: 'hld', label: 'HLD', icon: Compass },
  { value: 'lld', label: 'LLD', icon: List },
  { value: 'wireframe', label: 'Wireframes', icon: Layout },
  { value: 'database_schema', label: 'DB Schema', icon: Database },
  { value: 'api_spec', label: 'API Spec', icon: Code },
  { value: 'roadmap', label: 'Roadmap', icon: CalendarBlank },
  { value: 'bpmn', label: 'BPMN', icon: FlowArrow },
];

function getStatusForArtifact(artifacts: Artifact[], type: ArtifactType): 'ready' | 'pending' {
  return artifacts.some((a) => a.artifact_type === type) ? 'ready' : 'pending';
}

function MarkdownRenderer({ content }: { content: string }) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyToClipboard = useCallback(async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // silently fail
    }
  }, []);

  const renderContent = (text: string) => {
    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    let inCodeBlock = false;
    let codeLines: string[] = [];
    let codeKey = 0;
    let inTable = false;
    let tableRows: string[] = [];

    const flushTable = () => {
      if (tableRows.length === 0) return;
      const header = tableRows[0];
      const body = tableRows.slice(2);
      const headers = header
        .split('|')
        .map((h) => h.trim())
        .filter(Boolean);
      const rows = body.map((row) =>
        row
          .split('|')
          .map((c) => c.trim())
          .filter(Boolean)
      );
      const tableId = `table-${elements.length}`;
      elements.push(
        <div key={tableId} className="overflow-x-auto my-4">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr>
                {headers.map((h, i) => (
                  <th
                    key={i}
                    className="text-left px-3 py-2 bg-secondary border border-border font-semibold text-foreground"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri}>
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      className="px-3 py-2 border border-border text-muted-foreground"
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
      inTable = false;
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      if (line.startsWith('```')) {
        if (inCodeBlock) {
          const code = codeLines.join('\n');
          const id = `code-${codeKey++}`;
          elements.push(
            <div key={id} className="relative my-4 group">
              <div className="absolute top-2 right-2 z-10">
                <button
                  onClick={() => copyToClipboard(code, id)}
                  className="flex items-center gap-1 px-2 py-1 rounded bg-secondary hover:bg-secondary/80 text-xs text-muted-foreground hover:text-foreground transition-colors opacity-0 group-hover:opacity-100"
                >
                  {copiedId === id ? (
                    <Check className="w-3 h-3 text-success" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                  <span>{copiedId === id ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
              <pre className="bg-card border border-border rounded-lg p-4 overflow-x-auto text-xs leading-relaxed">
                <code className="text-foreground font-mono">{code}</code>
              </pre>
            </div>
          );
          codeLines = [];
          inCodeBlock = false;
        } else {
          if (inTable) flushTable();
          inCodeBlock = true;
        }
        continue;
      }

      if (inCodeBlock) {
        codeLines.push(line);
        continue;
      }

      if (line.startsWith('|') && line.endsWith('|')) {
        inTable = true;
        tableRows.push(line);
        continue;
      } else if (inTable) {
        flushTable();
      }

      if (line.trim() === '') {
        elements.push(<div key={`space-${i}`} className="h-2" />);
        continue;
      }

      if (line.match(/^={3,}/)) {
        elements.push(<Separator key={`sep-${i}`} className="my-3" />);
        continue;
      }

      const headingMatch = line.match(/^(#{1,6})\s+(.+)/);
      if (headingMatch) {
        const level = headingMatch[1].length;
        const text = headingMatch[2];
        const id = text
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/(^-|-$)/g, '');
        const sizes: Record<number, string> = {
          1: 'text-xl font-extrabold',
          2: 'text-lg font-bold',
          3: 'text-base font-bold',
          4: 'text-sm font-semibold',
          5: 'text-xs font-semibold',
          6: 'text-xs font-medium',
        };
        elements.push(
          <h2
            key={`h-${i}`}
            id={id}
            className={cn(
              'text-foreground mt-6 mb-2 scroll-mt-20',
              sizes[level] || 'text-sm font-semibold'
            )}
          >
            {text}
          </h2>
        );
        continue;
      }

      if (line.match(/^\d+\.\s+/)) {
        const text = line.replace(/^\d+\.\s+/, '');
        elements.push(
          <div key={`ol-${i}`} className="flex gap-2 text-xs text-foreground leading-relaxed pl-2">
            <span className="text-primary font-semibold shrink-0 mt-0.5">
              {line.match(/^(\d+)\./)?.[1]}.
            </span>
            <span>{renderInline(text)}</span>
          </div>
        );
        continue;
      }

      if (line.match(/^[-*]\s+/)) {
        const text = line.replace(/^[-*]\s+/, '');
        elements.push(
          <div key={`ul-${i}`} className="flex gap-2 text-xs text-foreground leading-relaxed pl-2">
            <span className="text-primary font-bold shrink-0 mt-0.5">-</span>
            <span>{renderInline(text)}</span>
          </div>
        );
        continue;
      }

      if (line.match(/^[A-Z][A-Z\s]+:$/)) {
        elements.push(
          <h3 key={`sh-${i}`} className="text-sm font-bold text-foreground mt-4 mb-1 uppercase tracking-wide">
            {line}
          </h3>
        );
        continue;
      }

      if (line.match(/^-{3,}/)) {
        elements.push(<Separator key={`s-${i}`} className="my-2" />);
        continue;
      }

      elements.push(
        <p key={`p-${i}`} className="text-xs text-muted-foreground leading-relaxed">
          {renderInline(line)}
        </p>
      );
    }

    if (inTable) flushTable();

    return elements;
  };

  const renderInline = (text: string): React.ReactNode => {
    const parts: React.ReactNode[] = [];
    let remaining = text;
    let key = 0;

    while (remaining.length > 0) {
      const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
      const codeMatch = remaining.match(/`(.+?)`/);

      let nextMatch: RegExpMatchArray | null = null;
      let matchType = '';

      if (boldMatch && codeMatch) {
        if (remaining.indexOf(boldMatch[0]) < remaining.indexOf(codeMatch[0])) {
          nextMatch = boldMatch;
          matchType = 'bold';
        } else {
          nextMatch = codeMatch;
          matchType = 'code';
        }
      } else if (boldMatch) {
        nextMatch = boldMatch;
        matchType = 'bold';
      } else if (codeMatch) {
        nextMatch = codeMatch;
        matchType = 'code';
      }

      if (!nextMatch) {
        parts.push(remaining);
        break;
      }

      const idx = remaining.indexOf(nextMatch[0]);
      if (idx > 0) {
        parts.push(remaining.slice(0, idx));
      }

      if (matchType === 'bold') {
        parts.push(
          <strong key={key++} className="font-bold text-foreground">
            {nextMatch[1]}
          </strong>
        );
      } else {
        parts.push(
          <code
            key={key++}
            className="px-1 py-0.5 rounded bg-secondary text-foreground font-mono text-[10px]"
          >
            {nextMatch[1]}
          </code>
        );
      }

      remaining = remaining.slice(idx + nextMatch[0].length);
    }

    return parts.length === 1 ? parts[0] : <>{parts}</>;
  };

  return <div className="flex flex-col gap-1">{renderContent(content)}</div>;
}

function DdlRenderer({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // silently fail
    }
  };

  return (
    <div className="relative group">
      <div className="absolute top-2 right-2 z-10">
        <button
          onClick={copyToClipboard}
          className="flex items-center gap-1 px-2 py-1 rounded bg-secondary hover:bg-secondary/80 text-xs text-muted-foreground hover:text-foreground transition-colors opacity-0 group-hover:opacity-100"
        >
          {copied ? (
            <Check className="w-3 h-3 text-success" />
          ) : (
            <Copy className="w-3 h-3" />
          )}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className="bg-card border border-border rounded-lg p-4 overflow-x-auto text-xs leading-relaxed">
        <code className="text-foreground font-mono whitespace-pre">{content}</code>
      </pre>
    </div>
  );
}

function JsonRenderer({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);

  const formatted = (() => {
    try {
      return JSON.stringify(JSON.parse(content), null, 2);
    } catch {
      return content;
    }
  })();

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(formatted);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // silently fail
    }
  };

  return (
    <div className="relative group">
      <div className="absolute top-2 right-2 z-10">
        <button
          onClick={copyToClipboard}
          className="flex items-center gap-1 px-2 py-1 rounded bg-secondary hover:bg-secondary/80 text-xs text-muted-foreground hover:text-foreground transition-colors opacity-0 group-hover:opacity-100"
        >
          {copied ? (
            <Check className="w-3 h-3 text-success" />
          ) : (
            <Copy className="w-3 h-3" />
          )}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className="bg-card border border-border rounded-lg p-4 overflow-x-auto text-xs leading-relaxed">
        <code className="text-foreground font-mono whitespace-pre">{formatted}</code>
      </pre>
    </div>
  );
}

function WireframeFallback({ artifact }: { artifact: Artifact }) {
  const contentText = artifact.content_text || '';
  const description =
    typeof artifact.content?.description === 'string'
      ? artifact.content.description
      : '';
  const components = Array.isArray(artifact.content?.components)
    ? (artifact.content.components as string[])
    : [];

  return (
    <div className="flex flex-col gap-4">
      {description && (
        <div className="p-4 rounded-lg bg-card border border-border">
          <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>
        </div>
      )}
      {components.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {components.map((c, i) => (
            <Badge key={i} variant="secondary" className="text-xs">
              {c}
            </Badge>
          ))}
        </div>
      )}
      {contentText && (
        <pre className="bg-card border border-border rounded-lg p-4 overflow-x-auto text-xs leading-relaxed font-mono text-foreground whitespace-pre">
          {contentText}
        </pre>
      )}
    </div>
  );
}

export default function SolutionViewerPage() {
  const params = useParams();
  const solutionId = params?.id as string;

  const [solution, setSolution] = useState<Solution | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [activeArtifact, setActiveArtifact] = useState<ArtifactType>('hld');
  const [showExportModal, setShowExportModal] = useState(false);
  const [showRegenerateModal, setShowRegenerateModal] = useState(false);
  const [showEditTitle, setShowEditTitle] = useState(false);
  const [solutionTitle, setSolutionTitle] = useState('');
  const [loadingSolution, setLoadingSolution] = useState(true);
  const [solutionError, setSolutionError] = useState<string | null>(null);

  useEffect(() => {
    async function loadSolution() {
      setLoadingSolution(true);
      setSolutionError(null);
      try {
        const sol = await solutionApi.get(solutionId);
        setSolution(sol);
        setSolutionTitle(sol.title || 'Solution Design Session');
        if (sol.artifacts && sol.artifacts.length > 0) {
          setArtifacts(sol.artifacts);
          const firstAvailable = ARTIFACT_TABS.find((tab) =>
            sol.artifacts!.some((a) => a.artifact_type === tab.value)
          );
          if (firstAvailable) setActiveArtifact(firstAvailable.value);
        } else {
          setArtifacts([]);
        }
      } catch (err) {
        setSolutionError(err instanceof Error ? err.message : 'Could not load this solution.');
        setArtifacts([]);
      } finally {
        setLoadingSolution(false);
      }
    }

    loadSolution();
  }, [solutionId]);

  const currentArtifact = artifacts.find((a) => a.artifact_type === activeArtifact);

  const handleArtifactUpdated = (newArt: Artifact) => {
    setArtifacts([
      newArt,
      ...artifacts.filter(
        (a) => a.id !== newArt.id && a.artifact_type !== newArt.artifact_type
      ),
    ]);
  };

  const handleSaveTitle = async () => {
    const nextTitle = solutionTitle.trim() || 'Solution Design Session';
    try {
      const updated = await solutionApi.update(solutionId, { title: nextTitle });
      setSolution((current) => (current ? { ...current, title: updated.title } : current));
      setSolutionTitle(updated.title || nextTitle);
      setShowEditTitle(false);
    } catch (err) {
      setSolutionError(err instanceof Error ? err.message : 'Could not update the solution title.');
    }
  };

  const renderArtifactContent = () => {
    if (loadingSolution) {
      return (
        <div className="flex-1 p-6">
          <div className="flex flex-col gap-3">
            <div className="h-5 w-48 animate-pulse rounded bg-secondary" />
            <div className="h-24 animate-pulse rounded-lg bg-secondary" />
            <div className="h-24 animate-pulse rounded-lg bg-secondary" />
            <div className="h-24 animate-pulse rounded-lg bg-secondary" />
          </div>
        </div>
      );
    }

    if (solutionError) {
      return (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center flex flex-col items-center gap-3">
            <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20">
              <Database className="w-8 h-8 text-destructive" />
            </div>
            <p className="text-sm text-destructive">{solutionError}</p>
          </div>
        </div>
      );
    }

    if (!currentArtifact) {
      const artifactLabel = ARTIFACT_TABS.find((t) => t.value === activeArtifact)?.label ?? 'Artifact';
      const isComplete = solution?.status === 'complete';
      const isGenerating = solution?.status === 'generating';

      return (
        <div className="flex-1 flex items-center justify-center">
          <div className="max-w-md text-center flex flex-col items-center gap-4">
            <div className="p-4 rounded-lg bg-secondary border border-border">
              <Database className="w-8 h-8 text-muted-foreground" />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-semibold text-foreground">
                {isComplete
                  ? 'Design is complete — ready for the MVP build.'
                  : isGenerating
                    ? 'This generation is still in progress.'
                    : 'No data available for this section yet.'}
              </p>
              <p className="text-sm text-muted-foreground">
                {isComplete
                  ? 'The solution has been generated and is ready to move into build mode.'
                  : isGenerating
                    ? 'Please wait for the architecture artifacts to finish generating.'
                    : `No ${artifactLabel.toLowerCase()} artifact has been generated for this solution yet.`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {isComplete ? (
                <Button
                  size="sm"
                  className="gap-1.5"
                  render={<Link href={`/solution/${solutionId}/mvp`} />}
                  nativeButton={false}
                >
                  <Rocket className="w-3.5 h-3.5" />
                  <span>Build MVP</span>
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowRegenerateModal(true)}
                >
                  <ArrowClockwise className="w-3.5 h-3.5" />
                  <span>Generate</span>
                </Button>
              )}
            </div>
          </div>
        </div>
      );
    }

    switch (activeArtifact) {
      case 'wireframe': {
        const hasScreens =
          currentArtifact.content &&
          typeof currentArtifact.content === 'object' &&
          Array.isArray(currentArtifact.content.screens);
        if (hasScreens) {
          return (
            <WireframeCanvas
              wireframes={[currentArtifact]}
              onUpdate={handleArtifactUpdated}
            />
          );
        }
        return <WireframeFallback artifact={currentArtifact} />;
      }
      case 'database_schema':
        return <DdlRenderer content={currentArtifact.content_text || ''} />;
      case 'api_spec':
        return <JsonRenderer content={currentArtifact.content_text || ''} />;
      case 'bpmn': {
        const processData =
          currentArtifact.content &&
          typeof currentArtifact.content === 'object' &&
          'processName' in currentArtifact.content
            ? (currentArtifact.content as unknown as import('@/types').BpmnProcess)
            : undefined;
        return <BpmnViewer processData={processData} />;
      }
      case 'hld':
      case 'lld':
      case 'roadmap':
      default:
        return <MarkdownRenderer content={currentArtifact.content_text || ''} />;
    }
  };

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header Bar */}
      <header className="flex items-center justify-between px-4 h-14 border-b border-border bg-card shrink-0">
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
          >
            <House className="w-4 h-4" />
          </Link>
          <Separator orientation="vertical" className="h-4" />
            <h1 className="flex items-center gap-2 text-sm font-bold text-foreground truncate max-w-md">
              {showEditTitle ? (
                <>
                  <Input
                    value={solutionTitle}
                    onChange={(e) => setSolutionTitle(e.target.value)}
                    className="w-56 rounded-lg border border-border bg-background px-2 py-1 text-sm text-foreground outline-none transition-colors focus:border-primary"
                    placeholder="Solution title"
                  />
                  <Button
                    size="sm"
                    variant="secondary"
                    className="gap-1.5 text-xs"
                    onClick={handleSaveTitle}
                  >
                    <FloppyDisk className="w-3 h-3 align-middle" />
                    <span className="hidden sm:inline">Save</span>
                  </Button>
                </>
              ) : (
                <>
                  <span className="truncate max-w-[17rem]">{solution?.title || 'Solution Design Session'}</span>
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1.5 text-xs"
                    onClick={() => setShowEditTitle(true)}
                  >
                    <PencilSimple className="w-3 h-3 align-middle" />
                    <span className="hidden sm:inline">Edit</span>
                  </Button>
                </>
              )}
            </h1>
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 gap-1">
            <Check className="w-3 h-3 text-success" />
            Complete
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowRegenerateModal(true)}
            className="gap-1.5 text-xs"
          >
            <ArrowClockwise className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Regenerate</span>
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowExportModal(true)}
            className="gap-1.5 text-xs"
          >
            <Download className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Export</span>
          </Button>
          <Separator orientation="vertical" className="h-4" />
          <Button
            size="sm"
            className="gap-1.5 text-xs"
            render={<Link href={`/solution/${solutionId}/mvp`} />}
            nativeButton={false}
          >
            <Rocket className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Build MVP</span>
          </Button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        {/* Left Sidebar */}
        <aside className="w-60 border-r border-border bg-card flex flex-col shrink-0">
          <ScrollArea className="flex-1">
            <div className="flex flex-col gap-0.5 p-3">
              {ARTIFACT_TABS.map((tab) => {
                const Icon = tab.icon;
                const status = getStatusForArtifact(artifacts, tab.value);
                const isActive = activeArtifact === tab.value;

                return (
                  <button
                    key={tab.value}
                    onClick={() => setActiveArtifact(tab.value)}
                    className={cn(
                      'flex items-center gap-2.5 px-3 py-2 rounded-md text-left text-xs font-medium transition-colors w-full',
                      isActive
                        ? 'bg-primary/10 text-primary border border-primary/20'
                        : 'text-muted-foreground hover:text-foreground hover:bg-secondary border border-transparent'
                    )}
                  >
                    <Icon
                      className={cn(
                        'w-4 h-4 shrink-0',
                        isActive ? 'text-primary' : 'text-muted-foreground'
                      )}
                      weight={isActive ? 'fill' : 'regular'}
                    />
                    <span className="flex-1 truncate">{tab.label}</span>
                    <span
                      className={cn(
                        'w-1.5 h-1.5 rounded-full shrink-0',
                        status === 'ready' ? 'bg-success' : 'bg-muted-foreground/40'
                      )}
                    />
                  </button>
                );
              })}
            </div>
          </ScrollArea>

          <div className="p-3 border-t border-border flex flex-col gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="justify-start gap-2 text-xs text-muted-foreground"
              render={<Link href="/dashboard" />}
              nativeButton={false}
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Dashboard</span>
            </Button>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 min-w-0 overflow-hidden flex flex-col">
          {currentArtifact && (
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-card/50 shrink-0">
              <div className="flex items-center gap-2">
                <h2 className="text-xs font-bold text-foreground truncate max-w-lg">
                  {currentArtifact.title}
                </h2>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-[10px] font-mono px-1.5 py-0">
                  v{currentArtifact.version}
                </Badge>
                <Badge variant="outline" className="text-[10px] px-1.5 py-0 capitalize">
                  {activeArtifact.replace('_', ' ')}
                </Badge>
              </div>
            </div>
          )}
          <div className="flex-1 overflow-y-auto p-6">
            {renderArtifactContent()}
          </div>
        </main>
      </div>

      {/* Modals */}
      <ExportModal
        open={showExportModal}
        onOpenChange={setShowExportModal}
        solutionId={solutionId}
      />

      {currentArtifact && (
        <RegenerateModal
          solutionId={solutionId}
          artifactType={activeArtifact}
          currentTitle={currentArtifact.title}
          isOpen={showRegenerateModal}
          onClose={() => setShowRegenerateModal(false)}
          onRegenerated={handleArtifactUpdated}
        />
      )}
    </div>
  );
}


