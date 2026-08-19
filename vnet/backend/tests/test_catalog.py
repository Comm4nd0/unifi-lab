from simcore.catalog import CATALOG, media_compatible, poe_meets


def test_every_model_expands_to_numbered_ports():
    for spec in CATALOG:
        assert spec.ports, f"{spec.key} has no ports"
        indexes = [p.index for p in spec.ports]
        assert indexes == list(range(1, len(indexes) + 1))
        assert len({p.label for p in spec.ports}) == len(spec.ports)


def test_pro_24_poe_layout():
    spec = CATALOG["usw-pro-24-poe"]
    assert spec.port_count == 26
    assert spec.ports[0].label == "Port 1"
    assert spec.ports[23].label == "Port 24"
    assert spec.ports[24].media == "sfp+"
    assert spec.ports[24].speed_mbps == 10000
    assert spec.ports[16].poe_out == "802.3bt"
    assert spec.poe_budget_w == 400


def test_udm_pro_separates_wan_from_lan():
    spec = CATALOG["udm-pro"]
    roles = {p.label: p.role for p in spec.ports}
    assert roles["WAN"] == "wan"
    assert roles["SFP+ WAN"] == "wan"
    assert roles["Port 1"] == "lan"


def test_access_points_declare_their_power_needs():
    ap = CATALOG["u7-pro"]
    assert ap.needs_poe
    assert ap.poe_in == "802.3at"
    assert ap.ports[0].speed_mbps == 2500


def test_media_and_poe_rules():
    assert media_compatible("sfp+", "sfp")
    assert not media_compatible("rj45", "sfp+")
    assert poe_meets("802.3bt", "802.3at")
    assert not poe_meets("802.3af", "802.3at")
    assert not poe_meets(None, "802.3af")
