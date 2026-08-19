"""Persistence for a virtual site.

Models hold state only. Anything that reasons about the network lives in
``netsim.services`` or in the framework-free ``simcore`` package.
"""

from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from simcore.catalog import CATALOG

STP_MODES = [("rstp", "RSTP"), ("stp", "STP (802.1D)"), ("disabled", "Disabled")]
CABLE_TYPES = [
    ("cat5e", "Cat5e"),
    ("cat6", "Cat6"),
    ("cat6a", "Cat6a"),
    ("dac", "DAC"),
    ("fibre", "Fibre"),
]
CLIENT_KINDS = [("wired", "Wired"), ("wireless", "Wireless")]
CLIENT_CATEGORIES = [
    ("workstation", "Workstation"),
    ("laptop", "Laptop"),
    ("phone", "Phone"),
    ("tablet", "Tablet"),
    ("tv", "TV / media"),
    ("server", "Server / NAS"),
    ("camera", "Camera"),
    ("printer", "Printer"),
    ("iot", "IoT"),
    ("voip", "VoIP phone"),
]
ENDPOINT_KINDS = [("client", "Client"), ("device", "Device"), ("internet", "Internet")]


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Site(TimestampedModel):
    """A virtual network. The console shows one site at a time."""

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    stp_mode = models.CharField(max_length=16, choices=STP_MODES, default="rstp")
    wan_download_mbps = models.PositiveIntegerField(default=1000)
    wan_upload_mbps = models.PositiveIntegerField(default=1000)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Network(TimestampedModel):
    """A VLAN / network as it appears under Settings in the UniFi console."""

    site = models.ForeignKey(Site, related_name="networks", on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    vlan_id = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(4094)]
    )
    subnet = models.CharField(max_length=64, default="192.168.1.0/24")
    purpose = models.CharField(max_length=32, default="corporate")
    isolated = models.BooleanField(default=False)

    class Meta:
        ordering = ["vlan_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "vlan_id"], name="unique_vlan_per_site"
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} (VLAN {self.vlan_id})"


class Device(TimestampedModel):
    """One piece of UniFi hardware placed into the site."""

    site = models.ForeignKey(Site, related_name="devices", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    model = models.CharField(max_length=64, help_text="Catalogue key, e.g. usw-pro-24-poe")
    mac = models.CharField(max_length=17, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    x = models.FloatField(default=0)
    y = models.FloatField(default=0)
    enabled = models.BooleanField(default=True)
    stp_enabled = models.BooleanField(default=True)
    stp_priority = models.PositiveIntegerField(default=32768)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.name} ({self.model})"

    @property
    def spec(self):
        return CATALOG[self.model]


class Port(TimestampedModel):
    """A physical port. Created from the catalogue when a device is added."""

    device = models.ForeignKey(Device, related_name="ports", on_delete=models.CASCADE)
    index = models.PositiveIntegerField()
    name = models.CharField(max_length=80, blank=True)
    enabled = models.BooleanField(default=True)
    poe_enabled = models.BooleanField(default=True)
    bpdu_guard = models.BooleanField(default=False)
    speed_override = models.PositiveIntegerField(null=True, blank=True)
    native_network = models.ForeignKey(
        Network, null=True, blank=True, on_delete=models.SET_NULL, related_name="ports"
    )

    class Meta:
        ordering = ["device_id", "index"]
        constraints = [
            models.UniqueConstraint(
                fields=["device", "index"], name="unique_port_index_per_device"
            )
        ]

    def __str__(self) -> str:
        return f"{self.device.name} {self.label}"

    @property
    def spec(self):
        return self.device.spec.ports_by_index[self.index]

    @property
    def label(self) -> str:
        return self.name or self.spec.label

    @property
    def sim_id(self) -> str:
        return f"{self.device_id}:{self.index}"


class Link(TimestampedModel):
    """A patch cable between two ports."""

    site = models.ForeignKey(Site, related_name="links", on_delete=models.CASCADE)
    a_port = models.OneToOneField(Port, related_name="link_a", on_delete=models.CASCADE)
    b_port = models.OneToOneField(Port, related_name="link_b", on_delete=models.CASCADE)
    cable = models.CharField(max_length=16, choices=CABLE_TYPES, default="cat6")
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.a_port} ↔ {self.b_port}"


class Client(TimestampedModel):
    """An endpoint hanging off a switch port or associated to an access point."""

    site = models.ForeignKey(Site, related_name="clients", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=16, choices=CLIENT_KINDS, default="wired")
    category = models.CharField(
        max_length=24, choices=CLIENT_CATEGORIES, default="workstation"
    )
    mac = models.CharField(max_length=17, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    port = models.ForeignKey(
        Port, null=True, blank=True, on_delete=models.SET_NULL, related_name="clients"
    )
    access_point = models.ForeignKey(
        Device, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="wireless_clients",
    )
    network = models.ForeignKey(
        Network, null=True, blank=True, on_delete=models.SET_NULL, related_name="clients"
    )
    down_mbps = models.FloatField(default=5)
    up_mbps = models.FloatField(default=1)
    rssi_dbm = models.IntegerField(default=-55)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Flow(TimestampedModel):
    """A synthetic traffic generator between two endpoints."""

    site = models.ForeignKey(Site, related_name="flows", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    enabled = models.BooleanField(default=True)
    protocol = models.CharField(max_length=8, default="tcp")
    mbps = models.FloatField(default=100)
    burstiness = models.FloatField(default=0.15)

    src_kind = models.CharField(max_length=16, choices=ENDPOINT_KINDS, default="client")
    src_client = models.ForeignKey(
        Client, null=True, blank=True, on_delete=models.CASCADE, related_name="flows_out"
    )
    src_device = models.ForeignKey(
        Device, null=True, blank=True, on_delete=models.CASCADE, related_name="flows_out"
    )
    dst_kind = models.CharField(max_length=16, choices=ENDPOINT_KINDS, default="internet")
    dst_client = models.ForeignKey(
        Client, null=True, blank=True, on_delete=models.CASCADE, related_name="flows_in"
    )
    dst_device = models.ForeignKey(
        Device, null=True, blank=True, on_delete=models.CASCADE, related_name="flows_in"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def endpoint(self, side: str) -> tuple[str, str]:
        kind = getattr(self, f"{side}_kind")
        if kind == "internet":
            return "internet", "internet"
        client = getattr(self, f"{side}_client_id")
        device = getattr(self, f"{side}_device_id")
        if kind == "client" and client:
            return "client", str(client)
        if kind == "device" and device:
            return "device", str(device)
        return kind, ""
