"""Network topology engine — pure Python, no Django ORM.

Converts a validated blueprint ``parsed_data`` dict into a rich ``Site``
object containing networks, VLANs, WLANs, virtual clients (with assigned
IPs and personas), device links, and an evaluable firewall model.

Usable from Django views, the engine worker, and tests without any DB
dependency.

Personas define the traffic behaviour of a client endpoint.  Each persona
is a dict with:
  ``flows``  — list of flow dicts matching the TrafficProfile.flows schema
  ``rate``   — approximate flows / minute (informational; ticker uses profiles)
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from ipaddress import IPv4Network
from typing import Any

# ── Personas ──────────────────────────────────────────────────────────────────

PERSONAS: dict[str, dict[str, Any]] = {
    "iot-camera": {
        "rate": 3,
        "flows": [
            {
                "direction": "client-to-internet",
                "app": "Cloud Services",
                "rate": "2/min",
                "bytes_per_flow": "20KB-200KB",
            },
            {
                "direction": "client-to-internet",
                "app": "HTTPS",
                "rate": "1/min",
                "bytes_per_flow": "1KB-10KB",
            },
        ],
    },
    "laptop-worker": {
        "rate": 30,
        "flows": [
            {"direction": "client-to-internet", "app": "HTTPS",  "rate": "10/min", "bytes_per_flow": "5KB-5MB"},
            {"direction": "client-to-internet", "app": "Zoom",   "rate": "2/min",  "bytes_per_flow": "500KB-5MB"},
            {"direction": "client-to-internet", "app": "Slack",  "rate": "5/min",  "bytes_per_flow": "10KB-500KB"},
            {"direction": "client-to-internet", "app": "DNS",    "rate": "20/min", "bytes_per_flow": "100-1000"},
            {"direction": "client-to-internet", "app": "OneDrive","rate": "1/min", "bytes_per_flow": "50KB-10MB"},
        ],
    },
    "phone-streaming": {
        "rate": 15,
        "flows": [
            {"direction": "client-to-internet", "app": "YouTube",  "rate": "5/min", "bytes_per_flow": "500KB-5MB"},
            {"direction": "client-to-internet", "app": "Spotify",  "rate": "3/min", "bytes_per_flow": "200KB-1MB"},
            {"direction": "client-to-internet", "app": "Instagram","rate": "4/min", "bytes_per_flow": "200KB-2MB"},
            {"direction": "client-to-internet", "app": "TikTok",   "rate": "3/min", "bytes_per_flow": "500KB-5MB"},
        ],
    },
    "smart-tv": {
        "rate": 8,
        "flows": [
            {"direction": "client-to-internet", "app": "Netflix",     "rate": "4/min", "bytes_per_flow": "2MB-20MB"},
            {"direction": "client-to-internet", "app": "Disney+",     "rate": "2/min", "bytes_per_flow": "2MB-15MB"},
            {"direction": "client-to-internet", "app": "Amazon Prime","rate": "2/min", "bytes_per_flow": "2MB-15MB"},
        ],
    },
    "printer": {
        "rate": 2,
        "flows": [
            {"direction": "client-to-lan",      "app": "SMB",   "rate": "1/min", "bytes_per_flow": "10KB-5MB"},
            {"direction": "client-to-internet", "app": "HTTPS", "rate": "1/min", "bytes_per_flow": "1KB-50KB"},
        ],
    },
    "voip-phone": {
        "rate": 12,
        "flows": [
            {"direction": "client-to-internet", "app": "SIP",  "rate": "4/min", "bytes_per_flow": "1KB-5KB"},
            {"direction": "client-to-internet", "app": "RTP",  "rate": "8/min", "bytes_per_flow": "20KB-200KB"},
        ],
    },
}

# Which persona to assign to which blueprint model family.
_MODEL_PERSONA: dict[str, str] = {
    "ap":      "laptop-worker",
    "switch":  "printer",
    "gateway": "voip-phone",
    "other":   "iot-camera",
}


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class Vlan:
    id: int
    name: str


@dataclass
class Network:
    name: str
    vlan: int
    subnet: IPv4Network


@dataclass
class Wlan:
    ssid: str
    network: str
    security: str
    passphrase: str = ""


@dataclass
class VirtualClient:
    hostname: str
    persona: str
    network: str
    ip_address: str
    mac_address: str


@dataclass
class Link:
    src: str      # hostname
    dst: str      # hostname
    link_type: str = "wired"  # "wired" | "wireless"
    utilization: float = 0.0  # 0.0-1.0 for edge colour rendering


@dataclass
class FirewallRule:
    name: str
    src_network: str | None = None   # None = any
    dst_network: str | None = None   # None = any
    protocol: str | None = None      # None = any
    dst_port: int | None = None      # None = any
    action: str = "allow"            # "allow" | "block"


@dataclass
class Site:
    networks: dict[str, Network] = field(default_factory=dict)
    vlans: list[Vlan] = field(default_factory=list)
    wlans: list[Wlan] = field(default_factory=list)
    devices: list[dict[str, Any]] = field(default_factory=list)
    clients: list[VirtualClient] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    firewall_rules: list[FirewallRule] = field(default_factory=list)


# ── Firewall engine ───────────────────────────────────────────────────────────

class FirewallEngine:
    """Stateless match-rule evaluator.

    Rules are evaluated in order; the first match wins.  If no rule matches,
    the default policy is *allow* (open LAN — realistic for a typical home/
    lab setup; enterprise default-deny is opt-in via an explicit rule).
    """

    def __init__(self, rules: list[FirewallRule]) -> None:
        self.rules = rules

    def evaluate(
        self,
        *,
        src_network: str | None = None,
        dst_network: str | None = None,
        protocol: str | None = None,
        dst_port: int | None = None,
    ) -> tuple[bool, str | None]:
        """Return ``(allowed, matching_rule_name)``."""
        for rule in self.rules:
            if self._matches(rule, src_network, dst_network, protocol, dst_port):
                return rule.action == "allow", rule.name
        return True, None  # default allow

    @staticmethod
    def _matches(
        rule: FirewallRule,
        src_network: str | None,
        dst_network: str | None,
        protocol: str | None,
        dst_port: int | None,
    ) -> bool:
        if rule.src_network and rule.src_network != src_network:
            return False
        if rule.dst_network and rule.dst_network != dst_network:
            return False
        if rule.protocol and rule.protocol != protocol:
            return False
        return not (rule.dst_port is not None and rule.dst_port != dst_port)


# ── IP assignment ─────────────────────────────────────────────────────────────

def _assign_ips(clients: list[VirtualClient], networks: dict[str, Network]) -> None:
    """Assign sequential IPs from .10 upwards in each network's subnet."""
    counters: dict[str, int] = {}
    for client in clients:
        net = networks.get(client.network)
        if net is None:
            client.ip_address = "0.0.0.0"
            continue
        idx = counters.get(client.network, 10)
        counters[client.network] = idx + 1
        hosts = list(net.subnet.hosts())
        client.ip_address = str(hosts[min(idx, len(hosts) - 1)])


