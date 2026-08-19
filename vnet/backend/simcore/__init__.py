"""Pure-python simulation core for UniFi Virtual Lab.

This package has no Django (or any other framework) dependency. It takes a
declarative description of a site — devices, ports, cables, clients and traffic
flows — and returns everything the console needs to draw: spanning tree state,
per-link load, PoE budgets and the list of problems it found.
"""

from simcore.catalog import CATALOG, DeviceSpec, PortSpec
from simcore.engine import SimulationResult, simulate
from simcore.issues import Issue, Severity
from simcore.topology import SimClient, SimDevice, SimFlow, SimLink, SimPort, SimSite

__all__ = [
    "CATALOG",
    "DeviceSpec",
    "Issue",
    "PortSpec",
    "Severity",
    "SimClient",
    "SimDevice",
    "SimFlow",
    "SimLink",
    "SimPort",
    "SimSite",
    "SimulationResult",
    "simulate",
]
