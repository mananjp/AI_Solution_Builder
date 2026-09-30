'use client';

import React, { useState } from 'react';
import { 
  Play, 
  CheckCircle2, 
  GitFork, 
  AlertTriangle, 
  Layers, 
  Cpu, 
  User, 
  Sparkles
} from 'lucide-react';
import { BpmnNode, BpmnProcess } from '@/types';
import { Button } from "@/components/ui/button";

interface BpmnViewerProps {
  processData?: BpmnProcess;
}

export default function BpmnViewer({ processData }: BpmnViewerProps) {
  const [selectedNode, setSelectedNode] = useState<BpmnNode | null>(null);

  // Default rich BPMN process if not provided
  const process: BpmnProcess = processData || {
    processName: 'Order Placement & Real-Time Inventory Allocation Workflow',
    swimlanes: ['Customer / POS Client', 'API Gateway & Auth', 'Inventory Engine', 'Payment Gateway', 'Fulfillment'],
    bottlenecks: ['Manual Supervisor Price Override', 'Bank Gateway Timeout Retry'],
    nodes: [
      {
        id: 'n1',
        type: 'start',
        label: 'Order Initiated',
        actor: 'Customer / POS Client',
        description: 'Cashier scans barcode or customer submits web checkout cart.',
      },
      {
        id: 'n2',
        type: 'task',
        label: 'Validate Token & Idempotency',
        actor: 'API Gateway & Auth',
        description: 'Gateway checks JWT signature and verifies unique client_transaction_id.',
      },
      {
        id: 'n3',
        type: 'task',
        label: 'Pessimistic Stock Lock',
        actor: 'Inventory Engine',
        description: 'Row-level locking on inventory_stocks to reserve item quantities.',
      },
      {
        id: 'n4',
        type: 'gateway',
        label: 'Stock Available?',
        actor: 'Inventory Engine',
        description: 'Evaluates if available_qty >= requested_qty.',
      },
      {
        id: 'n5',
        type: 'task',
        label: 'Process Card / QR Payment',
        actor: 'Payment Gateway',
        description: 'Calls Stripe / Payment provider with idempotency key.',
      },
      {
        id: 'n6',
        type: 'task',
        label: 'Manual Supervisor Override',
        actor: 'Customer / POS Client',
        description: 'Required if price discount > 20% or stock exception occurs.',
        isBottleneck: true,
      },
      {
        id: 'n7',
        type: 'task',
        label: 'Dispatch Restock Alert & Order Slip',
        actor: 'Fulfillment',
        description: 'Emits asynchronous Celery/event-bus event for warehouse picking.',
      },
      {
        id: 'n8',
        type: 'end',
        label: 'Order Completed',
        actor: 'Customer / POS Client',
        description: 'Receipt generated and PDF sent to customer inbox.',
      },
    ],
    connections: [
      { from: 'n1', to: 'n2' },
      { from: 'n2', to: 'n3' },
      { from: 'n3', to: 'n4' },
      { from: 'n4', to: 'n5', label: 'Yes' },
      { from: 'n4', to: 'n6', label: 'Low Stock' },
      { from: 'n6', to: 'n5', label: 'Approved' },
      { from: 'n5', to: 'n7' },
      { from: 'n7', to: 'n8' },
    ],
  };

  const getNodeIcon = (node: BpmnNode) => {
    switch (node.type) {
      case 'start':
        return <Play className="w-3.5 h-3.5 text-[var(--green)]" />;
      case 'gateway':
        return <GitFork className="w-3.5 h-3.5 text-[var(--amber)]" />;
      case 'end':
        return <CheckCircle2 className="w-3.5 h-3.5 text-[var(--red)]" />;
      default:
        return <Cpu className="w-3.5 h-3.5 text-[var(--sutra-strong)]" />;
    }
  };

  return (
    <div className="flex flex-col h-full bg-[var(--bg-2)] border border-[var(--border)] rounded-sm overflow-hidden shadow-sm">
      {/* Top BPMN Header */}
      <div className="p-4 border-b border-[var(--border)] bg-[var(--bg-3)] flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-sm bg-[var(--sutra-strong)]/15 text-[var(--sutra-strong)] border border-[var(--sutra-strong)]/30 font-mono">
              BPMN 2.0 Process Intelligence
            </span>
            <span className="text-xs text-[var(--text-2)] font-light">Process Flow &amp; Swimlanes</span>
          </div>
          <h3 className="text-base font-serif font-bold text-[var(--sutra-ink)] mt-1">{process.processName}</h3>
        </div>

        {/* Bottleneck Alert Badge */}
        {process.bottlenecks && process.bottlenecks.length > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-sm bg-[var(--amber-wash)] border border-[var(--amber-wash)] text-[var(--amber)] text-xs">
            <AlertTriangle className="w-4 h-4 text-[var(--amber)] flex-shrink-0" />
            <span>
              <strong>AI Bottleneck Predictor:</strong> {process.bottlenecks[0]}
            </span>
          </div>
        )}
      </div>

      {/* Swimlane Diagram Container */}
      <div className="flex-1 p-6 overflow-y-auto space-y-6 bg-[var(--bg)]">
        {/* Swimlanes Overview */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--text-2)] uppercase tracking-wider">
            <Layers className="w-4 h-4 text-[var(--sutra-strong)]" />
            <span>Process Steps &amp; Decision Graph</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {process.nodes.map((node, idx) => (
              <div
                key={node.id}
                onClick={() => setSelectedNode(node)}
                className={`p-4 rounded-sm border text-left cursor-pointer transition-all relative select-none flex flex-col justify-between min-h-[130px] ${
                  selectedNode?.id === node.id
                    ? 'bg-[var(--sutra-strong)]/10 border-[var(--sutra-strong)] shadow-md ring-1 ring-[var(--sutra-strong)]/40 scale-[1.02]'
                    : node.isBottleneck
                    ? 'bg-[var(--amber-wash)] border-[var(--amber-wash)] hover:border-[var(--amber-wash)]'
                    : 'bg-[var(--bg-2)] border-[var(--border)] hover:border-[var(--sutra-strong)]/40 hover:bg-[var(--bg-3)]'
                }`}
              >
                {/* Node Step Header */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-sm bg-[var(--bg-3)] border border-[var(--border)]">
                      {getNodeIcon(node)}
                    </div>
                    <span className="text-[10px] font-semibold text-[var(--text-2)] uppercase tracking-wider font-mono">
                      Step {idx + 1}
                    </span>
                  </div>

                  {node.isBottleneck ? (
                    <span className="text-[10px] px-2 py-0.5 rounded-sm font-bold bg-[var(--amber-wash)] text-[var(--amber)] border border-[var(--amber-wash)] animate-pulse">
                      Bottleneck
                    </span>
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 rounded-sm font-medium bg-[var(--bg-3)] text-[var(--text-2)] border border-[var(--border)]">
                      {node.type.toUpperCase()}
                    </span>
                  )}
                </div>

                <div>
                  <h4 className="font-serif font-bold text-sm text-[var(--sutra-ink)] leading-tight">{node.label}</h4>
                  <div className="flex items-center gap-1.5 text-[11px] text-[var(--sutra-strong)] mt-1.5 font-medium">
                    <User className="w-3 h-3" />
                    <span>{node.actor}</span>
                  </div>
                </div>

                <p className="text-[11px] text-[var(--text-2)] mt-2 line-clamp-2 leading-relaxed font-light">
                  {node.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Selected Node Inspector Drawer */}
        {selectedNode && (
          <div className="p-5 rounded-sm bg-[var(--bg-2)] border border-[var(--sutra-strong)]/40 space-y-3 animate-fade-in shadow-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[var(--sutra-strong)]" />
                <h4 className="font-serif font-bold text-[var(--sutra-ink)] text-sm">Step Deep-Dive: {selectedNode.label}</h4>
              </div>
              <Button variant="ghost" size="default"
                onClick={() => setSelectedNode(null)}
                className="text-xs text-[var(--text-3)] hover:text-[var(--text)] transition-colors"
              >
                Close
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-sm bg-[var(--bg-3)] border border-[var(--border)]">
                <span className="text-[var(--text-2)] font-medium">Actor / Swimlane:</span>
                <p className="font-semibold text-[var(--sutra-ink)] mt-1">{selectedNode.actor}</p>
              </div>
              <div className="p-3 rounded-sm bg-[var(--bg-3)] border border-[var(--border)]">
                <span className="text-[var(--text-2)] font-medium">Element Classification:</span>
                <p className="font-semibold text-[var(--sutra-strong)] mt-1 capitalize">{selectedNode.type} Event</p>
              </div>
              <div className="p-3 rounded-sm bg-[var(--bg-3)] border border-[var(--border)]">
                <span className="text-[var(--text-2)] font-medium">Performance Profile:</span>
                <p className={`font-semibold mt-1 ${selectedNode.isBottleneck ? 'text-[var(--amber)]' : 'text-[var(--green)]'}`}>
                  {selectedNode.isBottleneck ? 'High Latency / Manual Gate' : 'Automated (< 50ms)'}
                </p>
              </div>
            </div>

            <p className="text-xs text-[var(--sutra-ink)] bg-[var(--bg-3)] p-3 rounded-sm border border-[var(--border)] leading-relaxed font-light">
              {selectedNode.description}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
