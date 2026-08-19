import { Badge, Panel, cx } from "@/components/ui";
import { categoryLabel } from "@/lib/format";
import type { Issue, Severity } from "@/types";

const ORDER: Record<Severity, number> = { critical: 0, warning: 1, info: 2 };

export function IssueList({
  issues,
  emptyMessage = "Nothing to report. The network is behaving.",
  compact,
  onSelectDevice,
}: {
  issues: Issue[];
  emptyMessage?: string;
  compact?: boolean;
  onSelectDevice?: (deviceId: string) => void;
}) {
  const sorted = [...issues].sort((a, b) => ORDER[a.severity] - ORDER[b.severity]);
  if (!sorted.length) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-ok/25 bg-ok/10 px-3 py-2.5 text-sm text-ok">
        <span className="text-base leading-none">✓</span>
        {emptyMessage}
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {sorted.map((issue, index) => (
        <IssueRow
          key={`${issue.code}-${index}`}
          issue={issue}
          compact={compact}
          onSelectDevice={onSelectDevice}
        />
      ))}
    </ul>
  );
}

function IssueRow({
  issue,
  compact,
  onSelectDevice,
}: {
  issue: Issue;
  compact?: boolean;
  onSelectDevice?: (deviceId: string) => void;
}) {
  const accent = {
    critical: "border-l-bad",
    warning: "border-l-warn",
    info: "border-l-unifi-bright",
  }[issue.severity];

  return (
    <li className={cx("rounded-md border border-ink-800 border-l-2 bg-ink-850/60 p-3", accent)}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={issue.severity}>{issue.severity}</Badge>
        <span className="text-sm font-medium text-ink-100">{issue.title}</span>
        <Badge className="ml-auto">{categoryLabel(issue.category)}</Badge>
      </div>
      {!compact && (
        <>
          <p className="mt-1.5 text-xs leading-relaxed text-ink-400">{issue.detail}</p>
          {issue.recommendation && (
            <p className="mt-1.5 text-xs leading-relaxed text-ink-300">
              <span className="font-medium text-ink-200">Fix: </span>
              {issue.recommendation}
            </p>
          )}
          {issue.subjects.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {issue.subjects.map((subject) => (
                <button
                  key={`${subject.kind}-${subject.id}`}
                  type="button"
                  disabled={subject.kind !== "device" || !onSelectDevice}
                  onClick={() => onSelectDevice?.(subject.id)}
                  className={cx(
                    "rounded border border-ink-700 bg-ink-900 px-1.5 py-0.5 text-[11px] text-ink-400",
                    subject.kind === "device" && onSelectDevice && "hover:border-unifi hover:text-unifi-bright",
                  )}
                >
                  {subject.label}
                </button>
              ))}
            </div>
          )}
          <code className="mt-2 block font-mono text-[10px] text-ink-600">{issue.code}</code>
        </>
      )}
    </li>
  );
}

export function IssuePanel({
  issues,
  title = "Alerts",
  onSelectDevice,
}: {
  issues: Issue[];
  title?: string;
  onSelectDevice?: (deviceId: string) => void;
}) {
  return (
    <Panel title={title} subtitle={`${issues.length} open`} className="min-h-0">
      <div className="max-h-[420px] overflow-y-auto pr-1">
        <IssueList issues={issues} onSelectDevice={onSelectDevice} />
      </div>
    </Panel>
  );
}
