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

import type { ControllerTarget, Fleet, VirtualDevice } from "../api/client";

type Props = {
  controllers: ControllerTarget[];
  fleets: Fleet[];
  devices: VirtualDevice[];
};

const READY_STATES = new Set(["adopted", "heartbeat"]);

const FLEET_STATE_COLOR: Record<string, string> = {
  active: "#059669",
  ramping: "#d97706",
  paused: "#64748b",
  retiring: "#dc2626",
  error: "#dc2626",
};

const CLUSTER_X = 0;
const CTRL_X = 280;
const FLEET_X = 620;
const ROW_HEIGHT = 110;

function ClusterNode({ data }: NodeProps) {
  const d = data as { controllers: number; fleets: number; devices: number };
  return (
    <div className="rounded-md border border-slate-700 bg-slate-900 px-4 py-3 text-xs shadow">
      <Handle type="source" position={Position.Right} id="out" />
      <p className="font-semibold text-slate-100">Cluster</p>
      <dl className="mt-2 grid grid-cols-[5rem_auto] gap-y-1 font-mono text-[10px] text-slate-400">
        <dt>controllers</dt>
        <dd className="text-slate-200">{d.controllers}</dd>
        <dt>fleets</dt>
        <dd className="text-slate-200">{d.fleets}</dd>
        <dt>devices</dt>
        <dd className="text-slate-200">{d.devices}</dd>
      </dl>
    </div>
  );
}

function ControllerNode({ data }: NodeProps) {
  const d = data as {
    controller: ControllerTarget;
    fleetCount: number;
    deviceCount: number;
  };
  return (
    <Link
      to="/controllers/$id"
      params={{ id: d.controller.id }}
      className="block rounded-md border border-indigo-700 bg-indigo-900/40 px-3 py-2 text-xs shadow hover:bg-indigo-900/60"
    >
      <Handle type="target" position={Position.Left} id="in" />
      <Handle type="source" position={Position.Right} id="out" />
      <p className="font-semibold text-indigo-100">{d.controller.name}</p>
      <p className="mt-0.5 font-mono text-[10px] text-indigo-300">
        {d.controller.kind} · {d.controller.health}
      </p>
      <p className="mt-1 font-mono text-[10px] text-indigo-400">
        {d.fleetCount} fleet{d.fleetCount === 1 ? "" : "s"} · {d.deviceCount} device
        {d.deviceCount === 1 ? "" : "s"}
      </p>
    </Link>
  );
}

function FleetNode({ data }: NodeProps) {
  const d = data as { fleet: Fleet; readyCount: number };
  const color = FLEET_STATE_COLOR[d.fleet.state] ?? FLEET_STATE_COLOR.paused;
  return (
    <Link
      to="/fleets/$id"
      params={{ id: d.fleet.id }}
      className="block rounded-md border bg-slate-900 px-3 py-2 text-xs shadow hover:bg-slate-800"
      style={{ borderColor: color }}
    >
      <Handle type="target" position={Position.Left} id="in" />
      <div className="flex items-center gap-2">
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ backgroundColor: color }}
          aria-hidden
        />
        <p className="font-medium text-slate-100">{d.fleet.name}</p>
      </div>
      <p className="mt-0.5 font-mono text-[10px] text-slate-400">
        {d.fleet.model_code} · {d.fleet.state}
      </p>
      <p className="mt-1 font-mono text-[10px] text-slate-500">
        {d.readyCount}/{d.fleet.device_count} ready
      </p>
    </Link>
  );
}

const nodeTypes = {
  cluster: ClusterNode,
  controller: ControllerNode,
  fleet: FleetNode,
};

