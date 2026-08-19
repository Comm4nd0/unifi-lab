"""Small helpers for assembling sites in tests, fixtures and seed data."""

from __future__ import annotations

import zlib

from simcore.topology import SimClient, SimDevice, SimFlow, SimLink, SimSite

#: Ubiquiti OUIs, so generated MACs look like the real thing.
OUIS = ("78:8a:20", "74:ac:b9", "f4:92:bf", "e0:63:da", "24:5a:4c", "68:d7:9a")


def generate_mac(seed: str) -> str:
    """Stable, collision-resistant MAC for a device identifier."""
    digest = zlib.crc32(seed.encode())
    oui = OUIS[digest % len(OUIS)]
    tail = (digest >> 3) & 0xFFFFFF
    return f"{oui}:{tail >> 16 & 0xFF:02x}:{tail >> 8 & 0xFF:02x}:{tail & 0xFF:02x}"


class SiteBuilder:
    """Fluent builder that keeps identifiers and MACs consistent."""

    def __init__(self, site_id: str = "site-1", name: str = "Lab", **kwargs) -> None:
        self.site = SimSite(id=site_id, name=name, **kwargs)
        self._link_seq = 0

    def device(
        self,
        device_id: str,
        model: str,
        name: str | None = None,
        *,
        ip: str = "",
        **kwargs,
    ) -> SimDevice:
        device = SimDevice.from_model(
            device_id, model, name or device_id, mac=generate_mac(device_id), ip=ip, **kwargs
        )
        self.site.devices.append(device)
        return device

    def link(
        self,
        a_device: str,
        a_index: int,
        b_device: str,
        b_index: int,
        cable: str = "cat6",
        link_id: str | None = None,
    ) -> SimLink:
        self._link_seq += 1
        link = SimLink(
            id=link_id or f"link-{self._link_seq}",
            a=f"{a_device}:{a_index}",
            b=f"{b_device}:{b_index}",
            cable=cable,
        )
        self.site.links.append(link)
        return link

    def client(self, client_id: str, name: str, **kwargs) -> SimClient:
        client = SimClient(id=client_id, name=name, mac=generate_mac(client_id), **kwargs)
        self.site.clients.append(client)
        return client

    def flow(self, flow_id: str, name: str, **kwargs) -> SimFlow:
        flow = SimFlow(id=flow_id, name=name, **kwargs)
        self.site.flows.append(flow)
        return flow

    def build(self) -> SimSite:
        return self.site


def demo_site() -> SimSite:
    """A small office: gateway, core switch, access switch, two APs and clients."""
    b = SiteBuilder("demo", "Chiltern View", wan_download_mbps=900, wan_upload_mbps=110)
    b.device("gw", "udm-pro", "Dream Machine Pro", ip="10.0.0.1", stp_priority=4096, x=0, y=0)
    b.device("core", "usw-pro-24-poe", "Core Switch", ip="10.0.0.2", x=0, y=180)
    b.device("access", "usw-lite-16-poe", "Workshop Switch", ip="10.0.0.3", x=-260, y=340)
    b.device("ap-office", "u7-pro", "Office AP", ip="10.0.0.11", x=200, y=340)
    b.device("ap-barn", "u6-lr", "Barn AP", ip="10.0.0.12", x=-80, y=480)

    b.link("gw", 11, "core", 25, cable="dac")  # UDM SFP+ LAN into core SFP+
    b.link("core", 1, "access", 1)
    b.link("core", 17, "ap-office", 1)
    b.link("access", 9, "ap-barn", 1)

    b.client("c1", "Marco's Laptop", kind="wireless", ap_id="ap-office", ip="10.0.0.51",
             category="laptop", down_mbps=45, up_mbps=8)
    b.client("c2", "Workshop NAS", kind="wired", port_id="access:2", ip="10.0.0.60",
             category="server", down_mbps=20, up_mbps=60)
    b.client("c3", "Yard Camera", kind="wired", port_id="core:5", ip="10.0.0.70",
             category="camera", down_mbps=2, up_mbps=12)
    b.client("c4", "Farm Office iPad", kind="wireless", ap_id="ap-barn", ip="10.0.0.52",
             category="tablet", down_mbps=15, up_mbps=3, rssi_dbm=-68)

    b.flow("f1", "NAS backup to office", src_kind="client", src_id="c2",
           dst_kind="client", dst_id="c1", mbps=180)
    return b.build()
