"""Traffic models.

- ``TrafficProfile`` — declarative, authored in YAML (like a Blueprint).
  Stored both as raw source and parsed JSON. Materialisation into actual
  flow records happens in the worker's Traffic Simulator component
  (Phase 3), which reads parsed_json at runtime.
- ``FlowRecord`` — one simulated flow. Worker-owned writes via
  SQLAlchemy async; Django reads for the UI.
"""

from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


class TrafficProfile(BaseModel):
    """A reusable definition of simulated traffic — personas, rates, apps.

    Associated to fleets via ``FleetTrafficAssignment`` (future); for the
    Phase 2 MVP the assignment is implicit via the profile's parsed_json
    ``applies_to`` clause and runtime evaluation.
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default="")
    source_yaml = models.TextField()
    parsed_json = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"


class FlowRecord(BaseModel):
    PROTOCOL_TCP = "tcp"
    PROTOCOL_UDP = "udp"
    PROTOCOL_ICMP = "icmp"
    PROTOCOL_CHOICES = [
        (PROTOCOL_TCP, "TCP"),
        (PROTOCOL_UDP, "UDP"),
        (PROTOCOL_ICMP, "ICMP"),
    ]

    device = models.ForeignKey(
        "devices.VirtualDevice", on_delete=models.CASCADE, related_name="flows"
    )
    protocol = models.CharField(max_length=8, choices=PROTOCOL_CHOICES)
    src_ip = models.GenericIPAddressField()
    dst_ip = models.GenericIPAddressField()
    src_port = models.PositiveIntegerField(null=True, blank=True)
    dst_port = models.PositiveIntegerField(null=True, blank=True)
    bytes_tx = models.BigIntegerField(default=0)
    bytes_rx = models.BigIntegerField(default=0)
    application = models.CharField(max_length=64, blank=True, default="")
    reported_at = models.DateTimeField(db_index=True)
    blocked = models.BooleanField(default=False)

    class Meta:
        ordering = ("-reported_at",)
