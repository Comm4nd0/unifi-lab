"""Spanning tree behaviour — the part of the lab people actually come for."""

from simcore.builder import SiteBuilder
from simcore.engine import simulate


def codes(result) -> set[str]:
    return {issue.code for issue in result.issues}


def build_ring():
    """Three switches in a triangle behind a gateway."""
    b = SiteBuilder()
    b.device("gw", "udm-pro", "Gateway", stp_priority=4096)
    b.device("sw1", "usw-pro-24-poe", "Switch 1")
    b.device("sw2", "usw-pro-24-poe", "Switch 2")
    b.device("sw3", "usw-pro-24-poe", "Switch 3")
    b.link("gw", 11, "sw1", 25, cable="dac", link_id="gw-sw1")
    b.link("sw1", 1, "sw2", 1, link_id="sw1-sw2")
    b.link("sw2", 2, "sw3", 1, link_id="sw2-sw3")
    b.link("sw3", 2, "sw1", 2, link_id="sw3-sw1")
    return b.build()


def test_simple_tree_has_no_blocked_ports():
    b = SiteBuilder()
    b.device("gw", "udm-pro", "Gateway", stp_priority=4096)
    b.device("sw", "usw-24-poe", "Switch")
    b.device("ap", "u7-pro", "AP")
    b.link("gw", 3, "sw", 1)
    b.link("sw", 2, "ap", 1)
    result = simulate(b.build())
    assert not result.stp.blocked_link_ids
    assert not result.stp.loops
    assert "stp.loop_active" not in codes(result)
    assert result.health_status in ("ok", "warning")


def test_ring_blocks_exactly_one_port_and_stays_loop_free():
    result = simulate(build_ring())
    assert len(result.stp.blocked_link_ids) == 1
    assert result.stp.loops == []
    assert "stp.port_blocked" in codes(result)
    # Every switch still reaches the root.
    assert all(b.root_device_id == "gw" for b in result.stp.bridges.values())


def test_root_bridge_is_the_lowest_priority():
    result = simulate(build_ring())
    assert result.stp.root_device_ids == ["gw"]
    assert result.stp.bridges["gw"].is_root
    assert result.stp.bridges["sw2"].root_path_cost > 0


def test_blocked_link_recovers_when_the_active_path_fails():
    site = build_ring()
    before = simulate(site)
    blocked = next(iter(before.stp.blocked_link_ids))
    # Pull the cable on one of the forwarding links in the ring.
    victim = next(
        link
        for link in site.links
        if link.id not in ("gw-sw1", blocked) and link.id in before.stp.active_link_ids
    )
    victim.enabled = False
    after = simulate(site)
    assert blocked in after.stp.active_link_ids
    assert not after.stp.loops


def test_ap_patched_twice_into_one_switch_is_blocked_not_looped():
    """The switch sees its own BPDUs come back and puts one port into backup."""
    b = SiteBuilder()
    b.device("gw", "udm-pro", "Gateway", stp_priority=4096)
    b.device("sw", "usw-24-poe", "Switch")
    b.device("ap", "uap-ac-pro", "Reception AP")  # no STP, two ports
    b.link("gw", 3, "sw", 1)
    b.link("sw", 2, "ap", 1, link_id="ap-a")
    b.link("sw", 3, "ap", 2, link_id="ap-b")  # both AP ports into the same switch
    result = simulate(b.build())
    assert result.stp.loops == []
    assert len(result.stp.blocked_link_ids) == 1
    roles = {result.stp.ports["sw:2"].role, result.stp.ports["sw:3"].role}
    assert roles == {"designated", "backup"}
    assert "stp.daisy_chained_ap" in codes(result)


def test_loop_between_switches_with_stp_off_is_critical():
    """Two unmanaged desk switches patched together twice: nothing can block."""
    b = SiteBuilder()
    b.device("gw", "udm-pro", "Gateway", stp_priority=4096)
    b.device("sw1", "usw-24-poe", "Desk Switch 1", stp_enabled=False)
    b.device("sw2", "usw-24-poe", "Desk Switch 2", stp_enabled=False)
    b.link("gw", 3, "sw1", 1)
    b.link("sw1", 2, "sw2", 1, link_id="loop-a")
    b.link("sw1", 3, "sw2", 2, link_id="loop-b")
    result = simulate(b.build())
    assert "stp.loop_active" in codes(result)
    assert "stp.disabled_on_device" in codes(result)
    assert result.health_status == "critical"
    assert {"loop-a", "loop-b"} <= result.stp.active_link_ids


