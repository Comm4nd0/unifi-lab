import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { endpoints, type HealthCheckStep } from "../api/client";
import { Button } from "./ui";

type DisplayStatus = "pending" | "running" | "ok" | "failed" | "skipped";

type DisplayStep = {
  name: string;
  label: string;
  status: DisplayStatus;
  detail?: string;
  elapsed_ms?: number;
};

const STEP_ORDER: { name: string; label: string }[] = [
  { name: "parse_url", label: "Parse inform URL" },
  { name: "tcp_connect", label: "Network reachable" },
  { name: "api_login", label: "Authenticate API credentials" },
];

function initialSteps(): DisplayStep[] {
  return STEP_ORDER.map((s) => ({ ...s, status: "pending" }));
}

function StatusIcon({ status }: { status: DisplayStatus }) {
  if (status === "ok")
    return <span className="text-emerald-400 font-mono text-sm">✓</span>;
  if (status === "failed")
    return <span className="text-rose-400 font-mono text-sm">✕</span>;
  if (status === "skipped")
    return <span className="text-slate-600 font-mono text-sm">—</span>;
  if (status === "running")
    return (
      <span
        className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent"
        aria-label="running"
      />
    );
  // pending
  return (
    <span className="inline-block h-3 w-3 rounded-full border border-slate-700" aria-label="pending" />
  );
}

export function HealthCheckModal({
  controllerId,
  open,
  onClose,
}: {
  controllerId: string;
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [steps, setSteps] = useState<DisplayStep[]>(initialSteps);
  const [overallHealth, setOverallHealth] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const check = useMutation({
    mutationFn: () => endpoints.controllers.healthCheck(controllerId),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["controllers"] });
      qc.invalidateQueries({ queryKey: ["controllers", controllerId] });
      // Stagger the step reveal: the request returned all at once but
      // we want the UI to feel like each stage completes in sequence.
      animateSteps(result.steps);
      setOverallHealth(result.health);
    },
    onError: (err) => {
      setErrorMsg(err instanceof Error ? err.message : String(err));
    },
  });

  const animateSteps = (final: HealthCheckStep[]) => {
    // Show each step as "running" then settle into its final status,
    // ~350ms apart. Gives the modal some life without faking data.
    const PER_STEP_DELAY = 350;
    final.forEach((s, i) => {
      window.setTimeout(() => {
        setSteps((prev) => {
          const next = prev.slice();
          next[i] = {
            ...next[i],
            status: "running",
          };
          return next;
        });
      }, i * PER_STEP_DELAY);
      window.setTimeout(
        () => {
          setSteps((prev) => {
            const next = prev.slice();
            next[i] = {
              name: s.name,
              label: s.label ?? next[i]?.label ?? s.name,
              status: (s.status as DisplayStatus) ?? "pending",
              detail: s.detail,
              elapsed_ms: s.elapsed_ms,
            };
            return next;
          });
        },
        i * PER_STEP_DELAY + PER_STEP_DELAY - 80,
      );
    });
  };

  // Reset + fire on open
  useEffect(() => {
    if (!open) return;
    setSteps(initialSteps());
    setOverallHealth(null);
    setErrorMsg(null);
    check.mutate();
    // Don't retrigger on mutation identity changes.

  }, [open, controllerId]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const isDone = !check.isPending && (overallHealth !== null || errorMsg !== null);
  const failedStep = steps.find((s) => s.status === "failed");

  const verdict = errorMsg
    ? { tone: "bad" as const, title: "Check failed to run", body: errorMsg }
    : overallHealth === "ok"
      ? {
          tone: "good" as const,
          title: "Controller is healthy",
          body: "All three stages passed — auto-adopt against this controller should succeed.",
        }
      : overallHealth === "auth-failed"
        ? {
            tone: "bad" as const,
            title: "Credentials rejected",
            body:
              "Network is reachable but the controller refused the supplied username/password. Update the credentials via the Rotate secrets action and re-run the check.",
          }
        : overallHealth === "unreachable"
          ? {
              tone: "bad" as const,
              title: "Controller unreachable",
              body:
                "Could not complete the check. See the failing step above for the specific error. Typical causes: wrong inform URL, firewall, VPN down, or TLS mismatch (try toggling Verify TLS).",
            }
          : overallHealth === "unknown"
            ? {
                tone: "bad" as const,
                title: "Malformed configuration",
                body: "The inform URL couldn't be parsed. Edit the controller to fix it.",
              }
            : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 pt-[10vh]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-lg border border-slate-700 bg-slate-950 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-slate-800 px-4 py-3">
          <h2 className="text-sm font-medium uppercase tracking-wide text-slate-300">
            Controller health check
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Probes three stages in sequence. Each step runs on the server and reports back here.
          </p>
        </div>

        <ul className="divide-y divide-slate-800">
          {steps.map((s) => {
            const tone =
              s.status === "ok"
                ? "text-emerald-200"
                : s.status === "failed"
                  ? "text-rose-200"
                  : s.status === "skipped"
                    ? "text-slate-600"
                    : s.status === "running"
                      ? "text-indigo-200"
                      : "text-slate-400";
            return (
              <li key={s.name} className="flex items-start gap-3 px-4 py-3">
                <div className="mt-0.5 flex h-4 w-4 items-center justify-center">
                  <StatusIcon status={s.status} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className={`text-sm ${tone}`}>{s.label}</p>
                  {s.detail && (
                    <p className="mt-0.5 font-mono text-[11px] text-slate-500 break-words">
                      {s.detail}
                      {s.elapsed_ms !== undefined && (
                        <span className="ml-2 text-slate-600">{s.elapsed_ms}ms</span>
                      )}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ul>

        {verdict && (
          <div
            className={
              "border-t border-slate-800 px-4 py-3 text-sm " +
              (verdict.tone === "good"
                ? "bg-emerald-900/20 text-emerald-200"
                : "bg-rose-900/20 text-rose-200")
            }
          >
            <p className="font-medium">{verdict.title}</p>
            <p className="mt-1 text-xs text-slate-400">{verdict.body}</p>
            {failedStep && verdict.tone === "bad" && failedStep.detail && (
              <p className="mt-2 font-mono text-[11px] text-slate-500">
                {failedStep.label}: {failedStep.detail}
              </p>
            )}
          </div>
        )}

        <div className="flex items-center justify-between border-t border-slate-800 px-4 py-3">
          <span className="text-xs text-slate-500">
            {!isDone ? "Running…" : "Done"}
          </span>
          <div className="flex gap-2">
            {isDone && (
              <Button size="sm" variant="secondary" onClick={() => check.mutate()}>
                Re-run
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
