"""Unit tests for backend/apps/blueprints/topology.py."""
from __future__ import annotations

from apps.blueprints.topology import (
    PERSONAS,
    FirewallEngine,
    FirewallRule,
    build_topology,
)

# ── Fixtures ─────────────────────────────────────────────────────────────────

SIMPLE_BP: dict = {
    "name": "test-site",
    "site": {
        "networks": [
            {"name": "main", "vlan": 10, "subnet": "192.168.10.0/24"},
            {"name": "iot", "vlan": 20, "subnet": "192.168.20.0/24"},
        ],
        "wlans": [
            {"ssid": "TestNet", "network": "main", "security": "wpa2", "passphrase": "secret"},
        ],
        "devices": [
            {"hostname": "gw-01",  "model": "UDM-PRO", "network": "main"},
            {"hostname": "sw-01",  "model": "USW-24",   "network": "main", "uplink": "gw-01"},
            {"hostname": "ap-01",  "model": "U6-LITE",  "network": "main", "uplink": "sw-01"},
            {"hostname": "ap-02",  "model": "U6-LR",    "network": "iot",  "uplink": "sw-01"},
        ],
        "firewall_rules": [
            {"name": "block-iot-main", "src_network": "iot", "dst_network": "main", "action": "block"},
            {"name": "allow-dns",      "protocol": "udp", "dst_port": 53, "action": "allow"},
        ],
    },
}


# ── build_topology — networks ─────────────────────────────────────────────────

def test_topology_networks_parsed():
    site = build_topology(SIMPLE_BP)
    assert "main" in site.networks
    assert "iot" in site.networks
    assert str(site.networks["main"].subnet) == "192.168.10.0/24"
    assert site.networks["iot"].vlan == 20


def test_topology_vlans_populated():
    site = build_topology(SIMPLE_BP)
    vlan_ids = {v.id for v in site.vlans}
    assert 10 in vlan_ids
    assert 20 in vlan_ids


def test_topology_wlans():
    site = build_topology(SIMPLE_BP)
    assert len(site.wlans) == 1
    assert site.wlans[0].ssid == "TestNet"
    assert site.wlans[0].security == "wpa2"


# ── build_topology — devices & links ─────────────────────────────────────────

def test_topology_devices_list():
    site = build_topology(SIMPLE_BP)
    hostnames = [d["hostname"] for d in site.devices]
    assert "gw-01" in hostnames
    assert "ap-01" in hostnames


def test_topology_uplink_links():
    site = build_topology(SIMPLE_BP)
    wired = [(lnk.src, lnk.dst) for lnk in site.links if lnk.link_type == "wired"]
    assert ("sw-01", "gw-01") in wired
    assert ("ap-01", "sw-01") in wired


def test_topology_wireless_client_links():
    site = build_topology(SIMPLE_BP, clients_per_ap=2)
    wireless = [(lnk.src, lnk.dst) for lnk in site.links if lnk.link_type == "wireless"]
    # 2 APs x 2 clients each = 4 wireless links
    assert len(wireless) == 4
    dsts = {lnk.dst for lnk in site.links if lnk.link_type == "wireless"}
    assert "ap-01" in dsts
    assert "ap-02" in dsts


# ── build_topology — virtual clients ─────────────────────────────────────────

def test_topology_clients_created():
    site = build_topology(SIMPLE_BP, clients_per_ap=3)
    # 2 APs → 6 clients
    assert len(site.clients) == 6


def test_topology_client_ips_assigned():
    site = build_topology(SIMPLE_BP, clients_per_ap=2)
    for client in site.clients:
        assert client.ip_address not in ("", "0.0.0.0")


def test_topology_clients_have_valid_persona():
    site = build_topology(SIMPLE_BP, clients_per_ap=5)
    for client in site.clients:
        assert client.persona in PERSONAS, f"Unknown persona: {client.persona}"


def test_topology_client_macs_unique():
    site = build_topology(SIMPLE_BP, clients_per_ap=4)
    macs = [c.mac_address for c in site.clients]
    assert len(macs) == len(set(macs))


def test_topology_deterministic_with_seed():
    s1 = build_topology(SIMPLE_BP, seed=42, clients_per_ap=3)
    s2 = build_topology(SIMPLE_BP, seed=42, clients_per_ap=3)
    for c1, c2 in zip(s1.clients, s2.clients, strict=True):
        assert c1.persona == c2.persona
        assert c1.mac_address == c2.mac_address


