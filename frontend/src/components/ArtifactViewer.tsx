'use client';

import React, { useState } from 'react';
import { 
  FileCode, 
  Stack, 
  Database, 
  Layout, 
  Calendar, 
  GitBranch, 
  Copy, 
  Check, 
  Download,
  ArrowClockwise,
  GitFork,
  Play,
  PencilSimple
} from '@phosphor-icons/react/dist/ssr';
import { Artifact, ArtifactType } from '@/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import BpmnViewer from './BpmnViewer';
import WorkablePreview from './WorkablePreview';
import RegenerateModal from './RegenerateModal';
import WireframeCanvas from './WireframeCanvas';

interface ArtifactViewerProps {
  artifacts: Artifact[];
  solutionId: string;
  onArtifactUpdated?: (updated: Artifact) => void;
}

export default function ArtifactViewer({ artifacts, solutionId, onArtifactUpdated }: ArtifactViewerProps) {
  const [activeType, setActiveType] = useState<ArtifactType>('hld');
  const [copied, setCopied] = useState(false);
  const [showRegenModal, setShowRegenModal] = useState(false);
  const [wireframeView, setWireframeView] = useState<'canvas' | 'details'>('canvas');

  const tabs: { type: ArtifactType; label: string; icon: React.ComponentType<{className?: string}>; badge?: string }[] = [
    { type: 'hld', label: 'High-Level Design', icon: Stack },
    { type: 'lld', label: 'Low-Level Design', icon: GitBranch },
    { type: 'workable', label: 'Mounted Live App', icon: Play, badge: 'Operational' },
    { type: 'bpmn', label: 'BPMN 2.0 Process', icon: GitFork },
    { type: 'wireframe', label: 'UI Wireframes', icon: Layout },
    { type: 'database_schema', label: 'DB Schema & ERD', icon: Database },
    { type: 'api_spec', label: 'OpenAPI Spec', icon: FileCode },
    { type: 'roadmap', label: 'Roadmap & Sprints', icon: Calendar },
  ];

  const currentArtifacts = artifacts.filter(a => a.artifact_type === activeType);
  const activeArtifact = currentArtifacts[0];

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = (filename: string, content: string) => {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getRawContentString = (artifact?: Artifact) => {
    if (!artifact) return '';
    if (artifact.content_text) return artifact.content_text;
    return JSON.stringify(artifact.content, null, 2);
  };

  return (
    <div className="flex flex-col h-full bg-background border border-border rounded-lg overflow-hidden">
      <div className="flex items-center justify-between border-b border-border bg-card/60 px-4 pt-2 overflow-x-auto gap-2">
        <div className="flex gap-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const hasData = artifacts.some(a => a.artifact_type === tab.type) || tab.type === 'workable' || tab.type === 'bpmn';
            const isActive = activeType === tab.type;

            return (
              <Button
                key={tab.type}
                variant="ghost"
                size="sm"
                onClick={() => setActiveType(tab.type)}
                className={`flex items-center gap-2 px-3 py-2.5 text-xs font-medium rounded-t transition-all border-t-2 whitespace-nowrap ${
                  isActive
                    ? 'border-primary bg-background text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-accent'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-primary' : 'text-muted-foreground/70'}`} />
                <span>{tab.label}</span>
                {tab.badge && (
                  <Badge variant="secondary" className="px-1.5 py-0.2 text-[9px] font-bold rounded bg-success/20 text-success border border-success/30">
                    {tab.badge}
                  </Badge>
                )}
                {hasData && !tab.badge && (
                  <span className="w-1.5 h-1.5 rounded-full bg-success ml-0.5" />
                )}
              </Button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 pb-2">
          {activeType !== 'workable' && activeType !== 'bpmn' && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowRegenModal(true)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary text-xs font-semibold border border-primary/20 transition-colors whitespace-nowrap"
            >
              <ArrowClockwise className="w-3.5 h-3.5" />
              <span>Regenerate</span>
            </Button>
          )}

          {activeArtifact && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleCopy(getRawContentString(activeArtifact))}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-accent bg-accent text-muted-foreground text-xs transition-colors whitespace-nowrap"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleDownload(`${activeType}-spec.txt`, getRawContentString(activeArtifact))}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-accent bg-accent text-muted-foreground text-xs transition-colors whitespace-nowrap"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Export</span>
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto font-sans">
        {activeType === 'workable' ? (
          <div className="h-full">
            <WorkablePreview solutionId={solutionId} />
          </div>
        ) : activeType === 'bpmn' ? (
          <div className="h-full p-4">
            <BpmnViewer />
          </div>
        ) : activeArtifact ? (
          <div className="max-w-4xl mx-auto p-6 flex flex-col gap-6">
            <div className="flex items-center justify-between pb-4 border-b border-border">
              <div>
                <h3 className="text-xl font-bold text-foreground">{activeArtifact.title}</h3>
                <p className="text-xs text-muted-foreground mt-1">
                  Version {activeArtifact.version} • Synthesized by Autonomous Agent
                </p>
              </div>
              <Badge variant="secondary" className="px-3 py-1 rounded-full text-xs font-semibold bg-primary/10 text-primary border border-primary/20">
                Production Spec
              </Badge>
            </div>

            {activeType === 'wireframe' ? (
              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1 p-1 rounded bg-card/80 border border-border">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setWireframeView('canvas')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                        wireframeView === 'canvas'
                          ? 'bg-primary/20 text-primary border border-primary/20'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      Canvas Editor
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setWireframeView('details')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                        wireframeView === 'details'
                          ? 'bg-primary/20 text-primary border border-primary/20'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      Details
                    </Button>
                  </div>
                  <span className="flex items-center gap-1.5 text-[10px] text-muted-foreground/70">
                    <PencilSimple className="w-3 h-3" />
                    Drag, add, and connect components — then Save Layout
                  </span>
                </div>

                {wireframeView === 'canvas' && currentArtifacts.length > 0 ? (
                  <WireframeCanvas wireframes={currentArtifacts} onUpdate={onArtifactUpdated} />
                ) : (
                  currentArtifacts.map((wf, idx) => {
                    const wfContent = wf.content as
                      | { description?: string; components?: Array<{ name?: string; title?: string }> }
                      | undefined;
                    return (
                  <div key={idx} className="p-5 rounded bg-card/60 border border-border flex flex-col gap-3">
                    <h4 className="font-semibold text-base text-foreground">{wf.title}</h4>
                    {wf.content_text ? (
                      <pre className="text-xs text-muted-foreground font-mono bg-background p-4 rounded-lg overflow-x-auto whitespace-pre-wrap leading-relaxed">
                        {wf.content_text}
                      </pre>
                    ) : (
                      <div className="text-xs text-muted-foreground flex flex-col gap-2">
                        <p>{wfContent?.description || 'UI Wireframe Blueprint'}</p>
                        {wfContent?.components && (
                          <div className="grid grid-cols-2 gap-2 mt-2">
                            {wfContent.components.map((comp, cidx) => (
                              <div key={cidx} className="p-2 rounded bg-accent border border-border">
                                <span className="font-semibold text-foreground">{comp.name || comp.title}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                    );
                  })
                )}
              </div>
            ) : (
              <div className="rounded bg-card/50 border border-border p-5">
                <pre className="text-xs text-muted-foreground font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">
                  {getRawContentString(activeArtifact)}
                </pre>
              </div>
            )}
          </div>
        ) : (
          <div className="h-64 flex flex-col items-center justify-center text-center flex flex-col gap-3 text-muted-foreground/70 p-8">
            <div className="p-3 rounded-lg bg-white/[0.02] border border-border">
              <Stack className="w-8 h-8 text-muted-foreground/70" />
            </div>
            <p className="text-sm font-medium text-muted-foreground">
              No artifact generated yet for this category.
            </p>
            <p className="text-xs text-muted-foreground/70 max-w-sm">
              Use the AI Architect Chat to describe your business problem or confirm recommended modules to trigger synthesis.
            </p>
          </div>
        )}
      </div>

      <RegenerateModal
        solutionId={solutionId}
        artifactType={activeType}
        currentTitle={activeArtifact?.title || activeType.toUpperCase()}
        isOpen={showRegenModal}
        onClose={() => setShowRegenModal(false)}
        onRegenerated={(newArt) => {
          onArtifactUpdated?.(newArt);
        }}
      />
    </div>
  );
}