def _deterministic_mac(seed_str: str) -> str:
    h = hashlib.sha256(seed_str.encode()).digest()
    return f"02:cc:{h[0]:02x}:{h[1]:02x}:{h[2]:02x}:{h[3]:02x}"


# ── Firewall rule parsing ─────────────────────────────────────────────────────

def _parse_firewall_rules(site_data: dict[str, Any]) -> list[FirewallRule]:
    """Parse ``site.firewall_rules`` list from blueprint data."""
    rules: list[FirewallRule] = []
    for raw in site_data.get("firewall_rules", []) or []:
        if not isinstance(raw, dict):
            continue
        port = raw.get("dst_port")
        rules.append(
            FirewallRule(
                name=str(raw.get("name") or "unnamed"),
                src_network=raw.get("src_network") or None,
                dst_network=raw.get("dst_network") or None,
                protocol=raw.get("protocol") or None,
                dst_port=int(port) if port is not None else None,
                action=str(raw.get("action", "allow")).lower(),
            )
        )
    return rules


# ── Model-to-family helper (mirrors apps/templates/models.py) ─────────────────

def _model_family(model_code: str) -> str:
    mc = model_code.upper()
    if mc.startswith(("U6-", "U7-", "UAP", "UAP-")):
        return "ap"
    if mc.startswith(("USW", "US-")):
        return "switch"
    if mc.startswith(("UDR", "UDM", "USG", "UCG")):
        return "gateway"
    return "other"


