"""PoE budget and powered-device analysis.

Runs before spanning tree, because a device that never gets power is not on the
network at all — and the switch it was daisy-chained to goes with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simcore.catalog import poe_meets
from simcore.issues import Issue, Severity, Subject
from simcore.topology import Topology


@dataclass
class PseUsage:
    device_id: str
    budget_w: float
    used_w: float
    powered_device_ids: list[str] = field(default_factory=list)

    @property
    def utilisation(self) -> float:
        return self.used_w / self.budget_w if self.budget_w else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "budget_w": round(self.budget_w, 1),
            "used_w": round(self.used_w, 1),
            "utilisation": round(self.utilisation, 4),
            "powered_device_ids": self.powered_device_ids,
        }


@dataclass
class PowerResult:
    offline_device_ids: set[str]
    delivered_w: dict[str, float]
    pse: dict[str, PseUsage]
    issues: list[Issue]

    def to_dict(self) -> dict[str, Any]:
        return {
            "offline_device_ids": sorted(self.offline_device_ids),
            "delivered_w": {k: round(v, 1) for k, v in self.delivered_w.items()},
            "pse": {k: v.to_dict() for k, v in self.pse.items()},
        }


def compute(topo: Topology) -> PowerResult:
    issues: list[Issue] = []
    offline: set[str] = set()
    delivered: dict[str, float] = {}
    pse: dict[str, PseUsage] = {
        d.id: PseUsage(device_id=d.id, budget_w=d.spec.poe_budget_w, used_w=0.0)
        for d in topo.site.devices
        if d.spec.poe_budget_w > 0
    }

    # A PoE switch that loses power takes its downstream devices with it, so keep
    # re-evaluating until the set of offline devices stops growing.
    for _ in range(len(topo.site.devices) + 1):
        changed = _pass(topo, offline, delivered, pse, issues)
        if not changed:
            break

    for usage in pse.values():
        device = topo.devices[usage.device_id]
        if device.id in offline or usage.budget_w <= 0:
            continue
        if usage.used_w > usage.budget_w:
            issues.append(
                Issue(
                    code="power.budget_exceeded",
                    severity=Severity.CRITICAL,
                    category="power",
                    title=f"{device.name} is over its PoE budget",
                    detail=(
                        f"Connected devices are asking for {usage.used_w:.1f} W but "
                        f"{device.name} can only deliver {usage.budget_w:.0f} W. Real "
                        "hardware sheds power on the highest-numbered ports first."
                    ),
                    recommendation=(
                        "Move some powered devices to another switch, or fit a switch "
                        "with a larger PoE budget."
                    ),
                    subjects=(Subject("device", device.id, device.name),),
                    meta={"used_w": round(usage.used_w, 1), "budget_w": usage.budget_w},
                )
            )
        elif usage.utilisation >= 0.9:
            issues.append(
                Issue(
                    code="power.budget_high",
                    severity=Severity.WARNING,
                    category="power",
                    title=f"{device.name} PoE budget is {usage.utilisation * 100:.0f}% used",
                    detail=(
                        f"{usage.used_w:.1f} W of {usage.budget_w:.0f} W is committed. "
                        "There is little headroom for another access point."
                    ),
                    recommendation="Plan the next powered device onto a different switch.",
                    subjects=(Subject("device", device.id, device.name),),
                )
            )
    return PowerResult(
        offline_device_ids=offline, delivered_w=delivered, pse=pse, issues=issues
    )


def _pass(
    topo: Topology,
    offline: set[str],
    delivered: dict[str, float],
    pse: dict[str, PseUsage],
    issues: list[Issue],
) -> bool:
    changed = False
    for usage in pse.values():
        usage.used_w = 0.0
        usage.powered_device_ids = []
    delivered.clear()
    reported: set[str] = set()

    for device in topo.site.devices:
        spec = device.spec
        if not spec.needs_poe or not device.enabled:
            continue
        inlet = next((p for p in device.ports if p.spec.poe_in), None)
        problem = _fault(topo, device.id, inlet, offline)
        if problem is not None:
            if device.id not in offline:
                offline.add(device.id)
                changed = True
            if problem[0] not in reported:
                reported.add(problem[0])
                issues.append(problem[1])
            continue
        if device.id in offline:
            offline.discard(device.id)
            changed = True
        assert inlet is not None
        peer = topo.peer_port(inlet.id)
        assert peer is not None
        draw = spec.power_draw_w
        delivered[device.id] = draw
        supplier = pse.get(peer.device_id)
        if supplier is not None:
            supplier.used_w += draw
            supplier.powered_device_ids.append(device.id)
        if peer.spec.poe_max_w and draw > peer.spec.poe_max_w:
            issues.append(
                Issue(
                    code="power.port_overdraw",
                    severity=Severity.WARNING,
                    category="power",
                    title=f"{device.name} draws more than its port can supply",
                    detail=(
                        f"{device.name} needs {draw:.1f} W but "
                        f"{topo.devices[peer.device_id].name} {peer.label} tops out at "
                        f"{peer.spec.poe_max_w:.1f} W."
                    ),
                    recommendation="Move it to a PoE++ port or use a power injector.",
                    subjects=(
                        Subject("device", device.id, device.name),
                        Subject("port", peer.id, peer.label),
                    ),
                )
            )
    return changed


def _fault(
    topo: Topology, device_id: str, inlet: Any, offline: set[str]
) -> tuple[str, Issue] | None:
    device = topo.devices[device_id]
    subject = (Subject("device", device.id, device.name),)
    if inlet is None:  # pragma: no cover - catalogue guarantees an inlet
        return None
    link = topo.link_of(inlet.id)
    if link is None or not link.enabled:
        return (
            f"unpowered:{device.id}",
            Issue(
                code="power.not_connected",
                severity=Severity.WARNING,
                category="power",
                title=f"{device.name} has no power source",
                detail=(
                    f"{device.name} is powered over ethernet but its {inlet.label} port "
                    "is not patched into anything, so it is offline."
                ),
                recommendation="Patch it into a PoE port on a switch.",
                subjects=subject,
            ),
        )
    peer = topo.peer_port(inlet.id)
    if peer is None:
        return None
    upstream = topo.devices[peer.device_id]
    if upstream.id in offline or not upstream.enabled:
        return (
            f"upstream-down:{device.id}",
            Issue(
                code="power.upstream_offline",
                severity=Severity.CRITICAL,
                category="power",
                title=f"{device.name} lost power with {upstream.name}",
                detail=(
                    f"{upstream.name} supplies PoE to {device.name} and is itself "
                    "offline, so everything downstream of it is dark."
                ),
                recommendation=f"Restore power to {upstream.name}.",
                subjects=(*subject, Subject("device", upstream.id, upstream.name)),
            ),
        )
    if peer.spec.poe_out is None:
        return (
            f"no-pse:{device.id}",
            Issue(
                code="power.no_pse",
                severity=Severity.CRITICAL,
                category="power",
                title=f"{device.name} is on a port that does not supply PoE",
                detail=(
                    f"{upstream.name} {peer.label} has no PoE injector, so "
                    f"{device.name} never boots."
                ),
                recommendation=(
                    f"Move {device.name} to a PoE port, or add a power injector."
                ),
                subjects=(*subject, Subject("port", peer.id, peer.label)),
            ),
        )
    if not peer.poe_enabled:
        return (
            f"poe-off:{device.id}",
            Issue(
                code="power.poe_disabled",
                severity=Severity.CRITICAL,
                category="power",
                title=f"PoE is switched off on {upstream.name} {peer.label}",
                detail=f"{device.name} is cabled correctly but the port is not sourcing power.",
                recommendation=f"Enable PoE on {upstream.name} {peer.label}.",
                subjects=(*subject, Subject("port", peer.id, peer.label)),
            ),
        )
    if not poe_meets(peer.spec.poe_out, inlet.spec.poe_in):
        return (
            f"poe-standard:{device.id}",
            Issue(
                code="power.standard_insufficient",
                severity=Severity.CRITICAL,
                category="power",
                title=f"{device.name} needs {inlet.spec.poe_in}",
                detail=(
                    f"{upstream.name} {peer.label} only offers {peer.spec.poe_out}. "
                    f"{device.name} will not come up on this port."
                ),
                recommendation=(
                    f"Use a {inlet.spec.poe_in} port or a matching power injector."
                ),
                subjects=(*subject, Subject("port", peer.id, peer.label)),
            ),
        )
    return None
