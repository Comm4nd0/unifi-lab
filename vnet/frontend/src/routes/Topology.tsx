import {
  Background,
  ConnectionMode,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { del, post, useSimulation, useSiteMutation } from "@/api/client";
import { AddDeviceDialog } from "@/components/AddDeviceDialog";
import { DeviceDetail, usePortIdMap } from "@/components/DeviceDetail";
import { LinkDialog } from "@/components/LinkDialog";
import { DeviceNode, InternetNode } from "@/components/TopologyNodes";
import { PlusIcon } from "@/components/icons";
import { Badge, Button, EmptyState, Meter, cx, useToast } from "@/components/ui";
import { loadTone, mbps, percent, speed, titleCase } from "@/lib/format";
import { useUi } from "@/store";
import type { LinkRow, SimLink, Simulation } from "@/types";

const NODE_TYPES = { device: DeviceNode, internet: InternetNode };

export function TopologyPage() {
  return (
    <ReactFlowProvider>
      <TopologyCanvas />
    </ReactFlowProvider>
  );
}

function TopologyCanvas() {
  const toast = useToast();
  const { siteId, selectedDeviceId, selectedLinkId, selectDevice, selectLink } = useUi();
  const { data: sim } = useSimulation(siteId);
  const portIds = usePortIdMap(siteId);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges] = useEdgesState<Edge>([]);
  const [adding, setAdding] = useState(false);
  const [patching, setPatching] = useState(false);
  const dragging = useRef<string | null>(null);
  const fitted = useRef(false);
  const { fitView } = useReactFlow();

  const move = useSiteMutation(siteId, (args: { id: string; x: number; y: number }) =>
    post(`/devices/${args.id}/position/`, { x: args.x, y: args.y }),
  );
  const connect = useSiteMutation(siteId, (args: { a: number; b: number; cable: string }) =>
    post<LinkRow>("/links/", { site: siteId, a_port: args.a, b_port: args.b, cable: args.cable }),
  );
  const unplug = useSiteMutation(siteId, (id: string) => del(`/links/${id}/`));

  /* Rebuild the graph whenever the simulation changes, but never yank a node
     out from under the pointer while it is being dragged. */
  useEffect(() => {
    if (!sim) return;
    const gateway = sim.devices.find((device) => device.line === "gateway");
    const next: Node[] = sim.devices.map((device) => ({
      id: device.id,
      type: "device",
      position: { x: device.x, y: device.y },
      data: { device, isRoot: sim.stp.root_device_ids.includes(device.id) },
      selected: device.id === selectedDeviceId,
    }));
    if (gateway) {
      next.unshift({
        id: "internet",
        type: "internet",
        position: { x: gateway.x + 40, y: gateway.y - 150 },
        data: {},
        draggable: false,
        selectable: false,
      });
    }
    setNodes((current) => {
      const byId = new Map(current.map((node) => [node.id, node]));
      return next.map((node) =>
        node.id === dragging.current && byId.has(node.id)
          ? { ...node, position: byId.get(node.id)!.position }
          : node,
      );
    });
    setEdges(buildEdges(sim, selectedLinkId));
    if (!fitted.current && next.length) {
      fitted.current = true;
      // Nodes are measured on the next frame, so fit once they have a size.
      requestAnimationFrame(() => fitView({ padding: 0.18, duration: 300 }));
    }
  }, [sim, selectedDeviceId, selectedLinkId, setNodes, setEdges, fitView]);

  const handleNodesChange = useCallback(
    (changes: NodeChange<Node>[]) => {
      for (const change of changes) {
        if (change.type === "position") {
          dragging.current = change.dragging ? change.id : null;
        }
      }
      onNodesChange(changes);
    },
    [onNodesChange],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const a = connection.sourceHandle && portIds.get(connection.sourceHandle);
      const b = connection.targetHandle && portIds.get(connection.targetHandle);
      if (!a || !b) return;
      const aPort = findPort(sim, connection.sourceHandle!);
      const cable = aPort && aPort.media !== "rj45" ? "dac" : "cat6";
      connect
        .mutateAsync({ a, b, cable })
        .then(() => toast("Cable patched."))
        .catch((error: Error) => toast(error.message, "bad"));
    },
    [portIds, sim, connect, toast],
  );

  const isValidConnection = useCallback(
    (connection: Connection | Edge) => {
      const source = "sourceHandle" in connection ? connection.sourceHandle : null;
      const target = "targetHandle" in connection ? connection.targetHandle : null;
      if (!source || !target || source === target || !sim) return false;
      const a = findPort(sim, source);
      const b = findPort(sim, target);
      if (!a || !b) return false;
      if (a.link_id || b.link_id) return false;
      const family = (media: string) => (media === "rj45" ? "copper" : "fibre");
      return family(a.media) === family(b.media);
    },
    [sim],
  );

  const selectedLink = useMemo(
    () => sim?.links.find((link) => link.id === selectedLinkId) ?? null,
    [sim, selectedLinkId],
  );
  const selectedDevice = sim?.devices.find((device) => device.id === selectedDeviceId) ?? null;

  if (!sim) return <div className="p-6 text-sm text-ink-500">Loading topology…</div>;

  return (
    <div className="flex h-full min-h-0">
      <div className="relative min-w-0 flex-1">
        {sim.devices.length === 0 ? (
          <EmptyState
            title="Nothing here yet"
            detail="Add a gateway, then a switch, then drag a cable from one port to another."
            action={
              <Button variant="primary" onClick={() => setAdding(true)}>
                <PlusIcon size={14} /> Add a device
              </Button>
            }
          />
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={NODE_TYPES}
            onNodesChange={handleNodesChange}
            onConnect={onConnect}
            isValidConnection={isValidConnection}
            connectionMode={ConnectionMode.Loose}
            connectionRadius={18}
            onNodeDragStop={(_event, node) => {
              dragging.current = null;
              if (node.id !== "internet") {
                move.mutate({ id: node.id, x: Math.round(node.position.x), y: Math.round(node.position.y) });
              }
            }}
            onNodeClick={(_event, node) => node.id !== "internet" && selectDevice(node.id)}
            onEdgeClick={(_event, edge) => selectLink(edge.id)}
            onPaneClick={() => {
              selectDevice(null);
              selectLink(null);
            }}
            fitView
            minZoom={0.2}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
            className="bg-ink-950"
          >
            <Background color="#252a35" gap={22} size={1.5} />
            <Controls className="!border-ink-700 !bg-ink-900 [&>button]:!border-ink-700 [&>button]:!bg-ink-800 [&>button]:!fill-ink-300 [&>button:hover]:!bg-ink-700" />
            <MiniMap
              pannable
              zoomable
              className="!bg-ink-900 !border !border-ink-700"
              maskColor="rgba(11,13,16,0.75)"
              nodeColor={(node) =>
                node.id === "internet" ? "#4a5263" : nodeColour(sim, node.id)
              }
            />
          </ReactFlow>
        )}

        <div className="pointer-events-none absolute left-4 top-4 z-10 flex flex-wrap items-center gap-2">
          <div className="pointer-events-auto flex gap-2">
            <Button size="sm" variant="primary" onClick={() => setAdding(true)}>
              <PlusIcon size={14} /> Add device
            </Button>
            <Button size="sm" onClick={() => setPatching(true)}>
              Patch cable
            </Button>
          </div>
          <Legend sim={sim} />
        </div>
      </div>

      {(selectedDevice || selectedLink) && (
        <aside className="w-[380px] shrink-0 overflow-hidden border-l border-ink-800 bg-ink-900">
          {selectedDevice ? (
            <DeviceDetail
              device={selectedDevice}
              simulation={sim}
              onClose={() => selectDevice(null)}
            />
          ) : selectedLink ? (
            <LinkInspector
              link={selectedLink}
              onClose={() => selectLink(null)}
              onUnplug={() =>
                unplug
                  .mutateAsync(selectedLink.id)
                  .then(() => {
                    selectLink(null);
                    toast("Cable removed.");
                  })
                  .catch((error: Error) => toast(error.message, "bad"))
              }
            />
          ) : null}
        </aside>
      )}

      <AddDeviceDialog open={adding} onClose={() => setAdding(false)} siteId={siteId} />
      <LinkDialog open={patching} onClose={() => setPatching(false)} siteId={siteId} />
    </div>
  );
}

