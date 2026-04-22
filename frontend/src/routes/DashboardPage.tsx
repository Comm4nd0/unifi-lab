import { useQuery } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { Card, PageHeader, StateChip } from "../components/ui";

export function DashboardPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: endpoints.health, refetchInterval: 15_000 });
  const controllers = useQuery({ queryKey: ["controllers"], queryFn: endpoints.controllers.list });
  const devices = useQuery({ queryKey: ["devices"], queryFn: endpoints.devices.list });

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle="Phase 0 — scaffold online, protocol codec stubbed awaiting pcaps."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide">System</h3>
          {health.isLoading && <p className="mt-3 text-sm text-slate-500">Checking…</p>}
          {health.data && (
            <dl className="mt-3 grid grid-cols-2 gap-y-1.5 text-sm">
              <dt className="text-slate-500">Status</dt>
              <dd>
                <StateChip state={health.data.status} />
              </dd>
              <dt className="text-slate-500">Database</dt>
              <dd>
                <StateChip state={health.data.db} />
              </dd>
              <dt className="text-slate-500">Redis</dt>
              <dd>
                <StateChip state={health.data.redis} />
              </dd>
              <dt className="text-slate-500">Version</dt>
              <dd className="font-mono">{health.data.version}</dd>
            </dl>
          )}
        </Card>

        <Card>
          <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide">Controllers</h3>
          {controllers.isLoading && <p className="mt-3 text-sm text-slate-500">Loading…</p>}
          {controllers.data && (
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-3xl font-semibold">{controllers.data.count}</span>
              <span className="text-sm text-slate-500">total</span>
            </div>
          )}
        </Card>

        <Card>
          <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide">Devices</h3>
          {devices.isLoading && <p className="mt-3 text-sm text-slate-500">Loading…</p>}
          {devices.data && (
            <div className="mt-3 flex items-baseline gap-2">
              <span className="text-3xl font-semibold">{devices.data.count}</span>
              <span className="text-sm text-slate-500">virtual</span>
            </div>
          )}
        </Card>
      </div>

      <section className="mt-8">
        <Card>
          <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wide">Phase 0 note</h3>
          <p className="mt-3 text-sm text-slate-300">
            The inform protocol codec (TNBU + AES-CBC/GCM) is stubbed with{" "}
            <span className="font-mono text-slate-200">NotImplementedError</span>. Virtual devices can
            be created via the UI and the API, but they will not actually contact a controller until
            real pcaps land in{" "}
            <span className="font-mono text-slate-200">backend/tests/fixtures/pcaps/</span>.
          </p>
          <p className="mt-3 text-sm text-slate-400">
            See{" "}
            <a className="text-indigo-400 underline" href="/api/docs/" target="_blank" rel="noreferrer">
              /api/docs/
            </a>{" "}
            for the full API surface.
          </p>
        </Card>
      </section>
    </>
  );
}
