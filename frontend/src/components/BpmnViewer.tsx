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
        return <Play className="w-3.5 h-3.5 text-emerald-400" />;
      case 'gateway':
        return <GitFork className="w-3.5 h-3.5 text-amber-400" />;
      case 'end':
        return <CheckCircle2 className="w-3.5 h-3.5 text-rose-400" />;
      default:
        return <Cpu className="w-3.5 h-3.5 text-indigo-400" />;
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 border border-white/5 rounded-2xl overflow-hidden shadow-2xl">
      {/* Top BPMN Header */}
      <div className="p-4 border-b border-white/5 bg-slate-900/60 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              BPMN 2.0 Process Intelligence
            </span>
            <span className="text-xs text-slate-400">Process Flow & Swimlanes</span>
          </div>
          <h3 className="text-base font-bold text-white mt-1">{process.processName}</h3>
        </div>

        {/* Bottleneck Alert Badge */}
        {process.bottlenecks && process.bottlenecks.length > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs">
            <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />
            <span>
              <strong>AI Bottleneck Predictor:</strong> {process.bottlenecks[0]}
            </span>
          </div>
        )}
      </div>

      {/* Swimlane Diagram Container */}
      <div className="flex-1 p-6 overflow-y-auto space-y-6">
        {/* Swimlanes Overview */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            <Layers className="w-4 h-4 text-indigo-400" />
            <span>Process Steps & Decision Graph</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {process.nodes.map((node, idx) => (
              <div
                key={node.id}
                onClick={() => setSelectedNode(node)}
                className={`p-4 rounded-xl border text-left cursor-pointer transition-all relative select-none flex flex-col justify-between min-h-[130px] ${
                  selectedNode?.id === node.id
                    ? 'bg-indigo-950/40 border-indigo-500/60 shadow-lg shadow-indigo-500/20 scale-[1.02]'
                    : node.isBottleneck
                    ? 'bg-amber-950/20 border-amber-500/30 hover:border-amber-500/50'
                    : 'bg-slate-900/40 border-white/5 hover:border-white/20 hover:bg-slate-900/60'
                }`}
              >
                {/* Node Step Header */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg bg-white/5 border border-white/5">
                      {getNodeIcon(node)}
                    </div>
                    <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                      Step {idx + 1}
                    </span>
                  </div>

                  {node.isBottleneck ? (
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 animate-pulse">
                      Bottleneck
                    </span>
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-white/5 text-slate-400">
                      {node.type.toUpperCase()}
                    </span>
                  )}
                </div>

                <div>
                  <h4 className="font-bold text-sm text-white leading-tight">{node.label}</h4>
                  <div className="flex items-center gap-1.5 text-[11px] text-indigo-400 mt-1.5">
                    <User className="w-3 h-3" />
                    <span>{node.actor}</span>
                  </div>
                </div>

                <p className="text-[11px] text-slate-500 mt-2 line-clamp-2 leading-relaxed">
                  {node.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Selected Node Inspector Drawer */}
        {selectedNode && (
          <div className="p-5 rounded-2xl bg-indigo-950/30 border border-indigo-500/30 space-y-3 animate-fade-in">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-indigo-400" />
                <h4 className="font-bold text-white text-sm">Step Deep-Dive: {selectedNode.label}</h4>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-xs text-slate-400 hover:text-white"
              >
                Close
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-slate-900/60 border border-white/5">
                <span className="text-slate-500 font-medium">Actor / Swimlane:</span>
                <p className="font-semibold text-slate-200 mt-1">{selectedNode.actor}</p>
              </div>
              <div className="p-3 rounded-xl bg-slate-900/60 border border-white/5">
                <span className="text-slate-500 font-medium">Element Classification:</span>
                <p className="font-semibold text-indigo-300 mt-1 capitalize">{selectedNode.type} Event</p>
              </div>
              <div className="p-3 rounded-xl bg-slate-900/60 border border-white/5">
                <span className="text-slate-500 font-medium">Performance Profile:</span>
                <p className={`font-semibold mt-1 ${selectedNode.isBottleneck ? 'text-amber-400' : 'text-emerald-400'}`}>
                  {selectedNode.isBottleneck ? 'High Latency / Manual Gate' : 'Automated (< 50ms)'}
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-300 bg-slate-950/60 p-3 rounded-xl border border-white/5 leading-relaxed">
              {selectedNode.description}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
