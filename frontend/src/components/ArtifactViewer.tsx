'use client';

import React, { useState } from 'react';
import {
  FileCode2,
  Layers,
  Database,
  Layout,
  Calendar,
  Network,
  Copy,
  Check,
  Download,
  RotateCw,
  GitFork,
  Play,
  PenLine
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { Artifact, ArtifactType } from '@/types';
import BpmnViewer from './BpmnViewer';
import WorkablePreview from './WorkablePreview';
import RegenerateModal from './RegenerateModal';
import WireframeCanvas from './WireframeCanvas';
import MarkdownRenderer from './MarkdownRenderer';

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

  const tabs: { type: ArtifactType; label: string; icon: LucideIcon; badge?: string }[] = [
    { type: 'hld', label: 'High-Level Design', icon: Layers },
    { type: 'lld', label: 'Low-Level Design', icon: Network },
    { type: 'workable', label: 'Mounted Live App', icon: Play, badge: 'Operational' },
    { type: 'bpmn', label: 'BPMN 2.0 Process', icon: GitFork },
    { type: 'wireframe', label: 'UI Wireframes', icon: Layout },
    { type: 'database_schema', label: 'DB Schema & ERD', icon: Database },
    { type: 'api_spec', label: 'OpenAPI Spec', icon: FileCode2 },
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
    <div className="flex flex-col h-full bg-[#0a0a0a] border border-[#1a1a1a] rounded-xl overflow-hidden shadow-xl">
      {/* Top Tab Bar */}
      <div className="flex items-center justify-between border-b border-[#1a1a1a] bg-[#111] px-3 pt-2 overflow-x-auto gap-2">
        <div className="flex space-x-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const hasData = artifacts.some(a => a.artifact_type === tab.type) || tab.type === 'workable' || tab.type === 'bpmn';
            const isActive = activeType === tab.type;

            return (
              <button
                key={tab.type}
                onClick={() => setActiveType(tab.type)}
                className={`flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-t-lg transition-colors border-b-2 whitespace-nowrap -mb-px ${isActive
                    ? 'border-[#6366f1] bg-[#0a0a0a] text-white'
                    : 'border-transparent text-[#666] hover:text-[#a1a1a1] hover:bg-[#161616]'
                  }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-[#818cf8]' : 'text-[#555]'}`} />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span className="badge badge-green text-[9px]">
                    {tab.badge}
                  </span>
                )}
                {hasData && !tab.badge && <span className="w-1.5 h-1.5 rounded-full bg-[#4ade80] ml-0.5" />}
              </button>
            );
          })}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 pb-2">
          {activeType !== 'workable' && activeType !== 'bpmn' && (
            <button
              onClick={() => setShowRegenModal(true)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#161616] hover:bg-[#1f1f1f] text-[#818cf8] text-xs font-medium border border-[#242424] transition-colors whitespace-nowrap"
            >
              <RotateCw className="w-3.5 h-3.5" />
              <span>Regenerate</span>
            </button>
          )}

          {activeArtifact && (
            <>
              <button
                onClick={() => handleCopy(getRawContentString(activeArtifact))}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#161616] hover:bg-[#1f1f1f] text-[#a1a1a1] text-xs border border-[#242424] transition-colors whitespace-nowrap"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-[#4ade80]" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
              <button
                onClick={() => handleDownload(`${activeType}-spec.txt`, getRawContentString(activeArtifact))}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#161616] hover:bg-[#1f1f1f] text-[#a1a1a1] text-xs border border-[#242424] transition-colors whitespace-nowrap"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Export</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Artifact View Body */}
      <div className="flex-1 overflow-y-auto font-sans p-4">
        {activeType === 'workable' ? (
          <div className="h-full">
            <WorkablePreview solutionId={solutionId} />
          </div>
        ) : activeType === 'bpmn' ? (
          <div className="h-full">
            <BpmnViewer />
          </div>
        ) : activeArtifact ? (
          <div className="max-w-4xl mx-auto space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#1a1a1a]">
              <div>
                <h3 className="text-base font-semibold text-white">{activeArtifact.title}</h3>
                <p className="text-xs text-[#555] mt-0.5 font-mono">
                  v{activeArtifact.version} · Synthesized by Swarm Agent
                </p>
              </div>
              <span className="badge badge-blue">
                Production Spec
              </span>
            </div>

            {/* Wireframe vs Markdown Spec */}
            {activeType === 'wireframe' ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1 p-1 rounded-lg bg-[#111] border border-[#1a1a1a]">
                    <button
                      onClick={() => setWireframeView('canvas')}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${wireframeView === 'canvas'
                          ? 'bg-[#161616] text-white border border-[#2e2e2e]'
                          : 'text-[#666] hover:text-white'
                        }`}
                    >
                      Canvas Editor
                    </button>
                    <button
                      onClick={() => setWireframeView('details')}
                      className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${wireframeView === 'details'
                          ? 'bg-[#161616] text-white border border-[#2e2e2e]'
                          : 'text-[#666] hover:text-white'
                        }`}
                    >
                      Details
                    </button>
                  </div>
                  <span className="flex items-center gap-1.5 text-[11px] text-[#555]">
                    <PenLine className="w-3.5 h-3.5" />
                    Drag &amp; connect components
                  </span>
                </div>

                {wireframeView === 'canvas' && currentArtifacts.length > 0 ? (
                  <WireframeCanvas wireframes={currentArtifacts} onUpdate={onArtifactUpdated} />
                ) : (
                  currentArtifacts.map((wf, idx) => (
                    <div key={idx} className="p-4 rounded-xl bg-[#111] border border-[#1a1a1a] space-y-2">
                      <h4 className="font-semibold text-xs text-white">{wf.title}</h4>
                      <MarkdownRenderer content={getRawContentString(wf)} />
                    </div>
                  ))
                )}
              </div>
            ) : (
              <div className="rounded-xl bg-[#111] border border-[#1a1a1a] p-5">
                <MarkdownRenderer content={getRawContentString(activeArtifact)} />
              </div>
            )}
          </div>
        ) : (
          <div className="h-64 flex flex-col items-center justify-center text-center space-y-2 text-[#555] p-8">
            <div className="p-3 rounded-lg bg-[#111] border border-[#1a1a1a]">
              <Layers className="w-6 h-6 text-[#555]" />
            </div>
            <p className="text-xs font-medium text-[#a1a1a1]">
              No artifact generated yet for this category.
            </p>
            <p className="text-[11px] text-[#555] max-w-sm">
              Use the AI Architect Chat to describe your business problem to trigger synthesis.
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
