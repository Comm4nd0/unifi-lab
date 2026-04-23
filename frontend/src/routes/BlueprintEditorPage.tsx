import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  endpoints,
  type BlueprintValidationResult,
} from "../api/client";
import { BlueprintCanvas } from "../components/BlueprintCanvas";
import { BlueprintTopology } from "../components/BlueprintTopology";
import { DevicePalette } from "../components/DevicePalette";
import { YamlEditor } from "../components/YamlEditor";
import { Button, Card, Input, Label, PageHeader } from "../components/ui";
import {
  parseBlueprintYaml,
  stringifyBlueprint,
  type BlueprintDoc,
} from "../lib/blueprintDoc";

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

type View = "canvas" | "yaml";

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
  const [view, setView] = useState<View>("canvas");

  // Canvas works off a parsed doc; YAML textarea works off the source
  // string. Both paths keep ``source`` as the single source of truth so
  // the validator sees a consistent input.
  const doc = useMemo<BlueprintDoc>(
    () => parseBlueprintYaml(source) ?? { devices: [], rest: {} },
    [source],
  );

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

  // Auto-validate: on load, and whenever the source changes from any
  // path (canvas mutation or YAML edit). Debounced so fast edits don't
  // hammer the API.
  const debounceRef = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (!source) return;
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      validate.mutate(source);
    }, 300);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
    // validate.mutate is stable for the mutation lifetime.

  }, [source]);

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

  const onCanvasChange = (next: BlueprintDoc) => {
    setSource(stringifyBlueprint(next));
  };

  const issues = validation?.issues ?? [];

  return (
    <>
      <PageHeader
        title={isNew ? "New blueprint" : existing.data?.name ?? "Blueprint"}
        subtitle={
          isNew
            ? "Drag devices from the palette onto the canvas, or flip to YAML for full control."
            : `v${existing.data?.version ?? "?"} — edit updates increment the version on save.`
        }
        actions={
          <>
            <Link to="/blueprints" className="text-sm text-slate-400 hover:text-white">
              ← All blueprints
            </Link>
            <ViewToggle view={view} onChange={setView} />
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

      <div className="mb-4 grid gap-2 md:max-w-sm">
        <Label>Blueprint name (internal)</Label>
        <Input required value={name} onChange={(e) => setName(e.target.value)} />
      </div>

      {view === "canvas" ? (
        <Card>
          <div className="grid gap-4 md:grid-cols-[14rem_1fr]">
            <DevicePalette />
            <BlueprintCanvas doc={doc} onChange={onCanvasChange} />
          </div>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-[1fr_22rem]">
          <Card>
            <Label>Source YAML</Label>
            <div className="mt-1">
              <YamlEditor value={source} onChange={setSource} minHeight="28rem" />
            </div>
          </Card>
          <Card>
            <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
              Validation
            </h3>
            {!validation && (
              <p className="mt-3 text-sm text-slate-500">Validating…</p>
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
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          onClick={() => save.mutate()}
          disabled={!name || save.isPending}
        >
          {save.isPending ? "Saving…" : isNew ? "Create" : "Save new version"}
        </Button>
        {validation?.valid === false && (
          <span className="text-xs text-red-400">
            Fix validation errors before saving.
          </span>
        )}
        {formError && <span className="text-sm text-red-400">{formError}</span>}
      </div>

      {view === "yaml" && (
        <Card className="mt-6">
          <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">
            Topology preview
          </h3>
          <div className="mt-3">
            <BlueprintTopology parsed={validation?.parsed ?? existing.data?.parsed_json ?? null} />
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Read-only mirror of the last validated blueprint. Refreshes on each validate.
          </p>
        </Card>
      )}
    </>
  );
}

function ViewToggle({
  view,
  onChange,
}: {
  view: View;
  onChange: (v: View) => void;
}) {
  return (
    <div className="flex overflow-hidden rounded-md border border-slate-800 bg-slate-900 text-xs">
      {(["canvas", "yaml"] as View[]).map((v) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={
            "px-3 py-1.5 capitalize transition " +
            (view === v
              ? "bg-indigo-600 text-white"
              : "text-slate-400 hover:text-slate-200")
          }
        >
          {v}
        </button>
      ))}
    </div>
  );
}
