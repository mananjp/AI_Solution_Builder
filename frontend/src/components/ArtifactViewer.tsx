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

  // Find active artifact or fallback
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
    <div className="flex flex-col h-full bg-slate-950 border border-white/5 rounded-2xl overflow-hidden shadow-2xl">
      {/* Top Tab Bar */}
      <div className="flex items-center justify-between border-b border-white/5 bg-slate-900/60 px-4 pt-2 overflow-x-auto gap-2">
        <div className="flex space-x-1">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const hasData = artifacts.some(a => a.artifact_type === tab.type) || tab.type === 'workable' || tab.type === 'bpmn';
            const isActive = activeType === tab.type;

            return (
              <button
                key={tab.type}
                onClick={() => setActiveType(tab.type)}
                className={`flex items-center gap-2 px-3 py-2.5 text-xs font-medium rounded-t-xl transition-all border-t-2 whitespace-nowrap ${
                  isActive
                    ? 'border-indigo-500 bg-slate-950 text-indigo-300 shadow-sm'
                    : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/5'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-indigo-400' : 'text-slate-500'}`} />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span className="px-1.5 py-0.2 text-[9px] font-bold rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    {tab.badge}
                  </span>
                )}
                {hasData && !tab.badge && (
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 ml-0.5" />
                )}
              </button>
            );
          })}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 pb-2">
          {activeType !== 'workable' && activeType !== 'bpmn' && (
            <button
              onClick={() => setShowRegenModal(true)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 text-xs font-semibold border border-indigo-500/20 transition-colors whitespace-nowrap"
            >
              <RotateCw className="w-3.5 h-3.5" />
              <span>Regenerate</span>
            </button>
          )}

          {activeArtifact && (
            <>
              <button
                onClick={() => handleCopy(getRawContentString(activeArtifact))}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-xs transition-colors whitespace-nowrap"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
              <button
                onClick={() => handleDownload(`${activeType}-spec.txt`, getRawContentString(activeArtifact))}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-xs transition-colors whitespace-nowrap"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Export</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Artifact View Body */}
      <div className="flex-1 overflow-y-auto font-sans">
        {/* Workable Runtime View */}
        {activeType === 'workable' ? (
          <div className="h-full">
            <WorkablePreview solutionId={solutionId} />
          </div>
        ) : activeType === 'bpmn' ? (
          /* BPMN Process View */
          <div className="h-full p-4">
            <BpmnViewer />
          </div>
        ) : activeArtifact ? (
          <div className="max-w-4xl mx-auto p-6 space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-white/5">
              <div>
                <h3 className="text-xl font-bold text-white">{activeArtifact.title}</h3>
                <p className="text-xs text-slate-400 mt-1">
                  Version {activeArtifact.version} • Synthesized by Autonomous Agent
                </p>
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                Production Spec
              </span>
            </div>

            {/* Wireframe vs Raw Code */}
            {activeType === 'wireframe' ? (
              <div className="space-y-4">
                {/* View switcher */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1 p-1 rounded-xl bg-slate-900/80 border border-white/5">
                    <button
                      onClick={() => setWireframeView('canvas')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                        wireframeView === 'canvas'
                          ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/20'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      Canvas Editor
                    </button>
                    <button
                      onClick={() => setWireframeView('details')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                        wireframeView === 'details'
                          ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/20'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      Details
                    </button>
                  </div>
                  <span className="flex items-center gap-1.5 text-[10px] text-slate-500">
                    <PenLine className="w-3 h-3" />
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
                  <div key={idx} className="p-5 rounded-xl bg-slate-900/60 border border-white/5 space-y-3">
                    <h4 className="font-semibold text-base text-indigo-200">{wf.title}</h4>
                    {wf.content_text ? (
                      <pre className="text-xs text-slate-300 font-mono bg-slate-950 p-4 rounded-lg overflow-x-auto whitespace-pre-wrap leading-relaxed">
                        {wf.content_text}
                      </pre>
                    ) : (
                      <div className="text-xs text-slate-400 space-y-2">
                        <p>{wfContent?.description || 'UI Wireframe Blueprint'}</p>
                        {wfContent?.components && (
                          <div className="grid grid-cols-2 gap-2 mt-2">
                            {wfContent.components.map((comp, cidx) => (
                              <div key={cidx} className="p-2 rounded bg-white/5 border border-white/5">
                                <span className="font-semibold text-white">{comp.name || comp.title}</span>
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
              <div className="rounded-xl bg-slate-900/50 border border-white/5 p-5">
                <pre className="text-xs text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">
                  {getRawContentString(activeArtifact)}
                </pre>
              </div>
            )}
          </div>
        ) : (
          <div className="h-64 flex flex-col items-center justify-center text-center space-y-3 text-slate-500 p-8">
            <div className="p-3 rounded-2xl bg-white/[0.02] border border-white/5">
              <Layers className="w-8 h-8 text-slate-600" />
            </div>
            <p className="text-sm font-medium text-slate-400">
              No artifact generated yet for this category.
            </p>
            <p className="text-xs text-slate-500 max-w-sm">
              Use the AI Architect Chat to describe your business problem or confirm recommended modules to trigger synthesis.
            </p>
          </div>
        )}
      </div>

      {/* Scoped Regenerate Modal */}
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