# ── Main builder ──────────────────────────────────────────────────────────────

def build_topology(
    blueprint_data: dict[str, Any],
    *,
    seed: int = 42,
    clients_per_ap: int = 3,
) -> Site:
    """Convert blueprint ``parsed_data`` → ``Site`` topology.

    Parameters
    ----------
    blueprint_data:
        Validated parsed blueprint dict.
    seed:
        RNG seed for deterministic client MAC generation.
    clients_per_ap:
        How many virtual client endpoints to generate per AP-family device.
    """
    rng = random.Random(seed)
    site_data: dict[str, Any] = blueprint_data.get("site", {})

    # Networks
    networks: dict[str, Network] = {}
    vlans: list[Vlan] = []
    for n in site_data.get("networks", []) or []:
        name = str(n.get("name", "default"))
        vlan_id = int(n.get("vlan", 1))
        subnet_str = str(n.get("subnet", "10.0.0.0/24"))
        try:
            subnet = IPv4Network(subnet_str, strict=False)
        except ValueError:
            subnet = IPv4Network("10.0.0.0/24")
        networks[name] = Network(name=name, vlan=vlan_id, subnet=subnet)
        vlans.append(Vlan(id=vlan_id, name=name))

    # Default network if blueprint has none
    if not networks:
        networks["default"] = Network(name="default", vlan=1, subnet=IPv4Network("10.0.0.0/24"))
        vlans.append(Vlan(id=1, name="default"))

    # WLANs
    wlans = [
        Wlan(
            ssid=str(w.get("ssid", "")),
            network=str(w.get("network", "")),
            security=str(w.get("security", "wpa2")),
            passphrase=str(w.get("passphrase", "")),
        )
        for w in site_data.get("wlans", []) or []
    ]

    devices: list[dict[str, Any]] = site_data.get("devices", []) or []

    # Links from uplink relationships
    links: list[Link] = []
    for dev in devices:
        uplink = dev.get("uplink")
        if uplink:
            links.append(Link(src=str(dev.get("hostname", "")), dst=str(uplink)))

    # Virtual clients — one set per AP-family device
    clients: list[VirtualClient] = []
    default_net = next(iter(networks), "default")
    client_personas = list(PERSONAS.keys())

    for dev in devices:
        family = _model_family(str(dev.get("model", "")))
        if family != "ap":
            continue
        dev_hostname = str(dev.get("hostname", "ap"))
        dev_network = dev.get("network") or default_net
        for i in range(clients_per_ap):
            persona = client_personas[rng.randint(0, len(client_personas) - 1)]
            hostname = f"client-{dev_hostname}-{i + 1}"
            mac = _deterministic_mac(f"{dev_hostname}|{i}")
            clients.append(
                VirtualClient(
                    hostname=hostname,
                    persona=persona,
                    network=str(dev_network),
                    ip_address="",
                    mac_address=mac,
                )
            )
            # Wireless link: client → AP
            links.append(Link(src=hostname, dst=dev_hostname, link_type="wireless"))

    _assign_ips(clients, networks)

    # Firewall rules
    firewall_rules = _parse_firewall_rules(site_data)

    return Site(
        networks=networks,
        vlans=vlans,
        wlans=wlans,
        devices=devices,
        clients=clients,
        links=links,
        firewall_rules=firewall_rules,
    )
