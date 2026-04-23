import { useQuery } from "@tanstack/react-query";

import { endpoints } from "../api/client";
import { ClusterTopology } from "../components/ClusterTopology";
import { Card, PageHeader } from "../components/ui";

export function TopologyPage() {
  const controllers = useQuery({
    queryKey: ["controllers"],
    queryFn: endpoints.controllers.list,
    refetchInterval: 15_000,
  });
  const fleets = useQuery({
    queryKey: ["fleets"],
    queryFn: endpoints.fleets.list,
    refetchInterval: 10_000,
  });
  const devices = useQuery({
    queryKey: ["devices"],
    queryFn: endpoints.devices.list,
    refetchInterval: 10_000,
  });

  const loading = controllers.isLoading || fleets.isLoading || devices.isLoading;

  return (
    <>
      <PageHeader
        title="Topology"
        subtitle="Cluster overview — controllers, fleets, and their device counts. Click any node to drill in."
      />

      <Card>
        {loading ? (
          <p className="py-20 text-center text-sm text-slate-500">Loading topology…</p>
        ) : (
          <ClusterTopology
            controllers={controllers.data?.results ?? []}
            fleets={fleets.data?.results ?? []}
            devices={devices.data?.results ?? []}
          />
        )}
        <p className="mt-3 text-xs text-slate-500">
          Animated edges mark fleets that are currently ramping. Per-fleet device-level topology
          lives on each fleet's detail page.
        </p>
      </Card>
    </>
  );
}
