import { useEffect, useMemo } from "react";
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";

import { profileFor } from "../lib/deviceModels";

type BlueprintDevice = {
  hostname?: string;
  model?: string;
  uplink?: string;
};

type ParsedBlueprint = {
  name?: string;
  site?: {
    devices?: BlueprintDevice[];
  };
};

type Props = {
  parsed: unknown;
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

function InternetNode() {
  return (
    <div className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs shadow">
      <Handle type="source" position={Position.Right} id="out" />
      <p className="font-semibold text-slate-200">Controller / uplink</p>
      <p className="mt-0.5 font-mono text-[10px] text-slate-500">blueprint root</p>
    </div>
  );
}

function BlueprintDeviceNode({ data }: NodeProps) {
  const d = data as { hostname: string; model: string; family: string };
  const color = FAMILY_COLOR[d.family] ?? FAMILY_COLOR.other;
  const glyph = FAMILY_GLYPH[d.family] ?? FAMILY_GLYPH.other;
  return (
    <div
      className="rounded-md border bg-slate-900 px-3 py-2 text-xs shadow"
      style={{ borderColor: color }}
    >
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Right} id="out" />
      <div className="flex items-center gap-2">
        <span className="text-base" style={{ color }}>
          {glyph}
        </span>
        <div>
          <p className="font-medium text-slate-100">{d.hostname}</p>
          <p className="mt-0.5 font-mono text-[10px] text-slate-400">{d.model || "unknown"}</p>
        </div>
      </div>
    </div>
  );
}

const nodeTypes = {
  internet: InternetNode,
  bp: BlueprintDeviceNode,
};

function parseDevices(parsed: unknown): BlueprintDevice[] {
  const bp = parsed as ParsedBlueprint | null | undefined;
  const devs = bp?.site?.devices;
  return Array.isArray(devs) ? devs : [];
}

function buildGraph(devices: BlueprintDevice[]): { nodes: Node[]; edges: Edge[] } {
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
      id: "internet",
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
      const hostname = device.hostname ?? `(unnamed-${col}-${row})`;
      const model = device.model ?? "";
      const family = profileFor(model).family;
      const id = `bp-${hostname}`;
      nodes.push({
        id,
        type: "bp",
        position: { x: COL_WIDTH * col, y: ROW_HEIGHT * row },
        data: { hostname, model, family },
        draggable: true,
      });
      const parentHost = device.uplink && byHost[device.uplink] ? device.uplink : null;
      const sourceId = parentHost ? `bp-${parentHost}` : "internet";
      edges.push({
        id: `e-${sourceId}-${id}`,
        source: sourceId,
        target: id,
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

function BlueprintTopologyInner({ parsed }: Props) {
  const devices = useMemo(() => parseDevices(parsed), [parsed]);
  const initial = useMemo(() => buildGraph(devices), [devices]);
  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);

  useEffect(() => {
    setNodes(initial.nodes);
    setEdges(initial.edges);
  }, [initial, setNodes, setEdges]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes}
      defaultEdgeOptions={{ type: "default" }}
      fitView
      proOptions={{ hideAttribution: true }}
      minZoom={0.25}
      colorMode="dark"
    >
      <Background gap={16} color="#1e293b" />
      <Controls showInteractive={false} position="bottom-right" />
    </ReactFlow>
  );
}

export function BlueprintTopology({ parsed }: Props) {
  const devices = parseDevices(parsed);
  if (devices.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-slate-800 bg-slate-900/40 p-10 text-center text-sm text-slate-400">
        No devices declared in <span className="font-mono">site.devices[]</span> — nothing to
        preview yet.
      </p>
    );
  }
  return (
    <div className="h-[24rem] w-full rounded-md border border-slate-800 bg-slate-950">
      <ReactFlowProvider>
        <BlueprintTopologyInner parsed={parsed} />
      </ReactFlowProvider>
    </div>
  );
}
