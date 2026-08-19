import { useEffect, useState } from "react";

import {
  api,
  del,
  patch,
  post,
  useNetworks,
  useSimulation,
  useSiteMutation,
  useSites,
} from "@/api/client";
import { PlusIcon, TrashIcon } from "@/components/icons";
import {
  Badge,
  Button,
  Field,
  Input,
  Panel,
  Select,
  Table,
  Tr,
  useToast,
} from "@/components/ui";
import { useUi } from "@/store";
import type { NetworkRow, Site, StpMode } from "@/types";

export function SettingsPage() {
  const { siteId, setSite } = useUi();
  const sites = useSites();
  const { data: sim } = useSimulation(siteId);
  const site = sites.data?.find((item) => item.id === siteId);

  if (!site || !sim) return <div className="p-6 text-sm text-ink-500">Loading settings…</div>;

  return (
    <div className="grid gap-4 p-5 xl:grid-cols-2">
      <SiteSettings site={site} />
      <Networks />
      <Blueprint site={site} />
      <SiteAdmin site={site} onSwitch={setSite} />
    </div>
  );
}

function SiteSettings({ site }: { site: Site }) {
  const toast = useToast();
  const [form, setForm] = useState(site);

  useEffect(() => setForm(site), [site]);

  const save = useSiteMutation(site.id, (body: Partial<Site>) =>
    patch<Site>(`/sites/${site.id}/`, body),
  );

  const dirty =
    form.name !== site.name ||
    form.description !== site.description ||
    form.stp_mode !== site.stp_mode ||
    Number(form.wan_download_mbps) !== site.wan_download_mbps ||
    Number(form.wan_upload_mbps) !== site.wan_upload_mbps;

  return (
    <Panel title="Site" subtitle="Global settings for this virtual network">
      <div className="space-y-3">
        <Field label="Name">
          <Input
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </Field>
        <Field label="Description">
          <Input
            value={form.description}
            placeholder="What is this network for?"
            onChange={(event) => setForm({ ...form, description: event.target.value })}
          />
        </Field>
        <Field
          label="Spanning tree mode"
          hint="RSTP recovers in seconds. Turning it off is a good way to watch a loop take the network down."
        >
          <Select
            value={form.stp_mode}
            onChange={(event) =>
              setForm({ ...form, stp_mode: event.target.value as StpMode })
            }
          >
            <option value="rstp">RSTP (802.1w)</option>
            <option value="stp">STP (802.1D)</option>
            <option value="disabled">Disabled</option>
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="WAN download (Mbps)">
            <Input
              type="number"
              min={1}
              value={form.wan_download_mbps}
              onChange={(event) =>
                setForm({ ...form, wan_download_mbps: Number(event.target.value) })
              }
            />
          </Field>
          <Field label="WAN upload (Mbps)">
            <Input
              type="number"
              min={1}
              value={form.wan_upload_mbps}
              onChange={(event) =>
                setForm({ ...form, wan_upload_mbps: Number(event.target.value) })
              }
            />
          </Field>
        </div>
        <Button
          variant="primary"
          disabled={!dirty || save.isPending}
          onClick={() =>
            save
              .mutateAsync({
                name: form.name,
                description: form.description,
                stp_mode: form.stp_mode,
                wan_download_mbps: Number(form.wan_download_mbps),
                wan_upload_mbps: Number(form.wan_upload_mbps),
              })
              .then(() => toast("Site updated."))
              .catch((error: Error) => toast(error.message, "bad"))
          }
        >
          Save changes
        </Button>
      </div>
    </Panel>
  );
}

function Networks() {
  const toast = useToast();
  const { siteId } = useUi();
  const networks = useNetworks(siteId);
  const [form, setForm] = useState({ name: "", vlan_id: 10, subnet: "192.168.10.0/24" });

  const create = useSiteMutation(siteId, () =>
    post<NetworkRow>("/networks/", { site: siteId, ...form, vlan_id: Number(form.vlan_id) }),
  );
  const remove = useSiteMutation(siteId, (id: number) => del(`/networks/${id}/`));

  return (
    <Panel title="Networks" subtitle="VLANs available in this site" bodyClassName="p-0">
      <Table>
        <thead>
          <tr>
            <th className="th">Name</th>
            <th className="th">VLAN</th>
            <th className="th">Subnet</th>
            <th className="th" />
          </tr>
        </thead>
        <tbody>
          {(networks.data ?? []).map((network) => (
            <Tr key={network.id}>
              <td className="td">
                <span className="font-medium text-ink-100">{network.name}</span>
                {network.isolated && (
                  <Badge tone="warn" className="ml-2">
                    isolated
                  </Badge>
                )}
              </td>
              <td className="td tabular-nums text-ink-400">{network.vlan_id}</td>
              <td className="td font-mono text-xs text-ink-400">{network.subnet}</td>
              <td className="td text-right">
                <button
                  className="text-ink-500 hover:text-bad"
                  onClick={() =>
                    remove
                      .mutateAsync(network.id)
                      .then(() => toast("Network removed."))
                      .catch((error: Error) => toast(error.message, "bad"))
                  }
                >
                  <TrashIcon size={15} />
                </button>
              </td>
            </Tr>
          ))}
          {!networks.data?.length && (
            <tr>
              <td className="td text-ink-500" colSpan={4}>
                No VLANs defined.
              </td>
            </tr>
          )}
        </tbody>
      </Table>
      <div className="flex items-end gap-2 border-t border-ink-800 p-4">
        <Field label="Name" className="flex-1">
          <Input
            placeholder="Guest"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
        </Field>
        <Field label="VLAN" className="w-24">
          <Input
            type="number"
            min={1}
            max={4094}
            value={form.vlan_id}
            onChange={(event) => setForm({ ...form, vlan_id: Number(event.target.value) })}
          />
        </Field>
        <Field label="Subnet" className="flex-1">
          <Input
            value={form.subnet}
            onChange={(event) => setForm({ ...form, subnet: event.target.value })}
          />
        </Field>
        <Button
          disabled={!form.name.trim() || create.isPending}
          onClick={() =>
            create
              .mutateAsync()
              .then(() => {
                toast("Network added.");
                setForm({ name: "", vlan_id: form.vlan_id + 10, subnet: "192.168.20.0/24" });
              })
              .catch((error: Error) => toast(error.message, "bad"))
          }
        >
          <PlusIcon size={14} /> Add
        </Button>
      </div>
    </Panel>
  );
}

