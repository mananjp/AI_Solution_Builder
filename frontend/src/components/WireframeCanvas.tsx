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
import { Plus, Save, Trash2 } from 'lucide-react';
import type { Artifact } from '@/types';
import { Button } from "@/components/ui/button";

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
      className={`w-[240px] rounded-lg border bg-[var(--text)] shadow-lg transition-shadow ${
        selected ? 'border-[var(--sutra-strong)] ring-2 ring-[var(--sutra-strong)]/40' : 'border-[var(--border)]'
      }`}
    >
      <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-t-lg bg-[var(--text)] border-b border-[var(--border)]">
        <span className="w-2 h-2 rounded-full bg-[var(--red-wash)]" />
        <span className="w-2 h-2 rounded-full bg-[var(--amber-wash)]" />
        <span className="w-2 h-2 rounded-full bg-[var(--green-wash)]" />
        <span className="ml-2 text-[10px] font-medium text-[var(--border)] truncate">{data.label}</span>
      </div>
      <div className="px-3 py-3">
        <div className="text-[10px] font-semibold text-[var(--sutra-strong)] uppercase tracking-wide">Screen</div>
        <div className="mt-0.5 text-[10px] text-[var(--text-3)] leading-relaxed line-clamp-2">
          {data.subtitle || 'Mobile screen blueprint — drag to reposition'}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!w-2 !h-2 !bg-[var(--sutra-strong)]" />
    </div>
  );
}

function ComponentNode({ data, selected }: NodeProps<Node<NodeKind<WireframeNodeData, 'component'>>>) {
  return (
    <div
      className={`w-[210px] rounded-lg border bg-[var(--text)] shadow-md transition-shadow ${
        selected ? 'border-[var(--info)] ring-2 ring-[var(--info-wash)]' : 'border-[var(--border)]'
      }`}
    >
      <div className="px-3 py-2">
        <div className="flex items-center justify-between gap-2">
          {/* This node's header is the dark panel (bg-[var(--text)]), so the
              label is drawn in the background colour to read as reversed out of
              it. Tying it to --background rather than white keeps the pairing
              correct if the panel and page ever swap values. */}
          <span className="text-[11px] font-semibold text-[var(--background)] truncate">{data.label}</span>
          <span className="px-1.5 py-0.5 rounded bg-[var(--info-wash)] text-[var(--info)] text-[9px] font-bold uppercase">
            {data.componentType}
          </span>
        </div>
        {data.description && (
          <p className="mt-1 text-[10px] text-[var(--text-3)] leading-relaxed line-clamp-2">{data.description}</p>
        )}
        {data.fieldCount > 0 && (
          <p className="mt-1.5 text-[9px] text-[var(--text-2)]">Fields: {data.fieldCount}</p>
        )}
      </div>
      <Handle type="target" position={Position.Top} className="!w-2 !h-2 !bg-[var(--info)]" />
    </div>
  );
}

// --- Canvas serialization helpers --------------------------------------
const SCREEN_GAP_X = 300;
const COMPONENT_GAP_Y = 130;

/* React Flow's Background and MiniMap take colours as SVG attributes, not as
   class names, so they cannot read a CSS variable in a utility. These resolve
   the theme's own tokens once at module load instead, which keeps the canvas
   on the same palette as the rest of the app and lets it follow the theme
   rather than carrying three hardcoded hexes. */
const themeColor = (name: string, fallback: string) => {
  if (typeof window === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
};

const CANVAS_SURFACE = themeColor('--surface', '#161616');
const CANVAS_PRIMARY = themeColor('--foreground', '#ededed');
const CANVAS_ACCENT = themeColor('--info', '#58a6ff');

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
          style: { stroke: CANVAS_PRIMARY, strokeWidth: 1.5 },
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
    <div className="rounded-xl border border-[var(--border)] overflow-hidden bg-[var(--text)]">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border)] bg-[var(--text)]/70">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="default"
            onClick={addComponent}
            className="flex items-center gap-1.5 bg-[var(--info-wash)] hover:bg-[var(--info-wash)] border border-[var(--info-wash)] text-[var(--info)] text-xs font-semibold transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Component</span>
          </Button>
          <Button variant="outline" size="default"
            onClick={deleteSelected}
            disabled={selectedIds.length === 0}
            className="flex items-center gap-1.5 bg-[var(--red-wash)] hover:bg-[var(--red-wash)] border border-[var(--red-wash)] text-[var(--red)] text-xs font-semibold transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Delete</span>
          </Button>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-[var(--text-2)] hidden sm:block">
            Drag nodes to reposition • Connect screens to components
          </span>
          <Button variant="outline" size="default"
            onClick={save}
            className="flex items-center gap-1.5 bg-[var(--green-wash)] hover:bg-[var(--green-wash)] border border-[var(--green-wash)] text-[var(--green)] text-xs font-bold transition-colors"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Save Layout</span>
          </Button>
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
          {/* These are SVG attributes rather than class names, so they cannot
              read a CSS variable. The two node colours come from the theme's
              text and info tokens, resolved against the canvas element; the
              dot grid uses the surface token so it stays visible on the dark
              canvas without being a second hardcoded value. */}
          <Background variant={BackgroundVariant.Dots} gap={18} size={1} color={CANVAS_SURFACE} />
          <MiniMap
            pannable
            zoomable
            className="!bg-[var(--text)]/80"
            nodeColor={(n) => (n.type === 'screen' ? CANVAS_PRIMARY : CANVAS_ACCENT)}
          />
          <Controls className="!bg-[var(--text)] !border-[var(--border)]" />
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