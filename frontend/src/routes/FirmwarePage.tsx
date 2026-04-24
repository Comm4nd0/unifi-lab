import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, endpoints, type FirmwareBlob } from "../api/client";
import { useConfirm } from "../components/ConfirmDialog";
import { Card, EmptyState, PageHeader, StateChip } from "../components/ui";

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

export function FirmwarePage() {
  const qc = useQueryClient();
  const { openConfirm } = useConfirm();
  const fileInput = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);

  const list = useQuery({
    queryKey: ["firmware"],
    queryFn: endpoints.firmware.list,
    refetchInterval: 5_000,
  });

  const upload = useMutation({
    mutationFn: (file: File) => endpoints.firmware.upload(file),
    onSuccess: () => {
      setLastError(null);
      qc.invalidateQueries({ queryKey: ["firmware"] });
    },
    onError: (err) =>
      setLastError(err instanceof ApiError ? err.message : (err as Error).message),
  });

  const del = useMutation({
    mutationFn: (id: string) => endpoints.firmware.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["firmware"] }),
  });

  const takeFiles = (files: FileList | null) => {
    if (!files) return;
    for (const f of Array.from(files)) {
      upload.mutate(f);
    }
  };

  const onDrop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setDragActive(false);
    takeFiles(e.dataTransfer.files);
  };

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    takeFiles(e.target.files);
    e.target.value = "";
  };

  return (
    <>
      <PageHeader
        title="Firmware"
        subtitle="Upload UniFi firmware images. Ingestion runs in the worker-celery container."
      />

      <Card className="mb-6">
        <label
          htmlFor="firmware-upload"
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={onDrop}
          className={`flex min-h-40 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 text-center transition ${
            dragActive
              ? "border-indigo-500 bg-indigo-500/10"
              : "border-slate-700 bg-slate-950/60 hover:border-slate-600"
          }`}
        >
          <p className="text-base text-slate-200">
            Drop .bin files here, or <span className="text-indigo-400 underline">browse</span>
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Multiple files supported. Duplicates (same sha256) are deduped.
          </p>
          <input
            ref={fileInput}
            id="firmware-upload"
            type="file"
            accept=".bin,.tar,.tgz,application/octet-stream"
            multiple
            onChange={onChange}
            className="hidden"
          />
        </label>
        {upload.isPending && (
          <p className="mt-3 text-sm text-slate-400">Uploading…</p>
        )}
        {lastError && <p className="mt-3 text-sm text-red-400">{lastError}</p>}
      </Card>

      {list.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
      {list.data && list.data.results.length === 0 && (
        <EmptyState
          title="No firmware uploaded yet"
          hint="Drop a .bin to build device templates the engine can instantiate."
        />
      )}
      {list.data && list.data.results.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-xs uppercase text-slate-400">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Filename</th>
                <th className="px-4 py-2 text-left font-medium">Size</th>
                <th className="px-4 py-2 text-left font-medium">SHA-256</th>
                <th className="px-4 py-2 text-left font-medium">State</th>
                <th className="px-4 py-2 text-left font-medium">Models</th>
                <th className="px-4 py-2 text-left font-medium">Uploaded</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {list.data.results.map((f: FirmwareBlob) => (
                <tr key={f.id} className="hover:bg-slate-900/40">
                  <td className="px-4 py-3 font-medium">{f.filename}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400">
                    {humanSize(f.size_bytes)}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {f.sha256.slice(0, 12)}…
                  </td>
                  <td className="px-4 py-3">
                    <StateChip state={f.state} />
                  </td>
                  <td className="px-4 py-3 text-slate-400">
                    {f.model_codes.length ? f.model_codes.join(", ") : <span className="text-slate-600">—</span>}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">
                    {new Date(f.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      className="text-xs text-red-400 hover:text-red-300"
                      onClick={async () => {
                        const ok = await openConfirm({
                          title: `Delete ${f.filename}?`,
                          confirmLabel: "Delete",
                          variant: "danger",
                        });
                        if (ok) del.mutate(f.id);
                      }}
                    >
                      Delete
                    </button>
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
