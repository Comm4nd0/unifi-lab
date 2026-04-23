import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  addEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type OnNodesDelete,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";

import {
  addDevice,
  nextHostname,
  removeDevice,
  renameDevice,
  setUplink,
  type BlueprintDevice,
  type BlueprintDoc,
} from "../lib/blueprintDoc";
import { profileFor } from "../lib/deviceModels";

type Props = {
  doc: BlueprintDoc;
  onChange: (next: BlueprintDoc) => void;
};

const FAMILY_GLYPH: Record<string, string> = {
  gateway: "⬒",
  switch: "▣",
  ap: "✦",
  other: "○",
};

const FAMILY_COLOR: Record<string, string> = {
  gateway: "#4f46e5",
  switch: "#0891b2",
  ap: "#059669",
  other: "#64748b",
};

const COL_WIDTH = 220;
const ROW_HEIGHT = 90;
const ROOT_ID = "__root__";

// Pulls a BlueprintDevice out of a ReactFlow node's data when we need it
// outside the renderer. Typed as ``unknown`` so the component stays
// independent of the ReactFlow typing quirks.
function nodeDevice(n: Node): BlueprintDevice | null {
  const data = n.data as { device?: BlueprintDevice };
  return data?.device ?? null;
}

function InternetNode() {
  return (
    <div className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs shadow">
      <Handle type="source" position={Position.Right} id="out" />
      <p className="font-semibold text-slate-200">Controller / uplink</p>
      <p className="mt-0.5 font-mono text-[10px] text-slate-500">blueprint root</p>
    </div>
  );
}

function BlueprintCanvasNode({ data, id }: NodeProps) {
  const d = data as {
    device: BlueprintDevice;
    family: string;
    onRename: (hostname: string, next: string) => boolean;
  };
  const color = FAMILY_COLOR[d.family] ?? FAMILY_COLOR.other;
  const glyph = FAMILY_GLYPH[d.family] ?? FAMILY_GLYPH.other;

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(d.device.hostname);
  const [clash, setClash] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setDraft(d.device.hostname);
  }, [d.device.hostname]);

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  const commit = () => {
    const trimmed = draft.trim();
    if (!trimmed || trimmed === d.device.hostname) {
      setEditing(false);
      setClash(false);
      return;
    }
    const ok = d.onRename(d.device.hostname, trimmed);
    if (!ok) {
      setClash(true);
      return;
    }
    setClash(false);
    setEditing(false);
  };

  return (
    <div
      className="rounded-md border bg-slate-900 px-3 py-2 text-xs shadow"
      style={{ borderColor: clash ? "#dc2626" : color }}
      data-id={id}
    >
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Right} id="out" />
      <div className="flex items-center gap-2">
        <span className="text-base" style={{ color }}>
          {glyph}
        </span>
        <div>
          {editing ? (
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                if (clash) setClash(false);
              }}
              onBlur={commit}
              onKeyDown={(e) => {
                if (e.key === "Enter") commit();
                if (e.key === "Escape") {
                  setDraft(d.device.hostname);
                  setClash(false);
                  setEditing(false);
                }
              }}
              className="w-full rounded border border-slate-700 bg-slate-950 px-1 py-0.5 text-xs text-slate-100 focus:outline-none"
              spellCheck={false}
            />
          ) : (
            <p
              className="font-medium text-slate-100"
              onDoubleClick={() => setEditing(true)}
              title="Double-click to rename"
            >
              {d.device.hostname}
            </p>
          )}
          <p className="mt-0.5 font-mono text-[10px] text-slate-400">
            {d.device.model || "unknown"}
          </p>
        </div>
      </div>
    </div>
  );
}

const nodeTypes = {
  internet: InternetNode,
  bp: BlueprintCanvasNode,
};