def test_a_live_loop_saturates_every_link_in_it():
    b = SiteBuilder()
    b.device("gw", "udm-pro", "Gateway", stp_priority=4096)
    b.device("sw1", "usw-24-poe", "Desk Switch 1", stp_enabled=False)
    b.device("sw2", "usw-24-poe", "Desk Switch 2", stp_enabled=False)
    b.link("gw", 3, "sw1", 1)
    b.link("sw1", 2, "sw2", 1, link_id="loop-a")
    b.link("sw1", 3, "sw2", 2, link_id="loop-b")
    result = simulate(b.build())
    assert result.traffic.links["loop-a"].storm
    assert result.traffic.links["loop-a"].utilisation == 1.0
    assert "capacity.broadcast_storm" in codes(result)


def test_disabling_stp_leaves_the_ring_looping():
    site = build_ring()
    site.stp_mode = "disabled"
    result = simulate(site)
    assert "stp.disabled_with_redundancy" in codes(result)
    assert "stp.loop_active" in codes(result)
    assert not result.stp.blocked_link_ids


def test_stp_off_on_one_switch_is_flagged():
    site = build_ring()
    next(d for d in site.devices if d.id == "sw2").stp_enabled = False
    result = simulate(site)
    assert "stp.disabled_on_device" in codes(result)


def test_root_election_prefers_the_gateway_and_warns_otherwise():
    site = build_ring()
    next(d for d in site.devices if d.id == "gw").stp_priority = 32768
    next(d for d in site.devices if d.id == "sw1").stp_priority = 4096
    result = simulate(site)
    assert result.stp.root_device_ids == ["sw1"]
    assert "stp.root_not_core" in codes(result)


def test_equal_priorities_warn_that_mac_decides_the_root():
    site = build_ring()
    for device in site.devices:
        device.stp_priority = 32768
    result = simulate(site)
    assert "stp.priority_tie" in codes(result)


def test_bpdu_guard_err_disables_a_port_facing_a_switch():
    b = SiteBuilder()
    b.device("gw", "udm-pro", "Gateway", stp_priority=4096)
    b.device("sw1", "usw-24-poe", "Switch 1")
    b.device("sw2", "usw-24-poe", "Switch 2")
    b.link("gw", 3, "sw1", 1)
    b.link("sw1", 5, "sw2", 1, link_id="guarded")
    port = next(p for d in b.site.devices if d.id == "sw1" for p in d.ports if p.index == 5)
    port.bpdu_guard = True
    result = simulate(b.build())
    assert "stp.bpdu_guard_violation" in codes(result)
    assert result.stp.ports["sw1:5"].state == "err-disabled"
    assert "guarded" not in result.stp.active_link_ids


def test_a_cable_from_a_switch_into_itself_is_a_loop():
    b = SiteBuilder()
    b.device("gw", "udm-pro", "Gateway", stp_priority=4096)
    b.device("sw", "usw-24-poe", "Switch")
    b.link("gw", 3, "sw", 1)
    b.link("sw", 5, "sw", 6, link_id="self-loop")
    result = simulate(b.build())
    # STP puts one end into backup, so the self-patch must not stay forwarding.
    assert "self-loop" not in result.stp.active_link_ids or result.stp.loops


def test_legacy_stp_mode_reports_slow_convergence():
    site = build_ring()
    site.stp_mode = "stp"
    result = simulate(site)
    assert "stp.legacy_mode" in codes(result)
    assert result.stp.convergence_estimate_s > 25


def test_isolated_switch_is_reported():
    b = SiteBuilder()
    b.device("gw", "udm-pro", "Gateway", stp_priority=4096)
    b.device("sw1", "usw-24-poe", "Switch 1")
    b.device("sw2", "usw-24-poe", "Switch 2")
    b.link("gw", 3, "sw1", 1)
    b.link("sw1", 2, "sw2", 1, link_id="down-link").enabled = False
    result = simulate(b.build())
    assert "topology.isolated" in codes(result)
