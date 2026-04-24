import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ApiError, endpoints } from "../api/client";
import { Button, Input, Label } from "./ui";

/**
 * Modal for updating a controller's API username + password after it's
 * been created. Talks to ``POST /api/v1/controllers/{id}/secrets/`` —
 * the backend Fernet-encrypts the new values at rest.
 *
 * Either field can be left blank to keep its current value (the form
 * strips empty strings before posting). Password is never pre-filled.
 */
export function RotateSecretsModal({
  controllerId,
  open,
  onClose,
  onRotated,
}: {
  controllerId: string;
  open: boolean;
  onClose: () => void;
  onRotated?: () => void;
}) {
  const qc = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const rotate = useMutation({
    mutationFn: (body: { api_username?: string; api_password?: string }) =>
      endpoints.controllers.rotateSecrets(controllerId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["controllers"] });
      qc.invalidateQueries({ queryKey: ["controllers", controllerId] });
      onRotated?.();
      onClose();
    },
    onError: (e) => setErr(e instanceof ApiError ? e.message : String(e)),
  });

  useEffect(() => {
    if (!open) return;
    setUsername("");
    setPassword("");
    setErr(null);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const body: { api_username?: string; api_password?: string } = {};
    if (username.trim()) body.api_username = username.trim();
    if (password) body.api_password = password;
    if (!body.api_username && !body.api_password) {
      setErr("Enter at least one field to update.");
      return;
    }
    setErr(null);
    rotate.mutate(body);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 pt-[12vh]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md overflow-hidden rounded-lg border border-slate-700 bg-slate-950 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-slate-800 px-4 py-3">
          <h2 className="text-sm font-medium uppercase tracking-wide text-slate-300">
            Rotate API credentials
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            The backend re-encrypts the new values with Fernet before persisting. Leave a field
            blank to keep its current value.
          </p>
        </div>
        <form onSubmit={onSubmit} className="grid gap-3 px-4 py-4">
          <div>
            <Label>API username</Label>
            <Input
              type="text"
              autoComplete="off"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="leave blank to keep current"
              spellCheck={false}
            />
          </div>
          <div>
            <Label>API password</Label>
            <Input
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="leave blank to keep current"
            />
          </div>
          {err && <p className="text-sm text-red-400">{err}</p>}
          <div className="mt-2 flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={rotate.isPending}>
              {rotate.isPending ? "Saving…" : "Save credentials"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
