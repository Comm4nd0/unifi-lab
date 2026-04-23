import { useEffect, useMemo } from "react";
import { Link } from "@tanstack/react-router";
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

import type { Fleet, VirtualDevice } from "../api/client";
import { profileFor } from "../lib/deviceModels";

type Props = {
  fleet: Fleet;
  devices: VirtualDevice[];
  parsedBlueprint?: {
    site?: {
      devices?: { hostname?: string; uplink?: string }[];
    };
  };
};

const STATE_COLOR: Record<string, string> = {
  adopted: "#059669",
  heartbeat: "#059669",
  pending: "#d97706",
  key_exchange: "#d97706",
  config_apply: "#4f46e5",
  disconnected: "#475569",
  error: "#dc2626",
};

const FAMILY_GLYPH: Record<string, string> = {
  gateway: "⬒",
  switch: "▣",
  ap: "✦",
  other: "○",
};

const COL_WIDTH = 220;
const ROW_HEIGHT = 90;

function ControllerNode({ data }: NodeProps) {
  const d = data as { name: string };
  return (
    <div className="rounded-md border border-indigo-700 bg-indigo-900/40 px-4 py-3 text-xs shadow">
      <Handle type="source" position={Position.Right} id="out" />
      <p className="font-semibold text-indigo-200">{d.name}</p>
      <p className="mt-1 font-mono text-[10px] text-indigo-400">Controller</p>
    </div>
  );
}

function DeviceNode({ data }: NodeProps) {
  const d = data as {
    device: VirtualDevice;
    family: string;
  };
  const color = STATE_COLOR[d.device.state] ?? STATE_COLOR.disconnected;
  const glyph = FAMILY_GLYPH[d.family] ?? FAMILY_GLYPH.other;
  return (
    <Link
      to="/devices/$id"
      params={{ id: d.device.id }}
      className="block rounded-md border bg-slate-900 px-3 py-2 text-xs shadow hover:bg-slate-800"
      style={{ borderColor: color }}
    >
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Right} id="out" />
      <div className="flex items-center gap-2">
        <span className="text-base" style={{ color }}>
          {glyph}
        </span>
        <div>
          <p className="font-medium text-slate-100">
            {d.device.hostname || d.device.mac_address}
          </p>
          <p className="mt-0.5 font-mono text-[10px] text-slate-400">
            {d.device.model_code} · {d.device.state}
          </p>
        </div>
      </div>
    </Link>
  );
}

const nodeTypes = {
  controller: ControllerNode,
  device: DeviceNode,
};

function buildGraph(
  fleet: Fleet,
  devices: VirtualDevice[],
  parsedBlueprint: Props["parsedBlueprint"],
): { nodes: Node[]; edges: Edge[] } {
  const uplinkByHost: Record<string, string> = {};
  const declaredDevices = parsedBlueprint?.site?.devices ?? [];
  for (const dev of declaredDevices) {
    if (dev.hostname && dev.uplink) {
      uplinkByHost[dev.hostname] = dev.uplink;
    }
  }

  const byHost: Record<string, VirtualDevice> = {};
  for (const d of devices) {
    if (d.hostname) byHost[d.hostname] = d;
  }

  const depth = (hostname: string, seen = new Set<string>()): number => {
    if (!hostname || seen.has(hostname)) return 1;
    seen.add(hostname);
    const parent = uplinkByHost[hostname];
    if (!parent) return 1;
    return depth(parent, seen) + 1;
  };

  const controllerId = `ctrl-${fleet.controller_target}`;
  const nodes: Node[] = [
    {
      id: controllerId,
      type: "controller",
      position: { x: 0, y: 0 },
      data: { name: "Controller" },
    },
  ];
  const edges: Edge[] = [];

  const columns: Record<number, VirtualDevice[]> = {};
  for (const d of devices) {
    const col = d.hostname ? depth(d.hostname) : 1;
    (columns[col] = columns[col] ?? []).push(d);
  }

  const columnKeys = Object.keys(columns).map(Number).sort((a, b) => a - b);
  let tallest = 0;
  for (const col of columnKeys) {
    columns[col].forEach((device, row) => {
      const family = profileFor(device.model_code).family;
      nodes.push({
        id: device.id,
        type: "device",
        position: { x: COL_WIDTH * col, y: ROW_HEIGHT * row },
        data: { device, family },
        draggable: true,
      });

      const parentHost =
        device.hostname && uplinkByHost[device.hostname]
          ? uplinkByHost[device.hostname]
          : null;
      const parent = parentHost ? byHost[parentHost] : null;
      const sourceId = parent ? parent.id : controllerId;
      edges.push({
        id: `e-${sourceId}-${device.id}`,
        type: "default",
        source: sourceId,
        target: device.id,
        sourceHandle: "out",
        targetHandle: "in",
        animated: device.state === "heartbeat" || device.state === "adopted",
        style: { stroke: STATE_COLOR[device.state] ?? STATE_COLOR.disconnected, strokeWidth: 2 },
      });
    });
    tallest = Math.max(tallest, columns[col].length);
  }

  if (tallest > 1) {
    nodes[0].position = { x: 0, y: ((tallest - 1) * ROW_HEIGHT) / 2 };
  }
  return { nodes, edges };
}

function TopologyInner({ fleet, devices, parsedBlueprint }: Props) {
  const initial = useMemo(
    () => buildGraph(fleet, devices, parsedBlueprint),
    [fleet, devices, parsedBlueprint],
  );
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

export function TopologyGraph(props: Props) {
  if (props.devices.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-slate-800 bg-slate-900/40 p-10 text-center text-sm text-slate-400">
        No devices in this fleet yet — topology will render once devices materialise.
      </p>
    );
  }

  return (
    <div className="h-[28rem] w-full rounded-md border border-slate-800 bg-slate-950">
      <ReactFlowProvider>
        <TopologyInner {...props} />
      </ReactFlowProvider>
    </div>
  );
}