function Blueprint({ site }: { site: Site }) {
  const toast = useToast();
  const { setSite } = useUi();
  const [text, setText] = useState("");

  const load = () =>
    api<unknown>(`/sites/${site.id}/blueprint/`)
      .then((blueprint) => setText(JSON.stringify(blueprint, null, 2)))
      .catch((error: Error) => toast(error.message, "bad"));

  const importer = useSiteMutation(null, () =>
    post<Site>(`/sites/${site.id}/blueprint/`, {
      blueprint: JSON.parse(text),
      name: `${site.name} copy`,
    }),
  );

  const download = () => {
    const blob = new Blob([text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${site.name.toLowerCase().replace(/\s+/g, "-")}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Panel
      title="Blueprint"
      subtitle="Export the whole site, edit it, or re-import it as a copy"
    >
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button onClick={load}>Export this site</Button>
          <Button disabled={!text} onClick={download}>
            Download JSON
          </Button>
          <Button
            variant="primary"
            disabled={!text || importer.isPending}
            onClick={() =>
              importer
                .mutateAsync()
                .then((created) => {
                  setSite(created.id);
                  toast(`Imported as "${created.name}".`);
                })
                .catch((error: Error) => toast(error.message, "bad"))
            }
          >
            Import as new site
          </Button>
        </div>
        <textarea
          className="field h-56 resize-y font-mono text-[11px] leading-relaxed"
          spellCheck={false}
          placeholder="Export a site, or paste a blueprint here to import it."
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      </div>
    </Panel>
  );
}

function SiteAdmin({ site, onSwitch }: { site: Site; onSwitch: (id: number | null) => void }) {
  const toast = useToast();
  const sites = useSites();
  const [name, setName] = useState("");

  const create = useSiteMutation(null, () => post<Site>("/sites/", { name: name.trim() }));
  const seed = useSiteMutation(null, () => post<Site>("/sites/seed-demo/", {}));
  const remove = useSiteMutation(null, () => del(`/sites/${site.id}/`));

  return (
    <Panel title="Sites" subtitle={`${sites.data?.length ?? 0} in this lab`}>
      <div className="space-y-4">
        <div className="flex items-end gap-2">
          <Field label="New site" className="flex-1">
            <Input
              placeholder="Branch office"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Button
            disabled={!name.trim() || create.isPending}
            onClick={() =>
              create
                .mutateAsync()
                .then((created) => {
                  onSwitch(created.id);
                  setName("");
                  toast(`Site "${created.name}" created.`);
                })
                .catch((error: Error) => toast(error.message, "bad"))
            }
          >
            Create
          </Button>
          <Button
            onClick={() =>
              seed
                .mutateAsync()
                .then((created) => {
                  onSwitch(created.id);
                  toast("Example site created.");
                })
                .catch((error: Error) => toast(error.message, "bad"))
            }
          >
            Add example
          </Button>
        </div>

        <div className="border-t border-ink-800 pt-3">
          <p className="mb-2 text-xs text-ink-400">
            Deleting a site removes its devices, cables, clients and flows for good.
          </p>
          <Button
            variant="danger"
            disabled={(sites.data?.length ?? 0) < 2}
            onClick={() =>
              remove
                .mutateAsync()
                .then(() => {
                  const next = sites.data?.find((item) => item.id !== site.id);
                  onSwitch(next?.id ?? null);
                  toast(`"${site.name}" deleted.`);
                })
                .catch((error: Error) => toast(error.message, "bad"))
            }
          >
            <TrashIcon size={14} /> Delete “{site.name}”
          </Button>
        </div>
      </div>
    </Panel>
  );
}
