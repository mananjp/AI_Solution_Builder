'use client';

import { useCallback, useEffect, useMemo } from 'react';
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Handle,
  Position,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Plus, FloppyDisk, Trash } from '@phosphor-icons/react/dist/ssr';
import type { Artifact } from '@/types';

// --- Node data shapes -------------------------------------------------
type ScreenNodeData = { label: string; subtitle?: string; kind: 'screen' };
type ComponentNodeData = {
  label: string;
  kind: 'component';
  componentType: string;
  description?: string;
  fieldCount: number;
};

type WireframeNodeData = ScreenNodeData | ComponentNodeData;

type NodeKind<T extends WireframeNodeData, K extends T['kind']> = T extends { kind: K } ? T : never;

// --- Custom node renderers --------------------------------------------
function ScreenNode({ data, selected }: NodeProps<Node<NodeKind<WireframeNodeData, 'screen'>>>) {
  return (
    <div
      className={`w-[240px] rounded-lg border bg-slate-900 shadow-lg transition-shadow ${
        selected ? 'border-indigo-400 ring-2 ring-indigo-500/30' : 'border-white/10'
      }`}
    >
      <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-t-lg bg-slate-950/80 border-b border-white/5">
        <span className="w-2 h-2 rounded-full bg-rose-400/80" />
        <span className="w-2 h-2 rounded-full bg-amber-400/80" />
        <span className="w-2 h-2 rounded-full bg-emerald-400/80" />
        <span className="ml-2 text-[10px] font-medium text-slate-200 truncate">{data.label}</span>
      </div>
      <div className="px-3 py-3">
        <div className="text-[10px] font-semibold text-indigo-300 uppercase tracking-wide">Screen</div>
        <div className="mt-0.5 text-[10px] text-slate-400 leading-relaxed line-clamp-2">
          {data.subtitle || 'Mobile screen blueprint — drag to reposition'}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!w-2 !h-2 !bg-indigo-400" />
    </div>
  );
}

function ComponentNode({ data, selected }: NodeProps<Node<NodeKind<WireframeNodeData, 'component'>>>) {
  return (
    <div
      className={`w-[210px] rounded-lg border bg-slate-800/90 shadow-md transition-shadow ${
        selected ? 'border-cyan-400 ring-2 ring-cyan-500/30' : 'border-white/10'
      }`}
    >
      <div className="px-3 py-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] font-semibold text-white truncate">{data.label}</span>
          <span className="px-1.5 py-0.5 rounded bg-cyan-500/15 text-cyan-300 text-[9px] font-bold uppercase">
            {data.componentType}
          </span>
        </div>
        {data.description && (
          <p className="mt-1 text-[10px] text-slate-400 leading-relaxed line-clamp-2">{data.description}</p>
        )}
        {data.fieldCount > 0 && (
          <p className="mt-1.5 text-[9px] text-slate-500">Fields: {data.fieldCount}</p>
        )}
      </div>
      <Handle type="target" position={Position.Top} className="!w-2 !h-2 !bg-cyan-400" />
    </div>
  );
}

// --- Canvas serialization helpers --------------------------------------
const SCREEN_GAP_X = 300;
const COMPONENT_GAP_Y = 130;

