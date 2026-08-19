import { Link } from "@tanstack/react-router";

import { useSimulation } from "@/api/client";
import { AreaChart } from "@/components/Chart";
import { IssueList } from "@/components/IssueList";
import { LINE_ICONS } from "@/components/icons";
import { Badge, Meter, Panel, StatTile, StatusDot, Table, Tr, cx } from "@/components/ui";
import { loadTone, mbps, percent, speed, watts } from "@/lib/format";
import { uplinkLabel } from "@/lib/topology";
import { useUi } from "@/store";

export function DashboardPage() {
  const { siteId, selectDevice } = useUi();
  const { data: sim } = useSimulation(siteId);

  if (!sim) return <div className="p-6 text-sm text-ink-500">Loading site…</div>;

  const { health, traffic } = sim;
  const online = sim.devices.filter((device) => device.status === "online").length;
  const wirelessClients = sim.clients.filter((client) => client.kind === "wireless").length;
  const poe = sim.devices.reduce(
    (totals, device) => ({
      used: totals.used + device.poe_used_w,
      budget: totals.budget + device.poe_budget_w,
    }),
    { used: 0, budget: 0 },
  );

  return (
    <div className="space-y-4 p-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Network health"
          value={health.score}
          unit="/ 100"
          tone={health.status === "ok" ? "ok" : health.status === "warning" ? "warn" : "bad"}
          hint={
            health.counts.critical
              ? `${health.counts.critical} critical, ${health.counts.warning} warnings`
              : health.counts.warning
                ? `${health.counts.warning} warnings`
                : "No open problems"
          }
        />
        <StatTile
          label="Devices"
          value={online}
          unit={`/ ${health.device_count}`}
          tone={online === health.device_count ? "ok" : "warn"}
          hint={`${sim.links.filter((l) => l.state === "forwarding").length} of ${health.link_count} links forwarding`}
        />
        <StatTile
          label="Clients"
          value={health.client_count}
          hint={`${wirelessClients} wireless · ${health.client_count - wirelessClients} wired`}
        />
        <StatTile
          label="PoE load"
          value={poe.budget ? percent(poe.used / poe.budget) : "—"}
          hint={poe.budget ? `${watts(poe.used)} of ${watts(poe.budget)} available` : "No PoE switches"}
          tone={poe.budget && poe.used / poe.budget > 0.9 ? "bad" : "default"}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Panel
          title="Internet throughput"
          subtitle={`${mbps(traffic.wan.download_capacity_mbps)} down · ${mbps(
            traffic.wan.upload_capacity_mbps,
          )} up`}
          className="xl:col-span-2"
        >
          <AreaChart
            height={180}
            series={[
              {
                name: "Download",
                color: "#1f7aff",
                values: traffic.history.map((point) => point.download_mbps),
              },
              {
                name: "Upload",
                color: "#2fb87a",
                values: traffic.history.map((point) => point.upload_mbps),
              },
            ]}
          />
          <div className="mt-3 grid grid-cols-2 gap-3">
            <WanBar
              label="Download"
              value={traffic.wan.download_mbps}
              capacity={traffic.wan.download_capacity_mbps}
              utilisation={traffic.wan.download_utilisation}
            />
            <WanBar
              label="Upload"
              value={traffic.wan.upload_mbps}
              capacity={traffic.wan.upload_capacity_mbps}
              utilisation={traffic.wan.upload_utilisation}
            />
          </div>
        </Panel>

        <Panel
          title="Alerts"
          subtitle={`${sim.issues.length} open`}
          action={
            <Link to="/insights" className="text-xs text-unifi-bright hover:underline">
              View all
            </Link>
          }
          bodyClassName="p-4 max-h-[430px] overflow-y-auto"
        >
          <IssueList
            issues={sim.issues.slice(0, 6)}
            compact
            emptyMessage="No problems detected."
          />
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Devices" bodyClassName="p-0">
          <Table>
            <thead>
              <tr>
                <th className="th">Device</th>
                <th className="th">Uplink</th>
                <th className="th text-right">Throughput</th>
                <th className="th text-right">Clients</th>
              </tr>
            </thead>
            <tbody>
              {sim.devices.map((device) => {
                const Icon = LINE_ICONS[device.line] ?? LINE_ICONS.other;
                const uplink = uplinkLabel(sim, device);
                return (
                  <Tr key={device.id} onClick={() => selectDevice(device.id)}>
                    <td className="td">
                      <Link to="/devices" className="flex items-center gap-2">
                        <Icon size={15} className="text-ink-400" />
                        <StatusDot status={device.status} />
                        <span className="font-medium text-ink-100">{device.name}</span>
                        <span className="text-xs text-ink-500">{device.short}</span>
                        {device.stp?.is_root && <Badge tone="info">root</Badge>}
                      </Link>
                    </td>
                    <td className="td text-ink-400">{uplink}</td>
                    <td className="td text-right tabular-nums">{mbps(device.throughput_mbps)}</td>
                    <td className="td text-right tabular-nums text-ink-400">
                      {device.client_count}
                    </td>
                  </Tr>
                );
              })}
            </tbody>
          </Table>
        </Panel>

        <Panel title="Busiest links" bodyClassName="p-0">
          <Table>
            <thead>
              <tr>
                <th className="th">Link</th>
                <th className="th">State</th>
                <th className="th w-40">Utilisation</th>
              </tr>
            </thead>
            <tbody>
              {[...sim.links]
                .sort((a, b) => b.utilisation - a.utilisation)
                .slice(0, 8)
                .map((link) => (
                  <Tr key={link.id}>
                    <td className="td">
                      <div className="text-ink-100">{link.a_label}</div>
                      <div className="text-xs text-ink-500">→ {link.b_label}</div>
                    </td>
                    <td className="td">
                      <Badge
                        tone={
                          link.state === "forwarding"
                            ? "ok"
                            : link.state === "blocked"
                              ? "warn"
                              : "neutral"
                        }
                      >
                        {link.state}
                      </Badge>
                      <div className="mt-1 text-[11px] text-ink-500">{speed(link.speed_mbps)}</div>
                    </td>
                    <td className="td">
                      <div className={cx("mb-1 text-xs tabular-nums", link.storm && "text-bad")}>
                        {link.storm ? "broadcast storm" : percent(link.utilisation)}
                      </div>
                      <Meter value={link.utilisation} tone={loadTone(link.utilisation)} />
                    </td>
                  </Tr>
                ))}
              {!sim.links.length && (
                <tr>
                  <td className="td text-ink-500" colSpan={3}>
                    Nothing is patched together yet.
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
        </Panel>
      </div>
    </div>
  );
}

function WanBar({
  label,
  value,
  capacity,
  utilisation,
}: {
  label: string;
  value: number;
  capacity: number;
  utilisation: number;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-ink-400">{label}</span>
        <span className="tabular-nums text-ink-300">
          {mbps(value)} <span className="text-ink-500">of {mbps(capacity)}</span>
        </span>
      </div>
      <Meter className="mt-1.5" value={utilisation} tone={loadTone(utilisation)} />
    </div>
  );
}
