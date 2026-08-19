"""Traffic placement, capacity and the effect of blocked ports."""

from simcore.builder import SiteBuilder, demo_site
from simcore.engine import simulate


def codes(result) -> set[str]:
    return {issue.code for issue in result.issues}


def office(wan_down: float = 1000):
    b = SiteBuilder(wan_download_mbps=wan_down, wan_upload_mbps=wan_down)
    b.device("gw", "udm-pro", "Gateway", stp_priority=4096)
    b.device("core", "usw-pro-24-poe", "Core")
    b.device("edge", "usw-lite-16-poe", "Edge")
    b.link("gw", 11, "core", 25, cable="dac", link_id="gw-core")
    b.link("core", 1, "edge", 1, link_id="core-edge")
    return b


def test_client_traffic_lands_on_the_path_to_the_gateway():
    b = office()
    b.client("c1", "Desk PC", kind="wired", port_id="edge:5", down_mbps=200, up_mbps=20)
    result = simulate(b.build())
    assert result.traffic.links["core-edge"].load_mbps > 100
    assert result.traffic.links["gw-core"].load_mbps > 100
    assert result.traffic.wan["download_mbps"] > 100


def test_a_blocked_link_carries_nothing():
    b = office()
    b.link("core", 2, "edge", 2, link_id="redundant")
    b.client("c1", "Desk PC", kind="wired", port_id="edge:5", down_mbps=400, up_mbps=20)
    result = simulate(b.build())
    blocked = next(iter(result.stp.blocked_link_ids))
    assert blocked not in result.traffic.links
    active = result.traffic.links["core-edge" if blocked == "redundant" else "redundant"]
    assert active.load_mbps > 100


def test_a_saturated_uplink_throttles_the_flows_crossing_it():
    b = office(wan_down=10000)
    for n in range(6):
        b.client(f"c{n}", f"Desk {n}", kind="wired", port_id=f"edge:{n + 5}",
                 down_mbps=400, up_mbps=20)
    result = simulate(b.build())
    uplink = result.traffic.links["core-edge"]
    assert uplink.offered_utilisation > 1.0
    assert uplink.load_mbps <= uplink.capacity_mbps + 0.01
    assert "capacity.link_saturated" in codes(result)
    congested = [f for f in result.traffic.flows if f.status == "congested"]
    assert congested and all(f.loss_pct > 0 for f in congested)


def test_the_wan_circuit_is_a_bottleneck_of_its_own():
    b = office(wan_down=100)
    b.client("c1", "Streaming box", kind="wired", port_id="edge:5",
             down_mbps=400, up_mbps=5)
    result = simulate(b.build())
    assert result.traffic.wan["download_mbps"] <= 100.01
    assert "capacity.wan_download_saturated" in codes(result)


def test_a_flow_between_two_clients_stays_on_the_lan():
    b = office()
    b.client("nas", "NAS", kind="wired", port_id="core:5", down_mbps=0, up_mbps=0)
    b.client("pc", "Desk PC", kind="wired", port_id="edge:5", down_mbps=0, up_mbps=0)
    b.flow("f1", "Restore from NAS", src_kind="client", src_id="nas",
           dst_kind="client", dst_id="pc", mbps=300)
    result = simulate(b.build())
    flow = next(f for f in result.traffic.flows if f.id == "flow:f1")
    assert flow.path_device_ids == ["core", "edge"]
    assert result.traffic.wan["download_mbps"] == 0
    assert result.traffic.links["core-edge"].load_mbps > 250


def test_wireless_clients_load_the_access_point_radio():
    b = office()
    b.device("ap", "u6-lite", "Lobby AP")  # 1.5 Gbps PHY, ~750 Mbps usable
    b.link("edge", 9, "ap", 1)
    for n in range(10):
        b.client(f"w{n}", f"Phone {n}", kind="wireless", ap_id="ap",
                 down_mbps=70, up_mbps=10)
    result = simulate(b.build())
    radio = result.traffic.wireless["ap"]
    assert radio["client_count"] == 10
    assert radio["utilisation"] >= 0.85
    assert "capacity.wireless_saturated" in codes(result)


def test_a_flow_with_no_path_is_reported_as_dropped():
    b = office()
    b.client("pc", "Desk PC", kind="wired", port_id="edge:5", down_mbps=10, up_mbps=1)
    site = b.build()
    next(link for link in site.links if link.id == "core-edge").enabled = False
    result = simulate(site)
    assert "traffic.no_path" in codes(result)
    assert any(f.status == "dropped" for f in result.traffic.flows)


def test_history_is_deterministic_for_a_given_moment():
    site = demo_site()
    first = simulate(site, t=1000.0)
    second = simulate(site, t=1000.0)
    assert first.traffic.history == second.traffic.history
    assert len(first.traffic.history) == 60


def test_demo_site_is_healthy_enough_to_explore():
    result = simulate(demo_site(), t=0)
    assert result.health_status != "critical"
    assert result.traffic.wan["download_mbps"] > 0
    assert len(result.to_dict()["devices"]) == 5
