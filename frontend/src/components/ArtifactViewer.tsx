'use client';

import React, { useState } from 'react';
import {
  FileCode2,
  Layers,
  Database,
  Layout,
  Calendar,
  Network,
  RotateCw,
  GitFork,
  Play,
  PenLine
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Artifact, ArtifactType, BpmnProcess } from '@/types';
import BpmnViewer from './BpmnViewer';
import WorkablePreview from './WorkablePreview';
import RegenerateModal from './RegenerateModal';
import WireframeCanvas from './WireframeCanvas';
import MarkdownRenderer from './MarkdownRenderer';
import ProductVisuals from './ProductVisuals';
import { TabBar } from '@/components/lab/tab-bar';
import { CopyButton } from '@/components/lab/copy-button';
import { DownloadButton, type DownloadStatus } from '@/components/lab/download-button';
import { SegmentedControl } from '@/components/lab/segmented-control';

import { Badge } from '@/components/ui/badge';
import { Button } from "@/components/ui/button";

interface ArtifactViewerProps {
  artifacts: Artifact[];
  solutionId: string;
  onArtifactUpdated?: (updated: Artifact) => void;
}

const BPMN_ALIAS: Record<string, ArtifactType> = { bpmn: 'bpmn_flows' };

// Product visuals are three distinct artifact types shown under one tab.
const VISUAL_TYPES: ArtifactType[] = ['hero_image', 'ui_mockup', 'app_icon'];
const VISUAL_TAB: ArtifactType = 'ui_mockup';

/** Does *artifactType* belong to the tab keyed by *tabType*? */
function matchesTab(artifactType: ArtifactType, tabType: ArtifactType): boolean {
  if (artifactType === tabType) return true;
  if (BPMN_ALIAS[artifactType] === tabType) return true;
  if (tabType === VISUAL_TAB && VISUAL_TYPES.includes(artifactType)) return true;
  return false;
}

function toBpmnProcess(artifact?: Artifact): BpmnProcess | undefined {
  if (!artifact) return undefined;
  const content = (artifact.content || {}) as {
    bpmn?: { name?: string };
    react_flow?: {
      nodes?: Array<{
        id?: string;
        type?: string;
        data?: { label?: string };
        position?: { x?: number; y?: number };
      }>;
      edges?: Array<{ id?: string; source?: string; target?: string }>;
    };
    swimlanes?: Array<{ id?: string; label?: string }>;
    bottlenecks?: Array<{ module?: string; severity?: string; reason?: string }>;
  };
  const nodes = (content.react_flow?.nodes || []).map((n) => ({
    id: n.id || 'node',
    type: (['start', 'task', 'gateway', 'end', 'service'].includes(n.type || '')
      ? n.type
      : 'task') as BpmnProcess['nodes'][number]['type'],
    label: n.data?.label || 'Step',
    actor: 'Flow Participant',
    description: `Step in the generated process at (${n.position?.x ?? 0}, ${n.position?.y ?? 0})`,
  }));
  return {
    processName: content.bpmn?.name || 'Process Workflow',
    swimlanes: (content.swimlanes || []).map((l) => l.label || l.id || 'Swimlane'),
    nodes: nodes.length ? nodes : [{ id: 'start', type: 'start', label: 'Start', actor: 'Participant' }],
    connections: (content.react_flow?.edges || []).map((e) => ({ from: e.source || '', to: e.target || '' })) as BpmnProcess['connections'],
    bottlenecks: (content.bottlenecks || [])
      .map((b) => b.reason || `Bottleneck in ${b.module || 'workflow'}`)
      .filter(Boolean),
  };
}

