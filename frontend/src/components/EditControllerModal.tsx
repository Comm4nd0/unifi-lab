import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ApiError, endpoints, type ControllerTarget } from "../api/client";
import { Button, Input, Label, Select } from "./ui";

/**
 * Edit a controller's connection config (everything except the API
 * credentials, which live on RotateSecretsModal). The ``kind`` field
 * matters because it picks the login-endpoint path — UniFi OS Server
 * (UDM with UOS ≥3) uses ``/api/auth/login``, legacy UniFi Network
 * (self-hosted, or older UDM firmware) uses ``/api/login``. Getting it
 * wrong means health-check reports bogus 401s.
 */
export function EditControllerModal({
  controller,
  open,
  onClose,
}: {
  controller: ControllerTarget | null;
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<ControllerTarget["kind"]>("uos-server");
  const [informUrl, setInformUrl] = useState("");
  const [apiUrl, setApiUrl] = useState("");
  const [verifyTls, setVerifyTls] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      if (!controller) throw new Error("no controller");
      return endpoints.controllers.update(controller.id, {
        name,
        kind,
        inform_url: informUrl,
        api_url: apiUrl,
        verify_tls: verifyTls,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["controllers"] });
      if (controller) qc.invalidateQueries({ queryKey: ["controllers", controller.id] });
      onClose();
    },
    onError: (e) => setErr(e instanceof ApiError ? e.message : String(e)),
  });

  useEffect(() => {
    if (!open || !controller) return;
    setName(controller.name);
    setKind(controller.kind);
    setInformUrl(controller.inform_url);
    setApiUrl(controller.api_url);
    setVerifyTls(controller.verify_tls);
    setErr(null);
  }, [open, controller]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !controller) return null;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setErr("Name is required.");
      return;
    }
    save.mutate();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 pt-[8vh]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-lg border border-slate-700 bg-slate-950 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-slate-800 px-4 py-3">
          <h2 className="text-sm font-medium uppercase tracking-wide text-slate-300">
            Edit controller
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Use <span className="font-mono">Rotate secrets</span> to change API credentials.
          </p>
        </div>
        <form onSubmit={onSubmit} className="grid gap-3 px-4 py-4">
          <div>
            <Label>Name</Label>
            <Input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              spellCheck={false}
            />
          </div>
          <div>
            <Label>Kind</Label>
            <Select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
              <option value="uos-server">UniFi OS Server (UDM / UDM-Pro / UDR / UOS ≥3)</option>
              <option value="legacy-network">
                UniFi Network (self-hosted / older firmware)
              </option>
            </Select>
            <p className="mt-1 text-xs text-slate-500">
              Picks the login-endpoint path:{" "}
              <span className="font-mono">/api/auth/login</span> vs{" "}
              <span className="font-mono">/api/login</span>. If health-check shows
              {" "}<span className="font-mono">status 401 · Unauthorized</span> with credentials you
              know are correct, switching this is usually the fix.
            </p>
          </div>
          <div>
            <Label>Inform URL</Label>
            <Input
              value={informUrl}
              onChange={(e) => setInformUrl(e.target.value)}
              placeholder="https://192.168.1.1:443"
              spellCheck={false}
            />
          </div>
          <div>
            <Label>API URL</Label>
            <Input
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              placeholder="https://192.168.1.1:443"
              spellCheck={false}
            />
            <p className="mt-1 text-xs text-slate-500">
              Base URL for the login endpoint — usually the same host as the inform URL, no
              trailing <span className="font-mono">/api</span> suffix.
            </p>
          </div>
          <label className="flex items-start gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-slate-700 bg-slate-900"
              checked={verifyTls}
              onChange={(e) => setVerifyTls(e.target.checked)}
            />
            <div>
              <span>Verify TLS</span>
              <span className="ml-2 text-xs text-slate-500">
                Uncheck for self-signed certs (most lab UDMs).
              </span>
            </div>
          </label>
          {err && <p className="text-sm text-red-400">{err}</p>}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save changes"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