function buildCanvas(wireframes: Artifact[]): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  let cursorX = 60;

  wireframes.forEach((artifact) => {
    const content = artifact.content && typeof artifact.content === 'object' ? artifact.content : {};
    const screens = Array.isArray(content.screens) ? content.screens : [];
    const screenItems =
      screens.length > 0
        ? screens.map((s: Record<string, unknown>) => ({
            name: String(s.name ?? 'Untitled Screen'),
            description: String(s.description ?? ''),
            components: Array.isArray(s.components) ? s.components : [],
          }))
        : [
            {
              name: artifact.title || 'Wireframe',
              description: String(content.description ?? ''),
              components: Array.isArray(content.components) ? content.components : [],
            },
          ];

    screenItems.forEach((screen, sIdx) => {
      const screenNodeId = `${artifact.id}-screen-${sIdx}`;
      nodes.push({
        id: screenNodeId,
        type: 'screen',
        position: { x: cursorX, y: 60 },
        data: { label: screen.name, subtitle: screen.description, kind: 'screen' } as ScreenNodeData,
      });

      screen.components.forEach((comp: Record<string, unknown>, cIdx: number) => {
        const compNodeId = `${screenNodeId}-comp-${cIdx}`;
        const fields = Array.isArray(comp.fields) ? comp.fields : [];
        nodes.push({
          id: compNodeId,
          type: 'component',
          position: { x: cursorX, y: 190 + cIdx * COMPONENT_GAP_Y },
          data: {
            label: String(comp.title ?? comp.name ?? 'Component'),
            componentType: String(comp.type ?? 'widget'),
            description: comp.description ? String(comp.description) : undefined,
            fieldCount: fields.length,
            kind: 'component',
          } as ComponentNodeData,
        });
        edges.push({
          id: `${screenNodeId}-edge-${cIdx}`,
          source: screenNodeId,
          target: compNodeId,
          animated: true,
          style: { stroke: '#818cf8', strokeWidth: 1.5 },
        });
      });
      cursorX += SCREEN_GAP_X;
    });
  });

  return { nodes, edges };
}

function serializeCanvas(
  artifact: Artifact,
  nodes: Node[],
  edges: Edge[]
): Record<string, unknown> {
  const original = artifact.content && typeof artifact.content === 'object' ? artifact.content : {};
  const screens: Record<string, unknown>[] = [];
  const byTarget = new Map<string, string>();
  edges.forEach((edge) => byTarget.set(edge.target, edge.source));

  nodes
    .filter((n) => n.type === 'screen')
    .forEach((screenNode) => {
      const data = screenNode.data as ScreenNodeData;
      const source = screenNode.id;
      const components = nodes
        .filter((n) => n.type === 'component' && byTarget.get(n.id) === source)
        .sort((a, b) => a.position.y - b.position.y)
        .map((compNode) => {
          const cd = compNode.data as ComponentNodeData;
          return {
            title: cd.label,
            type: cd.componentType,
            description: cd.description,
            x: Math.round(compNode.position.x),
            y: Math.round(compNode.position.y),
          };
        });

      const existing = Array.isArray(original.screens)
        ? (original.screens as Record<string, unknown>[])
        : [];

      screens.push({
        name: data.label,
        description: data.subtitle,
        route:
          existing.find((s) => String(s.name ?? '') === data.label)?.route ??
          `/${data.label.toLowerCase().replace(/\s+/g, '-')}`,
        components,
      });
    });

  return {
    ...original,
    screens,
    _canvas: {
      serializedAt: new Date().toISOString(),
    },
  };
}

// --- Editable canvas ------------------------------------------------
interface WireframeCanvasInnerProps {
  wireframes: Artifact[];
  onUpdate?: (updated: Artifact) => void;
}

