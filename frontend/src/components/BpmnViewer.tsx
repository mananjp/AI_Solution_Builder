'use client';

import React, { useState } from 'react';
import { 
  Play, 
  CheckCircle, 
  GitFork, 
  WarningCircle, 
  Stack, 
  Cpu, 
  User, 
  Lightbulb
} from '@phosphor-icons/react/dist/ssr';
import { Button } from '@/components/ui/button';
import { BpmnNode, BpmnProcess } from '@/types';

interface BpmnViewerProps {
  processData?: BpmnProcess;
}

export default function BpmnViewer({ processData }: BpmnViewerProps) {
  const [selectedNode, setSelectedNode] = useState<BpmnNode | null>(null);

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
        return <Play className="w-3.5 h-3.5 text-success" />;
      case 'gateway':
        return <GitFork className="w-3.5 h-3.5 text-primary" />;
      case 'end':
        return <CheckCircle className="w-3.5 h-3.5 text-destructive" />;
      default:
        return <Cpu className="w-3.5 h-3.5 text-primary" />;
    }
  };

  return (
    <div className="flex flex-col h-full bg-background border border-border rounded-lg overflow-hidden">
      <div className="p-4 border-b border-border bg-card/60 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-primary/20 text-primary border border-primary/30">
              BPMN 2.0 Process Intelligence
            </span>
            <span className="text-xs text-muted-foreground">Process Flow & Swimlanes</span>
          </div>
          <h3 className="text-base font-bold text-foreground mt-1">{process.processName}</h3>
        </div>

        {process.bottlenecks && process.bottlenecks.length > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-primary/10 border border-primary/20 text-primary text-xs">
            <WarningCircle className="w-4 h-4 text-primary flex-shrink-0" />
            <span>
              <strong>AI Bottleneck Predictor:</strong> {process.bottlenecks[0]}
            </span>
          </div>
        )}
      </div>

      <div className="flex-1 p-6 overflow-y-auto flex flex-col gap-6">
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            <Stack className="w-4 h-4 text-primary" />
            <span>Process Steps & Decision Graph</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {process.nodes.map((node, idx) => (
              <div
                key={node.id}
                onClick={() => setSelectedNode(node)}
                className={`p-4 rounded border text-left cursor-pointer transition-all relative select-none flex flex-col justify-between min-h-[130px] ${
                  selectedNode?.id === node.id
                    ? 'bg-card/40 border-primary/60'
                    : node.isBottleneck
                    ? 'bg-card/20 border-primary/30 hover:border-primary/50'
                    : 'bg-card/40 border-border hover:border-white/[0.08] hover:bg-card/60'
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg bg-accent border border-border">
                      {getNodeIcon(node)}
                    </div>
                    <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                      Step {idx + 1}
                    </span>
                  </div>

                  {node.isBottleneck ? (
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-primary/20 text-primary border border-primary/30 animate-pulse">
                      Bottleneck
                    </span>
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-accent text-muted-foreground">
                      {node.type.toUpperCase()}
                    </span>
                  )}
                </div>

                <div>
                  <h4 className="font-bold text-sm text-foreground leading-tight">{node.label}</h4>
                  <div className="flex items-center gap-1.5 text-[11px] text-primary mt-1.5">
                    <User className="w-3 h-3" />
                    <span>{node.actor}</span>
                  </div>
                </div>

                <p className="text-[11px] text-muted-foreground/70 mt-2 line-clamp-2 leading-relaxed">
                  {node.description}
                </p>
              </div>
            ))}
          </div>
        </div>

        {selectedNode && (
          <div className="p-5 rounded-lg bg-card/30 border border-primary/30 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-primary" />
                <h4 className="font-bold text-foreground text-sm">Step Deep-Dive: {selectedNode.label}</h4>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedNode(null)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                Close
              </Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div className="p-3 rounded bg-card/60 border border-border">
                <span className="text-muted-foreground/70 font-medium">Actor / Swimlane:</span>
                <p className="font-semibold text-foreground mt-1">{selectedNode.actor}</p>
              </div>
              <div className="p-3 rounded bg-card/60 border border-border">
                <span className="text-muted-foreground/70 font-medium">Element Classification:</span>
                <p className="font-semibold text-primary mt-1 capitalize">{selectedNode.type} Event</p>
              </div>
              <div className="p-3 rounded bg-card/60 border border-border">
                <span className="text-muted-foreground/70 font-medium">Performance Profile:</span>
                <p className={`font-semibold mt-1 ${selectedNode.isBottleneck ? 'text-primary' : 'text-success'}`}>
                  {selectedNode.isBottleneck ? 'High Latency / Manual Gate' : 'Automated (< 50ms)'}
                </p>
              </div>
            </div>

            <p className="text-xs text-muted-foreground bg-background/60 p-3 rounded border border-border leading-relaxed">
              {selectedNode.description}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
