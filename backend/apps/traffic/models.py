"""FlowRecord — simulated traffic flow reported to the controller.

Worker-owned writes via SQLAlchemy async; Django reads only for UI/admin.
"""

from __future__ import annotations

from django.db import models

from apps.common.models import BaseModel


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