function WireframeCanvasInner({ wireframes, onUpdate }: WireframeCanvasInnerProps) {
  const initial = useMemo(() => buildCanvas(wireframes), [wireframes]);
  const [nodes, setNodes] = useNodesState(initial.nodes);
  const [edges, setEdges] = useEdgesState(initial.edges);

  useEffect(() => {
    const rebuilt = buildCanvas(wireframes);
    setNodes(rebuilt.nodes);
    setEdges(rebuilt.edges);
  }, [wireframes, setNodes, setEdges]);

  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((nds) => applyNodeChanges(changes, nds)),
    [setNodes]
  );

  const handleEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    [setEdges]
  );

  const handleConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges]
  );

  const selectedIds = useMemo(
    () => nodes.filter((n) => n.selected).map((n) => n.id),
    [nodes]
  );

  const addComponent = () => {
    const source = selectedIds.find((id) => id.includes('screen')) ?? nodes[0]?.id;
    if (!source) return;
    const count = nodes.filter((n) => edges.some((e) => e.source === source && e.target === n.id)).length;
    const lastY = nodes.find((n) => n.id === source)?.position.y ?? 190;
    const id = `${source}-comp-new-${Date.now()}`;
    const position = { x: 60, y: lastY + count * COMPONENT_GAP_Y + COMPONENT_GAP_Y };
    setNodes((nds) => [
      ...nds,
      {
        id,
        type: 'component',
        position,
        data: {
          label: 'New Component',
          componentType: 'widget',
          description: 'Describe this UI component',
          fieldCount: 0,
          kind: 'component',
        } as ComponentNodeData,
      },
    ]);
    setEdges((eds) => [
      ...eds,
      {
        id: `edge-${id}`,
        source,
        target: id,
        animated: true,
      },
    ]);
  };

  const deleteSelected = () => {
    setNodes((nds) => nds.filter((n) => !n.selected));
    setEdges((eds) => eds.filter((e) => !selectedIds.includes(e.source) && !selectedIds.includes(e.target)));
  };

  const save = () => {
    wireframes.forEach((artifact) => {
      const prefix = `${artifact.id}-`;
      const owned = nodes.filter((n) => n.id.startsWith(prefix));
      const ownedEdgeIds = new Set<string>();
      edges.forEach((e) => {
        if (owned.some((n) => n.id === e.source) && owned.some((n) => n.id === e.target)) {
          ownedEdgeIds.add(e.id);
        }
      });
      onUpdate?.({
        ...artifact,
        version: artifact.version + 1,
        content: serializeCanvas(artifact, owned, edges.filter((e) => ownedEdgeIds.has(e.id))),
      });
    });
  };

  const nodeTypes = useMemo(() => ({ screen: ScreenNode, component: ComponentNode }), []);

  return (
    <div className="rounded-xl border border-white/5 overflow-hidden bg-slate-950">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/5 bg-slate-900/70">
        <div className="flex items-center gap-2">
          <button
            onClick={addComponent}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/20 text-cyan-300 text-xs font-semibold transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Component</span>
          </button>
          <button
            onClick={deleteSelected}
            disabled={selectedIds.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 text-rose-300 text-xs font-semibold transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <Trash className="w-3.5 h-3.5" />
            <span>Delete</span>
          </button>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-slate-500 hidden sm:block">
            Drag nodes to reposition • Connect screens to components
          </span>
          <button
            onClick={save}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/25 text-emerald-300 text-xs font-bold transition-colors"
          >
            <FloppyDisk className="w-3.5 h-3.5" />
            <span>Save Layout</span>
          </button>
        </div>
      </div>

      {/* Flow canvas */}
      <div className="h-[560px]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onConnect={handleConnect}
          fitView
          fitViewOptions={{ padding: 0.4, maxZoom: 1 }}
          minZoom={0.2}
          maxZoom={1.5}
          proOptions={{ hideAttribution: false }}
          defaultEdgeOptions={{ type: 'smoothstep' }}
          colorMode="dark"
        >
          <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#1e293b" />
          <MiniMap
            pannable
            zoomable
            className="!bg-slate-900/80"
            nodeColor={(n) => (n.type === 'screen' ? '#6366f1' : '#06b6d4')}
          />
          <Controls className="!bg-slate-900 !border-white/10" />
        </ReactFlow>
      </div>
    </div>
  );
}

interface WireframeCanvasProps {
  wireframes: Artifact[];
  onUpdate?: (updated: Artifact) => void;
}

export default function WireframeCanvas(props: WireframeCanvasProps) {
  return (
    <ReactFlowProvider>
      <WireframeCanvasInner {...props} />
    </ReactFlowProvider>
  );
}