export default function ArtifactViewer({ artifacts, solutionId, onArtifactUpdated }: ArtifactViewerProps) {
  const [activeType, setActiveType] = useState<ArtifactType>('hld');
  const [showRegenModal, setShowRegenModal] = useState(false);
  const [wireframeView, setWireframeView] = useState<'canvas' | 'details'>('canvas');
  const [downloadStatus, setDownloadStatus] = useState<DownloadStatus>('idle');

  const tabs: { type: ArtifactType; label: string; icon: LucideIcon; badge?: string }[] = [
    { type: 'hld', label: 'High-Level Design', icon: Layers },
    { type: 'lld', label: 'Low-Level Design', icon: Network },
    { type: 'workable', label: 'Mounted Live App', icon: Play, badge: 'Operational' },
    { type: 'bpmn_flows', label: 'BPMN 2.0 Process', icon: GitFork },
    { type: 'wireframe', label: 'UI Wireframes', icon: Layout },
    { type: 'database_schema', label: 'DB Schema & ERD', icon: Database },
    { type: 'api_spec', label: 'OpenAPI Spec', icon: FileCode2 },
    { type: 'roadmap', label: 'Roadmap & Sprints', icon: Calendar },
    { type: VISUAL_TAB, label: 'Product Visuals', icon: PenLine },
  ];

  const currentArtifacts = artifacts.filter(a => matchesTab(a.artifact_type, activeType));
  const activeArtifact = currentArtifacts[0];

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
    <div className="flex flex-col h-full bg-[var(--bg-2)] border border-[var(--border)] shadow-sm">
      {/* Top Tab Bar (IDE style) */}
      <div className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-3)] px-2 pt-2 overflow-x-auto gap-2">
        {/* The lab tab bar slides one pill between tabs, so the active tab is
            marked by a moving element rather than a second border that can
            drift out of step with the label it is supposed to be underlining. */}
        <TabBar
          items={tabs.map((tab) => ({
            id: tab.type,
            label: tab.label,
            icon: (
              <tab.icon
                className={`w-3.5 h-3.5 ${
                  activeType === tab.type
                    ? 'text-[var(--sutra-strong)]'
                    : 'text-[var(--text-3)]'
                }`}
              />
            ),
          }))}
          value={activeType}
          onChange={(value) => setActiveType(value as ArtifactType)}
          label="Artifacts"
          idBase="artifact-viewer"
          className="min-w-0"
        />

        {/* Action buttons */}
        <div className="flex items-center gap-3 pb-2 pr-2">
          {activeType !== 'workable' && activeType !== VISUAL_TAB && (
            <Button variant="secondary" size="default"
              onClick={() => setShowRegenModal(true)}
              className="flex items-center gap-1.5 bg-[var(--bg)] hover:bg-[var(--bg-3)] text-[var(--sutra-ink)] text-[10px] uppercase tracking-widest font-semibold border border-[var(--border)] transition-colors whitespace-nowrap"
            >
              <RotateCw className="w-3 h-3" />
              <span>Regenerate</span>
            </Button>
          )}

          {activeArtifact && activeType !== VISUAL_TAB && (
            <>
              {/* The lab buttons own their own confirming state, so the label
                  cannot drift from the icon and the timer resets on remount. */}
              <CopyButton
                value={getRawContentString(activeArtifact)}
                label="Copy artifact"
                className="shrink-0"
              />
              <DownloadButton
                status={downloadStatus}
                progress={0}
                onStart={() => {
                  handleDownload(`${activeType}-spec.txt`, getRawContentString(activeArtifact));
                  setDownloadStatus('done');
                }}
                onCancel={() => undefined}
                onReset={() => setDownloadStatus('idle')}
                label="Export"
                doneLabel="Saved"
                className="shrink-0"
              />
            </>
          )}
        </div>
      </div>

      {/* Artifact View Body */}
      <div className="flex-1 overflow-y-auto font-sans p-6 bg-[var(--bg)]">
        {activeType === 'workable' ? (
          <div className="h-full">
            <WorkablePreview solutionId={solutionId} />
          </div>
        ) : activeType === 'bpmn_flows' ? (
          <div className="h-full border border-[var(--border)] bg-[var(--bg-2)] p-2 shadow-sm">
            <BpmnViewer processData={toBpmnProcess(activeArtifact)} />
          </div>
        ) : activeType === VISUAL_TAB ? (
          <ProductVisuals artifacts={artifacts.filter((a) => VISUAL_TYPES.includes(a.artifact_type))} />
        ) : activeArtifact ? (
          <div className="max-w-5xl mx-auto space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-[var(--border)]">
              <div>
                <h3 className="text-xl font-serif text-[var(--sutra-ink)]">{activeArtifact.title}</h3>
                <div className="flex items-center gap-3 mt-2 text-[10px] uppercase tracking-widest text-[var(--text-2)] font-semibold">
                  <span>v{activeArtifact.version}</span>
                  <span className="w-1 h-1 rounded-full bg-[var(--border-2)]"></span>
                  <span>Synthesized by Swarm Agent</span>
                </div>
              </div>
              <Badge variant="neutral" className="text-[10px] uppercase tracking-widest">
                Production Spec
              </Badge>
            </div>

            {/* Wireframe vs Markdown Spec */}
            {activeType === 'wireframe' ? (
              <div className="space-y-6">
                <div className="flex items-center justify-between bg-[var(--bg-2)] p-2 border border-[var(--border)] shadow-sm">
                  {/* Two mutually exclusive views of the same wireframes. The lab
                      control slides its pill with a clip-path, so the selection
                      cannot jump or leave a gap between the two labels. */}
                  <SegmentedControl
                    options={['Canvas Editor', 'Details']}
                    value={wireframeView === 'details' ? 'Details' : 'Canvas Editor'}
                    onChange={(value) => setWireframeView(value === 'Details' ? 'details' : 'canvas')}
                    label="Wireframe view"
                  />
                  <span className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-[var(--text-2)] pr-4">
                    <PenLine className="w-3.5 h-3.5" />
                    Drag &amp; connect components
                  </span>
                </div>

                {wireframeView === 'canvas' && currentArtifacts.length > 0 ? (
                  <div className="border border-[var(--border)] shadow-sm bg-[var(--bg-2)] p-1">
                    <WireframeCanvas wireframes={currentArtifacts} onUpdate={onArtifactUpdated} />
                  </div>
                ) : (
                  currentArtifacts.map((wf, idx) => (
                    <div key={idx} className="sutra-card p-8">
                      <h4 className="font-serif text-lg text-[var(--sutra-ink)] mb-6 border-b border-[var(--border)] pb-3">{wf.title}</h4>
                      <MarkdownRenderer content={getRawContentString(wf)} />
                    </div>
                  ))
                )}
              </div>
            ) : (
              <div className="sutra-card p-10 bg-[var(--bg-2)]">
                <MarkdownRenderer content={getRawContentString(activeArtifact)} />
              </div>
            )}
          </div>
        ) : (
          <div className="h-[60vh] flex flex-col items-center justify-center text-center space-y-4 text-[var(--text-2)] p-8">
            <div className="p-4 border border-[var(--border)] bg-[var(--bg-2)] shadow-sm">
              <Layers className="w-8 h-8 text-[var(--sutra-strong)] opacity-80" />
            </div>
            <div>
              <p className="text-[13px] font-medium text-[var(--sutra-ink)]">
                No artifact generated yet.
              </p>
              <p className="text-[11px] text-[var(--text-2)] max-w-sm mx-auto mt-2 font-light">
                Use the AI Architect Chat to describe your business problem to trigger synthesis.
              </p>
            </div>
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
