import { FormEvent, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, endpoints } from "../api/client";
import { Button, Card, EmptyState, Input, Label, PageHeader, Select, StateChip } from "../components/ui";

export function ControllersPage() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["controllers"], queryFn: endpoints.controllers.list });
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader
        title="Controllers"
        subtitle="UniFi OS Server targets that virtual devices adopt into."
        actions={<Button onClick={() => setCreating(true)}>Add controller</Button>}
      />

      {creating && (
        <div className="mb-6">
          <CreateControllerForm
            onCancel={() => setCreating(false)}
            onCreated={() => {
              setCreating(false);
              qc.invalidateQueries({ queryKey: ["controllers"] });
            }}
          />
        </div>
      )}

      {list.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {list.error && (
        <p className="text-sm text-red-400">Failed to load controllers: {(list.error as Error).message}</p>
      )}
      {list.data && list.data.results.length === 0 && (
        <EmptyState
          title="No controllers yet"
          hint="Add one to give virtual devices somewhere to adopt into."
        />
      )}
      {list.data && list.data.results.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Name</th>
                <th className="px-4 py-2 text-left font-medium">Kind</th>
                <th className="px-4 py-2 text-left font-medium">Health</th>
                <th className="px-4 py-2 text-left font-medium">Verify TLS</th>
                <th className="px-4 py-2 text-left font-medium">Created</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {list.data.results.map((c) => (
                <tr key={c.id} className="hover:bg-slate-900/40">
                  <td className="px-4 py-3 font-medium">
                    <Link to="/controllers/$id" params={{ id: c.id }} className="hover:text-white">
                      {c.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400">{c.kind}</td>
                  <td className="px-4 py-3">
                    <StateChip state={c.health} />
                  </td>
                  <td className="px-4 py-3 text-slate-400">{c.verify_tls ? "yes" : "no"}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {new Date(c.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to="/controllers/$id"
                      params={{ id: c.id }}
                      className="text-sm text-indigo-400 hover:text-indigo-300"
                    >
                      Detail →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function CreateControllerForm({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"uos-server" | "legacy-network">("uos-server");
  const [informUrl, setInformUrl] = useState("");
  const [apiUrl, setApiUrl] = useState("");
  const [apiUsername, setApiUsername] = useState("");
  const [apiPassword, setApiPassword] = useState("");
  const [verifyTls, setVerifyTls] = useState(false);

  const create = useMutation({
    mutationFn: () =>
      endpoints.controllers.create({
        name,
        kind,
        inform_url: informUrl,
        api_url: apiUrl,
        api_username: apiUsername,
        api_password: apiPassword,
        verify_tls: verifyTls,
      }),
    onSuccess: onCreated,
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };

  return (
    <Card>
      <h2 className="text-lg font-semibold">New controller target</h2>
      <p className="mt-1 text-sm text-slate-400">
        Credentials are stored Fernet-encrypted at rest.
      </p>
      <form className="mt-4 grid gap-4 md:grid-cols-2" onSubmit={onSubmit}>
        <div className="flex flex-col gap-1.5">
          <Label>Name</Label>
          <Input required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Kind</Label>
          <Select value={kind} onChange={(e) => setKind(e.target.value as "uos-server" | "legacy-network")}>
            <option value="uos-server">UniFi OS Server</option>
            <option value="legacy-network">Legacy Network</option>
          </Select>
        </div>
        <div className="flex flex-col gap-1.5 md:col-span-2">
          <Label>Inform URL</Label>
          <Input
            required
            placeholder="https://192.168.1.1:443"
            value={informUrl}
            onChange={(e) => setInformUrl(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5 md:col-span-2">
          <Label>API URL</Label>
          <Input
            required
            placeholder="https://192.168.1.1:443/api"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>API username</Label>
          <Input
            required
            autoComplete="off"
            value={apiUsername}
            onChange={(e) => setApiUsername(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>API password</Label>
          <Input
            required
            type="password"
            autoComplete="new-password"
            value={apiPassword}
            onChange={(e) => setApiPassword(e.target.value)}
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-300 md:col-span-2">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-slate-700 bg-slate-900"
            checked={verifyTls}
            onChange={(e) => setVerifyTls(e.target.checked)}
          />
          Verify TLS certificates
        </label>
        {create.error && (
          <p className="text-sm text-red-400 md:col-span-2">
            {create.error instanceof ApiError ? create.error.message : String(create.error)}
          </p>
        )}
        <div className="flex gap-2 md:col-span-2">
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Create"}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}
