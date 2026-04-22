import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  endpoints,
  type BlueprintValidationResult,
} from "../api/client";
import { Button, Card, Input, Label, PageHeader } from "../components/ui";

const EXAMPLE = `schema_version: uvl-blueprint/v1
name: example-home
description: Small home lab
site:
  networks:
    - name: default
      vlan: 1
      subnet: 192.168.1.0/24
    - name: iot
      vlan: 10
      subnet: 192.168.10.0/24
  wlans:
    - ssid: CV-Home
      network: default
      security: wpa2
      passphrase: supersecret
  devices:
    - hostname: gateway
      model: UDR
    - hostname: switch-main
      model: USW24P250
      uplink: gateway
    - hostname: ap-office
      model: U6-Pro
      uplink: switch-main
`;

export function BlueprintEditorPage() {
  const params = useParams({ strict: false }) as { id?: string };
  const isNew = !params.id || params.id === "new";
  const navigate = useNavigate();
  const qc = useQueryClient();

  const existing = useQuery({
    queryKey: ["blueprints", params.id],
    queryFn: () => endpoints.blueprints.get(params.id!),
    enabled: !isNew,
  });

  const [name, setName] = useState("");
  const [source, setSource] = useState(EXAMPLE);
  const [validation, setValidation] = useState<BlueprintValidationResult | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (existing.data) {
      setName(existing.data.name);
      setSource(existing.data.source_yaml);
    }
  }, [existing.data]);

  const validate = useMutation({
    mutationFn: (yaml: string) => endpoints.blueprints.validate(yaml),
    onSuccess: (result) => setValidation(result),
  });

  const save = useMutation({
    mutationFn: () => {
      const body = { name, source_yaml: source };
      return isNew
        ? endpoints.blueprints.create(body)
        : endpoints.blueprints.update(params.id!, body);
    },
    onSuccess: (blueprint) => {
      qc.invalidateQueries({ queryKey: ["blueprints"] });
      setFormError(null);
      navigate({ to: "/blueprints/$id", params: { id: blueprint.id } });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : (err as Error).message);
    },
  });

  const del = useMutation({
    mutationFn: () => endpoints.blueprints.delete(params.id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["blueprints"] });
      navigate({ to: "/blueprints" });
    },
  });

  const issues = validation?.issues ?? [];

  return (
    <>
      <PageHeader
        title={isNew ? "New blueprint" : existing.data?.name ?? "Blueprint"}
        subtitle={
          isNew
            ? "YAML-authored site. Validate as you type; save to persist and bump the version."
            : `v${existing.data?.version ?? "?"} — edit updates increment the version on save.`
        }
        actions={
          <>
            <Link to="/blueprints" className="text-sm text-slate-400 hover:text-white">
              ← All blueprints
            </Link>
            {!isNew && (
              <Button
                size="sm"
                variant="danger"
                onClick={() => {
                  if (confirm(`Delete ${existing.data?.name}?`)) del.mutate();
                }}
              >
                Delete
              </Button>
            )}
          </>
        }
      />

      <div className="grid gap-6 md:grid-cols-[1fr_22rem]">
        <Card>
          <div className="mb-4 grid gap-2">
            <Label>Blueprint name (internal)</Label>
            <Input required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label>Source YAML</Label>
            <textarea
              className="min-h-[28rem] w-full rounded-md border border-slate-700 bg-slate-950 p-3 font-mono text-xs text-slate-100 focus-visible:border-indigo-500 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              spellCheck={false}
            />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => validate.mutate(source)}
              disabled={validate.isPending}
            >
              {validate.isPending ? "Validating…" : "Validate"}
            </Button>
            <Button
              onClick={() => save.mutate()}
              disabled={!name || save.isPending}
            >
              {save.isPending ? "Saving…" : isNew ? "Create" : "Save new version"}
            </Button>
            {formError && <p className="text-sm text-red-400">{formError}</p>}
          </div>
        </Card>

        <Card>
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
            Validation
          </h3>
          {!validation && (
            <p className="mt-3 text-sm text-slate-500">Click Validate to check the YAML.</p>
          )}
          {validation && (
            <>
              <p
                className={`mt-3 text-sm font-medium ${
                  validation.valid ? "text-emerald-300" : "text-red-300"
                }`}
              >
                {validation.valid
                  ? `Valid${
                      issues.length
                        ? ` — ${issues.filter((i) => i.severity === "warning").length} warning(s)`
                        : ""
                    }`
                  : `${issues.filter((i) => i.severity === "error").length} error(s)`}
              </p>
              {issues.length > 0 && (
                <ul className="mt-3 flex flex-col gap-2 text-xs">
                  {issues.map((i, idx) => (
                    <li
                      key={idx}
                      className={`rounded border p-2 ${
                        i.severity === "error"
                          ? "border-red-800 bg-red-900/20 text-red-300"
                          : "border-amber-800 bg-amber-900/20 text-amber-200"
                      }`}
                    >
                      <span className="font-mono text-slate-400">{i.path}</span>
                      <br />
                      {i.message}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </Card>
      </div>
    </>
  );
}