/* ------------------------------------------------------------------ pieces */

function Legend({ sim }: { sim: Simulation }) {
  const blocked = sim.stp.blocked_link_ids.length;
  const loops = sim.stp.loops.length;
  return (
    <div className="pointer-events-auto flex flex-wrap items-center gap-2 rounded-md border border-ink-800 bg-ink-900/90 px-2.5 py-1.5 text-[11px] text-ink-400 backdrop-blur">
      <LegendSwatch colour="#2fb87a" label="Forwarding" />
      <LegendSwatch colour="#f2a900" label="Blocked by STP" dashed />
      <LegendSwatch colour="#f0343f" label="Loop / storm" />
      <LegendSwatch colour="#4a5263" label="Down" dashed />
      <span className="ml-1 border-l border-ink-700 pl-2">
        {sim.stp.mode.toUpperCase()}
        {blocked > 0 && ` · ${blocked} blocked`}
        {loops > 0 && <span className="text-bad"> · {loops} loop(s)</span>}
      </span>
    </div>
  );
}

function LegendSwatch({
  colour,
  label,
  dashed,
}: {
  colour: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <span className="flex items-center gap-1.5">
      <svg width="18" height="6" aria-hidden>
        <line
          x1="0"
          y1="3"
          x2="18"
          y2="3"
          stroke={colour}
          strokeWidth="2.5"
          strokeDasharray={dashed ? "4 3" : undefined}
        />
      </svg>
      {label}
    </span>
  );
}

