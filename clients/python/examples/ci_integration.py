"""Worked example — drives UVL from a CI pipeline.

Mirrors the snippet in the project README. Run against a live stack::

    UVL_BASE=https://uvl.example.com \
    UVL_EMAIL=admin@uvl.local \
    UVL_PASSWORD=devpassword \
    UVL_CONTROLLER_ID=... \
    UVL_BLUEPRINT_ID=... \
    python ci_integration.py
"""
from __future__ import annotations

import asyncio
import os
import sys

from uvl_client import UVLClient, UVLTimeout


async def main() -> int:
    base = os.environ["UVL_BASE"]
    email = os.environ["UVL_EMAIL"]
    password = os.environ["UVL_PASSWORD"]
    controller_id = os.environ["UVL_CONTROLLER_ID"]
    blueprint_id = os.environ.get("UVL_BLUEPRINT_ID")
    run_id = os.environ.get("GITHUB_RUN_ID") or "local"

    async with UVLClient(base, email=email, password=password, verify_tls=False) as uvl:
        health = await uvl.health()
        print(f"backend: {health}")

        fleet = await uvl.fleets.create(
            name=f"ci-{run_id}",
            controller_target_id=controller_id,
            blueprint_id=blueprint_id,
            model_code=None if blueprint_id else "USW24P250",
            device_count=None if blueprint_id else 3,
        )
        print(f"fleet created: {fleet['id']} (state={fleet['state']})")

        try:
            # In full Phase 2 this would wait for "active". The supervisor's
            # ramping is still stubbed, so we just confirm the fleet was
            # provisioned and the devices are pending.
            fleet = await uvl.fleets.wait_for_state(
                fleet["id"], "ramping", timeout=30
            )
        except UVLTimeout as exc:
            print(f"warning: {exc}")

        devices = await uvl.devices.list(fleet_id=fleet["id"])
        print(f"{devices['count']} device(s) provisioned under fleet {fleet['id']}")

        await uvl.fleets.teardown(fleet["id"])
        print("teardown accepted")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
