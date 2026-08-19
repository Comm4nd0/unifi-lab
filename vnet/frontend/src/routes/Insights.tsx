import { useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";

import { useSimulation } from "@/api/client";
import { IssueList } from "@/components/IssueList";
import { Panel, StatTile, cx } from "@/components/ui";
import { categoryLabel, titleCase } from "@/lib/format";
import { useUi } from "@/store";
import type { Severity } from "@/types";

const CATEGORIES = ["all", "stp", "power", "capacity", "topology", "config"] as const;

export function InsightsPage() {
  const navigate = useNavigate();
  const { siteId, selectDevice } = useUi();
  const { data: sim } = useSimulation(siteId);
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("all");

  const issues = useMemo(() => {
    return (sim?.issues ?? []).filter(
      (issue) =>
        (severity === "all" || issue.severity === severity) &&
        (category === "all" || issue.category === category),
    );
  }, [sim?.issues, severity, category]);

  if (!sim) return <div className="p-6 text-sm text-ink-500">Loading insights…</div>;

  const counts = sim.health.counts;

  return (
    <div className="space-y-4 p-5">
      <div className="grid gap-3 sm:grid-cols-4">
        <StatTile
          label="Health score"
          value={sim.health.score}
          unit="/ 100"
          tone={sim.health.status === "ok" ? "ok" : sim.health.status === "warning" ? "warn" : "bad"}
        />
        <StatTile label="Critical" value={counts.critical} tone={counts.critical ? "bad" : "ok"} />
        <StatTile label="Warnings" value={counts.warning} tone={counts.warning ? "warn" : "ok"} />
        <StatTile
          label="STP convergence"
          value={sim.stp.convergence_estimate_s}
          unit="s"
          hint={`${sim.stp.mode.toUpperCase()} · ${sim.stp.blocked_link_ids.length} blocked link(s)`}
        />
      </div>

      <Panel
        title="Everything the simulator noticed"
        subtitle="Ranked by severity, with the fix it would suggest"
        action={
          <div className="flex flex-wrap gap-1">
            {(["all", "critical", "warning", "info"] as const).map((value) => (
              <Chip
                key={value}
                active={severity === value}
                onClick={() => setSeverity(value)}
                label={titleCase(value)}
              />
            ))}
          </div>
        }
      >
        <div className="mb-3 flex flex-wrap gap-1">
          {CATEGORIES.map((value) => (
            <Chip
              key={value}
              active={category === value}
              onClick={() => setCategory(value)}
              label={value === "stp" ? "Spanning tree" : categoryLabel(value)}
            />
          ))}
        </div>
        <IssueList
          issues={issues}
          emptyMessage={
            sim.issues.length
              ? "Nothing matches these filters."
              : "Nothing to report. The network is behaving."
          }
          onSelectDevice={(deviceId) => {
            selectDevice(deviceId);
            navigate({ to: "/devices" });
          }}
        />
      </Panel>
    </div>
  );
}

function Chip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cx(
        "rounded-md border px-2 py-1 text-xs transition",
        active
          ? "border-unifi bg-unifi/15 text-unifi-bright"
          : "border-ink-700 text-ink-400 hover:text-ink-200",
      )}
    >
      {label}
    </button>
  );
}