function buildGraph(
  doc: BlueprintDoc,
  onRename: (hostname: string, next: string) => boolean,
): { nodes: Node[]; edges: Edge[] } {
  const { devices } = doc;
  const byHost: Record<string, BlueprintDevice> = {};
  for (const d of devices) {
    if (d.hostname) byHost[d.hostname] = d;
  }

  const depth = (hostname: string, seen = new Set<string>()): number => {
    if (!hostname || seen.has(hostname)) return 1;
    seen.add(hostname);
    const dev = byHost[hostname];
    const parent = dev?.uplink;
    if (!parent || !byHost[parent]) return 1;
    return depth(parent, seen) + 1;
  };

  const columns: Record<number, BlueprintDevice[]> = {};
  for (const d of devices) {
    const col = d.hostname ? depth(d.hostname) : 1;
    (columns[col] = columns[col] ?? []).push(d);
  }

  const nodes: Node[] = [
    {
      id: ROOT_ID,
      type: "internet",
      position: { x: 0, y: 0 },
      data: {},
    },
  ];
  const edges: Edge[] = [];

  const columnKeys = Object.keys(columns).map(Number).sort((a, b) => a - b);
  let tallest = 0;
  for (const col of columnKeys) {
    columns[col].forEach((device, row) => {
      const hostname = device.hostname || `(unnamed-${col}-${row})`;
      const family = profileFor(device.model || "").family;
      nodes.push({
        id: hostname,
        type: "bp",
        position: { x: COL_WIDTH * col, y: ROW_HEIGHT * row },
        data: { device, family, onRename },
        draggable: true,
      });
      const parentHost = device.uplink && byHost[device.uplink] ? device.uplink : null;
      const sourceId = parentHost ? parentHost : ROOT_ID;
      edges.push({
        id: `e-${sourceId}-${hostname}`,
        source: sourceId,
        target: hostname,
        sourceHandle: "out",
        targetHandle: "in",
        style: { stroke: FAMILY_COLOR[family] ?? FAMILY_COLOR.other, strokeWidth: 2 },
      });
    });
    tallest = Math.max(tallest, columns[col].length);
  }

  if (tallest > 1) {
    nodes[0].position = { x: 0, y: ((tallest - 1) * ROW_HEIGHT) / 2 };
  }
  return { nodes, edges };
}

function BlueprintCanvasInner({ doc, onChange }: Props) {
  // Ref to the latest doc so callbacks built once don't close over stale state.
  const docRef = useRef(doc);
  useEffect(() => {
    docRef.current = doc;
  }, [doc]);

  const rename = useCallback(
    (oldHostname: string, newHostname: string): boolean => {
      const next = renameDevice(docRef.current, oldHostname, newHostname);
      if (next === null) return false;
      if (next !== docRef.current) onChange(next);
      return true;
    },
    [onChange],
  );

  const initial = useMemo(() => buildGraph(doc, rename), [doc, rename]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);

  useEffect(() => {
    setNodes(initial.nodes);
    setEdges(initial.edges);
  }, [initial, setNodes, setEdges]);

  const { screenToFlowPosition } = useReactFlow();

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const model = e.dataTransfer.getData("application/x-uvl-template");
      const family =
        e.dataTransfer.getData("application/x-uvl-family") ||
        profileFor(model).family;
      if (!model) return;

      const hostname = nextHostname(family, docRef.current.devices);

      // If the drop target is a node element, pre-fill uplink to that node.
      const node = (e.target as HTMLElement | null)?.closest?.(
        ".react-flow__node-bp",
      );
      const parent = node?.getAttribute("data-id") || null;

      const position = screenToFlowPosition({ x: e.clientX, y: e.clientY });

      const next = addDevice(docRef.current, {
        hostname,
        model,
        uplink: parent && parent !== hostname ? parent : null,
      });
      onChange(next);

      // Place the newly created node at the drop coordinates so it doesn't
      // jump to the auto-layout column. A small timeout ensures the effect
      // that syncs ``initial`` has applied first.
      setTimeout(() => {
        setNodes((prev) =>
          prev.map((n) =>
            n.id === hostname ? { ...n, position } : n,
          ),
        );
      }, 0);
    },
    [onChange, screenToFlowPosition, setNodes],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      // connection.source = parent hostname, connection.target = child.
      if (!connection.source || !connection.target) return;
      if (connection.target === ROOT_ID) return;
      const parent = connection.source === ROOT_ID ? null : connection.source;
      const updated = setUplink(docRef.current, connection.target, parent);
      if (updated !== docRef.current) onChange(updated);
      // Still add the edge visually for immediate feedback — the effect
      // will overwrite it from the re-derived graph shortly.
      setEdges((prev) => addEdge({ ...connection, style: { strokeWidth: 2 } }, prev));
    },
    [onChange, setEdges],
  );

  const onNodesDelete: OnNodesDelete = useCallback(
    (deleted) => {
      let next = docRef.current;
      for (const n of deleted) {
        if (n.id === ROOT_ID) continue;
        const device = nodeDevice(n);
        const hostname = device?.hostname ?? n.id;
        next = removeDevice(next, hostname);
      }
      if (next !== docRef.current) onChange(next);
    },
    [onChange],
  );

  return (
    <div className="h-[28rem] w-full" onDragOver={onDragOver} onDrop={onDrop}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodesDelete={onNodesDelete}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={{ type: "default" }}
        fitView
        proOptions={{ hideAttribution: true }}
        minZoom={0.25}
        colorMode="dark"
        deleteKeyCode={["Delete", "Backspace"]}
      >
        <Background gap={16} color="#1e293b" />
        <Controls showInteractive={false} position="bottom-right" />
      </ReactFlow>
    </div>
  );
}

export function BlueprintCanvas(props: Props) {
  return (
    <div className="w-full rounded-md border border-slate-800 bg-slate-950">
      <ReactFlowProvider>
        <BlueprintCanvasInner {...props} />
      </ReactFlowProvider>
    </div>
  );
}
