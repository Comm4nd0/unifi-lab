"""Ready-made topologies so a fresh install has something to look at."""

from __future__ import annotations

from django.db import transaction

from netsim.models import Client, Flow, Network, Port, Site
from netsim.services import create_device, create_link


@transaction.atomic
def seed_demo_site(name: str = "Chiltern View") -> Site:
    """A small farm office: gateway, core, access switch, two APs, a few clients.

    Deliberately includes one redundant fibre run between the core and the
    access switch so RSTP has a port to block on the first simulation.
    """
    from netsim.services import _unique_site_name

    site = Site.objects.create(
        name=_unique_site_name(name),
        description="Example site — gateway, core, access layer and two APs.",
        wan_download_mbps=900,
        wan_upload_mbps=110,
    )
    Network.objects.create(site=site, name="Default", vlan_id=1, subnet="10.0.0.0/24")
    Network.objects.create(
        site=site, name="IoT", vlan_id=20, subnet="10.0.20.0/24", purpose="iot", isolated=True
    )

    gw = create_device(site, "udm-pro", "Dream Machine Pro", x=0, y=-220, stp_priority=4096)
    core = create_device(site, "usw-pro-24-poe", "Core Switch", x=0, y=0)
    access = create_device(site, "usw-lite-16-poe", "Workshop Switch", x=-320, y=220)
    ap_office = create_device(site, "u7-pro", "Office AP", x=260, y=220)
    ap_barn = create_device(site, "u6-lr", "Barn AP", x=-120, y=430)

    def port(device, index):
        return Port.objects.get(device=device, index=index)

    create_link(site, port(gw, 11), port(core, 25), cable="dac")
    create_link(site, port(core, 1), port(access, 1), cable="cat6")
    create_link(site, port(core, 2), port(access, 15), cable="cat6")  # redundant path
    create_link(site, port(core, 17), port(ap_office, 1), cable="cat6")
    create_link(site, port(access, 9), port(ap_barn, 1), cable="cat6")

    laptop = Client.objects.create(
        site=site, name="Marco's Laptop", kind="wireless", category="laptop",
        ip="10.0.0.51", access_point=ap_office, down_mbps=45, up_mbps=8, rssi_dbm=-52,
    )
    nas = Client.objects.create(
        site=site, name="Workshop NAS", kind="wired", category="server",
        ip="10.0.0.60", port=port(access, 2), down_mbps=20, up_mbps=60,
    )
    Client.objects.create(
        site=site, name="Yard Camera", kind="wired", category="camera",
        ip="10.0.0.70", port=port(core, 5), down_mbps=2, up_mbps=12,
    )
    Client.objects.create(
        site=site, name="Farm Office iPad", kind="wireless", category="tablet",
        ip="10.0.0.52", access_point=ap_barn, down_mbps=15, up_mbps=3, rssi_dbm=-68,
    )

    Flow.objects.create(
        site=site, name="Nightly NAS backup", mbps=180,
        src_kind="client", src_client=nas, dst_kind="client", dst_client=laptop,
    )
    Flow.objects.create(
        site=site, name="Camera upload to cloud", mbps=25, protocol="udp",
        src_kind="client", src_client=nas, dst_kind="internet",
    )
    return site
