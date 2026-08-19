"""PoE delivery, budgets and what happens downstream when power is lost."""

from simcore.builder import SiteBuilder
from simcore.engine import simulate


def codes(result) -> set[str]:
    return {issue.code for issue in result.issues}


def base(switch_model: str = "usw-pro-24-poe"):
    b = SiteBuilder()
    b.device("gw", "udm-pro", "Gateway", stp_priority=4096)
    b.device("sw", switch_model, "Switch")
    b.link("gw", 3, "sw", 1)
    return b


def test_ap_on_a_poe_port_comes_up():
    b = base()
    b.device("ap", "u7-pro", "AP")
    b.link("sw", 2, "ap", 1)
    result = simulate(b.build())
    assert "ap" not in result.power.offline_device_ids
    assert result.power.delivered_w["ap"] == 21
    assert result.power.pse["sw"].used_w == 21


def test_ap_on_a_port_without_poe_never_boots():
    b = base("usw-24-g2")  # no PoE anywhere on this model
    b.device("ap", "u7-pro", "AP")
    b.link("sw", 2, "ap", 1)
    result = simulate(b.build())
    assert "power.no_pse" in codes(result)
    assert "ap" in result.power.offline_device_ids


def test_af_port_cannot_power_an_at_access_point():
    b = base()
    b.device("ap", "u6-lr", "Long Range AP")  # needs 802.3at
    b.device("flex", "usw-flex", "Flex Switch")
    b.link("sw", 2, "flex", 1)
    b.link("flex", 2, "ap", 1)  # Flex downlinks are 802.3af only
    result = simulate(b.build())
    assert "power.standard_insufficient" in codes(result)
    assert "ap" in result.power.offline_device_ids


def test_poe_budget_is_enforced():
    b = base("usw-lite-16-poe")  # 45 W budget
    for n in range(4):
        b.device(f"ap{n}", "u7-pro", f"AP {n}")  # 21 W each
        b.link("sw", 9 + n, f"ap{n}", 1)
    result = simulate(b.build())
    assert "power.budget_exceeded" in codes(result)
    assert result.power.pse["sw"].used_w == 84
    assert result.power.pse["sw"].utilisation > 1


def test_turning_poe_off_on_a_port_takes_the_device_down():
    b = base()
    b.device("ap", "u7-pro", "AP")
    b.link("sw", 2, "ap", 1)
    site = b.build()
    switch = next(d for d in site.devices if d.id == "sw")
    next(p for p in switch.ports if p.index == 2).poe_enabled = False
    result = simulate(site)
    assert "power.poe_disabled" in codes(result)
    assert "ap" in result.power.offline_device_ids


def test_losing_a_poe_switch_takes_its_downstream_devices_with_it():
    b = base()
    b.device("flex", "usw-flex", "Flex Switch")  # itself PoE powered, needs 802.3bt
    b.device("cam", "g5-bullet", "Yard Camera")
    b.link("sw", 17, "flex", 1, link_id="flex-uplink")  # PoE++ port
    b.link("flex", 2, "cam", 1)
    site = b.build()
    healthy = simulate(site)
    assert not healthy.power.offline_device_ids

    next(link for link in site.links if link.id == "flex-uplink").enabled = False
    broken = simulate(site)
    assert {"flex", "cam"} <= broken.power.offline_device_ids
    assert "power.upstream_offline" in codes(broken)


def test_an_unpatched_access_point_reports_no_power_source():
    b = base()
    b.device("ap", "u7-pro", "AP")
    result = simulate(b.build())
    assert "power.not_connected" in codes(result)
    assert "ap" in result.power.offline_device_ids
