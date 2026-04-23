import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  endpoints,
  type ApiTokenWithPlaintext,
} from "../api/client";
import {
  Button,
  Card,
  EmptyState,
  Input,
  Label,
  PageHeader,
} from "../components/ui";

const SCOPE_OPTIONS: { value: string; label: string; description: string }[] = [
  { value: "read", label: "read", description: "Read-only access to all resources." },
  {
    value: "write",
    label: "write",
    description: "Create + update resources (implies read).",
  },
  {
    value: "fleet:execute",
    label: "fleet:execute",
    description: "Pause / resume / teardown fleets (implies write).",
  },
  {
    value: "firmware:upload",
    label: "firmware:upload",
    description: "Upload new firmware blobs.",
  },
  { value: "admin", label: "admin", description: "Full admin access (use sparingly)." },
];

function humanRelative(iso: string | null): string {
  if (!iso) return "never";
  const delta = Date.now() - new Date(iso).getTime();
  if (delta < 60_000) return "just now";
  if (delta < 3_600_000) return `${Math.round(delta / 60_000)}m ago`;
  if (delta < 86_400_000) return `${Math.round(delta / 3_600_000)}h ago`;
  return `${Math.round(delta / 86_400_000)}d ago`;
}

export function TokensPage() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["tokens"], queryFn: endpoints.tokens.list });
  const [creating, setCreating] = useState(false);
  const [fresh, setFresh] = useState<ApiTokenWithPlaintext | null>(null);
  const [copied, setCopied] = useState(false);

  const create = useMutation({
    mutationFn: (body: { name: string; scopes: string[] }) => endpoints.tokens.create(body),
    onSuccess: (data) => {
      setFresh(data);
      setCreating(false);
      qc.invalidateQueries({ queryKey: ["tokens"] });
    },
  });

  const revoke = useMutation({
    mutationFn: (id: string) => endpoints.tokens.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tokens"] }),
  });

  const copy = async (plaintext: string) => {
    try {
      await navigator.clipboard.writeText(plaintext);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API blocked — user can still select manually.
    }
  };

  return (
    <>
      <PageHeader
        title="API tokens"
        subtitle="Long-lived, scoped tokens for machine-to-machine access. Bearer them in the Authorization header."
        actions={
          !creating && (
            <Button onClick={() => setCreating(true)}>New token</Button>
          )
        }
      />

      {fresh && (
        <Card className="mb-4 border-emerald-700 bg-emerald-900/20">
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="text-sm font-medium uppercase tracking-wide text-emerald-200">
              Copy your new token now
            </h3>
            <button
              type="button"
              onClick={() => setFresh(null)}
              className="text-xs text-emerald-200 hover:text-emerald-100"
            >
              Dismiss
            </button>
          </div>
          <p className="mt-2 text-xs text-emerald-200/80">
            This is the only time the plaintext will be shown. Store it somewhere safe — the
            server never keeps a copy.
          </p>
          <div className="mt-3 flex items-center gap-2">
            <code className="flex-1 break-all rounded bg-slate-950 px-3 py-2 font-mono text-xs text-emerald-100">
              {fresh.token}
            </code>
            <Button size="sm" variant="secondary" onClick={() => copy(fresh.token)}>
              {copied ? "Copied ✓" : "Copy"}
            </Button>
          </div>
          <p className="mt-2 text-[10px] font-mono text-emerald-200/60">
            Scopes: {fresh.scopes.join(", ")}
          </p>
        </Card>
      )}

      {creating && (
        <CreateTokenForm
          onCancel={() => setCreating(false)}
          onSubmit={(name, scopes) => create.mutate({ name, scopes })}
          pending={create.isPending}
          error={
            create.error instanceof ApiError
              ? create.error.message
              : create.error
                ? String(create.error)
                : undefined
          }
        />
      )}

      {list.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {list.data && list.data.results.length === 0 && !creating && !fresh && (
        <EmptyState
          title="No tokens yet"
          hint="Create one to automate UVL from CI. Store the plaintext somewhere safe — the server never shows it again."
        />
      )}
      {list.data && list.data.results.length > 0 && (
        <Card className="p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Name</th>
                <th className="px-4 py-2 text-left font-medium">Scopes</th>
                <th className="px-4 py-2 text-left font-medium">Last used</th>
                <th className="px-4 py-2 text-left font-medium">Created</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {list.data.results.map((t) => (
                <tr key={t.id} className="hover:bg-slate-900/40">
                  <td className="px-4 py-3 font-medium">{t.name}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {t.scopes.map((s) => (
                        <span
                          key={s}
                          className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-300"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {humanRelative(t.last_used_at)}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {new Date(t.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => {
                        if (confirm(`Revoke "${t.name}"? Any client using it will stop working.`))
                          revoke.mutate(t.id);
                      }}
                      disabled={revoke.isPending}
                    >
                      Revoke
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <div className="mt-6 rounded-md border border-slate-800 bg-slate-900/40 p-4 text-xs text-slate-400">
        <p className="font-medium text-slate-300">Using a token</p>
        <pre className="mt-2 overflow-x-auto rounded bg-slate-950 px-3 py-2 font-mono text-[11px] text-slate-200">
          curl -H "Authorization: Bearer &lt;token&gt;" https://your-uvl/api/v1/fleets/
        </pre>
      </div>
    </>
  );
}

function CreateTokenForm({
  onCancel,
  onSubmit,
  pending,
  error,
}: {
  onCancel: () => void;
  onSubmit: (name: string, scopes: string[]) => void;
  pending: boolean;
  error: string | undefined;
}) {
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set(["read"]));

  const toggle = (scope: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(scope)) next.delete(scope);
      else next.add(scope);
      // Always keep at least read selected — the backend defaults to it
      // anyway but the UI should mirror that so the form feels honest.
      if (next.size === 0) next.add("read");
      return next;
    });
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSubmit(name.trim(), Array.from(selected));
  };

  return (
    <Card className="mb-4">
      <h2 className="text-lg font-semibold">New API token</h2>
      <form className="mt-3 grid gap-4" onSubmit={submit}>
        <div>
          <Label>Name</Label>
          <Input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. ci-bot"
          />
        </div>
        <div>
          <Label>Scopes</Label>
          <div className="mt-2 flex flex-col gap-2">
            {SCOPE_OPTIONS.map((s) => (
              <label
                key={s.value}
                className="flex items-start gap-2 text-sm text-slate-300"
              >
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 rounded border-slate-700 bg-slate-900"
                  checked={selected.has(s.value)}
                  onChange={() => toggle(s.value)}
                />
                <div>
                  <span className="font-mono text-xs">{s.label}</span>
                  <span className="ml-2 text-xs text-slate-500">{s.description}</span>
                </div>
              </label>
            ))}
          </div>
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
        <div className="flex gap-2">
          <Button type="submit" disabled={pending || !name.trim()}>
            {pending ? "Creating…" : "Create token"}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}