function LinkInspector({
  link,
  onClose,
  onUnplug,
}: {
  link: SimLink;
  onClose: () => void;
  onUnplug: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <header className="flex items-start justify-between gap-2 border-b border-ink-800 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-ink-100">Cable</h2>
          <p className="text-xs text-ink-400">
            {link.a_label} → {link.b_label}
          </p>
        </div>
        <button onClick={onClose} className="text-ink-500 hover:text-ink-200">
          ✕
        </button>
      </header>
      <div className="space-y-4 p-4">
        <div className="flex flex-wrap gap-2">
          <Badge
            tone={
              link.storm ? "bad" : link.state === "forwarding" ? "ok" : link.state === "blocked" ? "warn" : "neutral"
            }
          >
            {link.storm ? "broadcast storm" : link.state}
          </Badge>
          <Badge>{link.cable}</Badge>
          <Badge>{speed(link.speed_mbps)}</Badge>
        </div>

        <dl className="grid grid-cols-2 gap-y-2 text-xs">
          <div>
            <dt className="text-ink-500">A-end role</dt>
            <dd className="text-ink-200">{titleCase(link.a_stp_role ?? "—")}</dd>
          </div>
          <div>
            <dt className="text-ink-500">B-end role</dt>
            <dd className="text-ink-200">{titleCase(link.b_stp_role ?? "—")}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Load</dt>
            <dd className="text-ink-200 tabular-nums">{mbps(link.load_mbps)}</dd>
          </div>
          <div>
            <dt className="text-ink-500">Utilisation</dt>
            <dd className="text-ink-200 tabular-nums">{percent(link.utilisation)}</dd>
          </div>
        </dl>

        <Meter value={link.utilisation} tone={loadTone(link.utilisation)} />

        {link.state === "blocked" && (
          <p className="rounded border border-warn/30 bg-warn/10 px-2.5 py-2 text-[11px] leading-relaxed text-warn">
            Spanning tree is holding this cable in discarding to keep the network loop-free.
            It will take over automatically if the active path fails.
          </p>
        )}

        <Button variant="danger" className="w-full" onClick={onUnplug}>
          Unplug this cable
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ helpers */

function findPort(sim: Simulation | undefined, portId: string) {
  if (!sim) return null;
  for (const device of sim.devices) {
    const port = device.ports.find((item) => item.id === portId);
    if (port) return port;
  }
  return null;
}

function nodeColour(sim: Simulation, deviceId: string): string {
  const device = sim.devices.find((item) => item.id === deviceId);
  if (!device) return "#4a5263";
  if (device.status === "offline") return "#4a5263";
  if (device.status === "error") return "#f0343f";
  return "#0559c9";
}

function buildEdges(sim: Simulation, selectedLinkId: string | null): Edge[] {
  const edges: Edge[] = sim.links.map((link) => {
    const colour = link.storm
      ? "#f0343f"
      : link.state === "forwarding"
        ? link.utilisation >= 0.9
          ? "#f0343f"
          : link.utilisation >= 0.7
            ? "#f2a900"
            : "#2fb87a"
        : link.state === "blocked"
          ? "#f2a900"
          : "#4a5263";
    return {
      id: link.id,
      source: link.a_device_id,
      target: link.b_device_id,
      sourceHandle: link.a_port_id,
      targetHandle: link.b_port_id,
      animated: link.storm,
      selected: link.id === selectedLinkId,
      label: link.state === "blocked" ? "blocked" : speed(link.speed_mbps),
      labelBgStyle: { fill: "#111318" },
      labelStyle: { fill: "#9aa3b5", fontSize: 10 },
      labelBgPadding: [4, 2] as [number, number],
      labelBgBorderRadius: 3,
      style: {
        stroke: colour,
        strokeWidth: link.state === "forwarding" ? 2 + link.utilisation * 2.5 : 1.6,
        strokeDasharray: link.state === "forwarding" ? undefined : "5 4",
      },
    };
  });

  const gateway = sim.devices.find((device) => device.id === sim.traffic.wan.gateway_id);
  const wanPort = gateway?.ports.find((port) => port.role === "wan" && port.enabled);
  if (gateway && wanPort) {
    const utilisation = sim.traffic.wan.download_utilisation;
    edges.push({
      id: "wan-uplink",
      source: "internet",
      target: gateway.id,
      sourceHandle: "internet",
      targetHandle: wanPort.id,
      label: mbps(sim.traffic.wan.download_mbps),
      labelBgStyle: { fill: "#111318" },
      labelStyle: { fill: "#9aa3b5", fontSize: 10 },
      labelBgPadding: [4, 2] as [number, number],
      labelBgBorderRadius: 3,
      selectable: false,
      style: {
        stroke: utilisation >= 0.9 ? "#f0343f" : "#1f7aff",
        strokeWidth: 2,
        strokeDasharray: "2 3",
      },
    });
  }
  return edges;
}

export const TOPOLOGY_CLASS = cx();