function buildGraph(props: Props): { nodes: Node[]; edges: Edge[] } {
  const { controllers, fleets, devices } = props;

  // Rollup: devices per controller (via fleet or direct assignment).
  const fleetsByCtrl = new Map<string, Fleet[]>();
  for (const f of fleets) {
    const list = fleetsByCtrl.get(f.controller_target) ?? [];
    list.push(f);
    fleetsByCtrl.set(f.controller_target, list);
  }
  const devicesByCtrl = new Map<string, number>();
  for (const d of devices) {
    if (!d.controller_target) continue;
    devicesByCtrl.set(d.controller_target, (devicesByCtrl.get(d.controller_target) ?? 0) + 1);
  }

  const nodes: Node[] = [];
  const edges: Edge[] = [];

  // Total row span is the total number of fleets, since each fleet takes
  // one row. Controllers sit at the vertical midpoint of their fleets.
  const sortedControllers = [...controllers].sort((a, b) => a.name.localeCompare(b.name));
  let fleetRow = 0;
  const rowForController: Record<string, number> = {};
  for (const c of sortedControllers) {
    const owned = fleetsByCtrl.get(c.id) ?? [];
    if (owned.length === 0) {
      rowForController[c.id] = fleetRow;
      fleetRow += 1; // leave a blank row so controllers without fleets don't stack on top of each other
      continue;
    }
    const startRow = fleetRow;
    rowForController[c.id] = startRow + (owned.length - 1) / 2;
    owned.forEach((f) => {
      const readyCount = Object.entries(f.device_states ?? {})
        .filter(([s]) => READY_STATES.has(s))
        .reduce((a, [, n]) => a + n, 0);
      nodes.push({
        id: `fleet-${f.id}`,
        type: "fleet",
        position: { x: FLEET_X, y: fleetRow * ROW_HEIGHT },
        data: { fleet: f, readyCount },
        draggable: true,
      });
      edges.push({
        id: `e-ctrl-${c.id}-fleet-${f.id}`,
        source: `ctrl-${c.id}`,
        target: `fleet-${f.id}`,
        sourceHandle: "out",
        targetHandle: "in",
        animated: f.state === "ramping",
        style: {
          stroke: FLEET_STATE_COLOR[f.state] ?? FLEET_STATE_COLOR.paused,
          strokeWidth: 2,
        },
      });
      fleetRow += 1;
    });
  }

  const tallest = Math.max(1, fleetRow);

  // Cluster root.
  nodes.push({
    id: "cluster",
    type: "cluster",
    position: { x: CLUSTER_X, y: ((tallest - 1) * ROW_HEIGHT) / 2 },
    data: {
      controllers: controllers.length,
      fleets: fleets.length,
      devices: devices.length,
    },
    draggable: true,
  });

  // Controller nodes + cluster→controller edges.
  for (const c of sortedControllers) {
    const row = rowForController[c.id];
    nodes.push({
      id: `ctrl-${c.id}`,
      type: "controller",
      position: { x: CTRL_X, y: row * ROW_HEIGHT },
      data: {
        controller: c,
        fleetCount: (fleetsByCtrl.get(c.id) ?? []).length,
        deviceCount: devicesByCtrl.get(c.id) ?? 0,
      },
      draggable: true,
    });
    edges.push({
      id: `e-cluster-ctrl-${c.id}`,
      source: "cluster",
      target: `ctrl-${c.id}`,
      sourceHandle: "out",
      targetHandle: "in",
      style: { stroke: "#334155", strokeWidth: 1.5 },
    });
  }

  return { nodes, edges };
}

function TopologyInner(props: Props) {
  const initial = useMemo(() => buildGraph(props), [props]);
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

export function ClusterTopology(props: Props) {
  if (props.controllers.length === 0 && props.fleets.length === 0) {
    return (
      <p className="rounded-md border border-dashed border-slate-800 bg-slate-900/40 p-10 text-center text-sm text-slate-400">
        No controllers or fleets yet — the topology appears once you connect a controller and ramp a
        fleet.
      </p>
    );
  }
  return (
    <div className="h-[34rem] w-full rounded-md border border-slate-800 bg-slate-950">
      <ReactFlowProvider>
        <TopologyInner {...props} />
      </ReactFlowProvider>
    </div>
  );
}