def test_topology_different_seeds_may_differ():
    s1 = build_topology(SIMPLE_BP, seed=1,  clients_per_ap=10)
    s2 = build_topology(SIMPLE_BP, seed=99, clients_per_ap=10)
    personas1 = [c.persona for c in s1.clients]
    personas2 = [c.persona for c in s2.clients]
    # Different seeds should produce different persona sequences (probabilistically)
    assert personas1 != personas2


# ── build_topology — firewall rules ──────────────────────────────────────────

def test_topology_firewall_rules_parsed():
    site = build_topology(SIMPLE_BP)
    names = [r.name for r in site.firewall_rules]
    assert "block-iot-main" in names
    assert "allow-dns" in names


def test_topology_firewall_rule_fields():
    site = build_topology(SIMPLE_BP)
    block_rule = next(r for r in site.firewall_rules if r.name == "block-iot-main")
    assert block_rule.src_network == "iot"
    assert block_rule.dst_network == "main"
    assert block_rule.action == "block"

    dns_rule = next(r for r in site.firewall_rules if r.name == "allow-dns")
    assert dns_rule.protocol == "udp"
    assert dns_rule.dst_port == 53
    assert dns_rule.action == "allow"


# ── build_topology — default network fallback ────────────────────────────────

def test_topology_default_network_when_none():
    site = build_topology({"site": {"devices": []}})
    assert "default" in site.networks
    assert len(site.vlans) == 1


# ── FirewallEngine ────────────────────────────────────────────────────────────

def _engine(*rules: FirewallRule) -> FirewallEngine:
    return FirewallEngine(list(rules))


def test_firewall_default_allow():
    eng = _engine()
    allowed, rule = eng.evaluate(src_network="a", dst_network="b", protocol="tcp", dst_port=80)
    assert allowed is True
    assert rule is None


def test_firewall_block_matches():
    eng = _engine(
        FirewallRule("block-all", action="block"),
    )
    allowed, rule = eng.evaluate()
    assert allowed is False
    assert rule == "block-all"


def test_firewall_first_match_wins():
    eng = _engine(
        FirewallRule("allow-first", action="allow"),
        FirewallRule("block-second", action="block"),
    )
    allowed, _ = eng.evaluate()
    assert allowed is True


def test_firewall_src_network_filter():
    eng = _engine(
        FirewallRule("block-iot", src_network="iot", action="block"),
    )
    blocked, _ = eng.evaluate(src_network="iot")
    assert blocked is False

    allowed, _ = eng.evaluate(src_network="main")
    assert allowed is True


def test_firewall_dst_network_filter():
    eng = _engine(
        FirewallRule("block-servers", dst_network="servers", action="block"),
    )
    assert eng.evaluate(dst_network="servers")[0] is False
    assert eng.evaluate(dst_network="main")[0] is True


def test_firewall_protocol_filter():
    eng = _engine(
        FirewallRule("block-udp", protocol="udp", action="block"),
    )
    assert eng.evaluate(protocol="udp")[0] is False
    assert eng.evaluate(protocol="tcp")[0] is True


def test_firewall_dst_port_filter():
    eng = _engine(
        FirewallRule("block-telnet", dst_port=23, action="block"),
    )
    assert eng.evaluate(dst_port=23)[0] is False
    assert eng.evaluate(dst_port=22)[0] is True


def test_firewall_combined_match():
    eng = _engine(
        FirewallRule("block-iot-to-lan-smb", src_network="iot", dst_network="main",
                     protocol="tcp", dst_port=445, action="block"),
    )
    assert eng.evaluate(src_network="iot", dst_network="main", protocol="tcp", dst_port=445)[0] is False
    assert eng.evaluate(src_network="iot", dst_network="main", protocol="tcp", dst_port=80)[0] is True
    assert eng.evaluate(src_network="main", dst_network="iot", protocol="tcp", dst_port=445)[0] is True


# ── PERSONAS coverage ─────────────────────────────────────────────────────────

def test_all_personas_have_flows():
    for name, persona in PERSONAS.items():
        assert "flows" in persona, f"{name} missing 'flows'"
        assert isinstance(persona["flows"], list), f"{name} flows not a list"
        assert len(persona["flows"]) > 0, f"{name} has empty flows"


def test_all_persona_flows_have_app():
    for name, persona in PERSONAS.items():
        for i, flow in enumerate(persona["flows"]):
            assert "app" in flow, f"{name}[{i}] missing 'app'"
