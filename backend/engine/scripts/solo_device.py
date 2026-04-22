"""Phase 0 smoke test — stand up a single VirtualDevice against a controller.

Usage:

    python -m engine.scripts.solo_device \\
        --controller https://192.168.1.50 \\
        --insecure \\
        --model USW24P250 \\
        --mac 02:00:00:ab:cd:ef

Phase 0 status: prints the flow it *would* execute. The inform protocol
codec is not yet implemented, so this does not transmit anything. Once
pcaps land, this script becomes the exit-criteria smoke test:

    - Device appears as "pending" in the controller.
    - User adopts via the controller UI.
    - Script maintains steady heartbeat for >= 30 minutes.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import secrets

from engine.device import VirtualDevice, VirtualDeviceSpec

log = logging.getLogger("uvl.engine.scripts.solo_device")


def _default_mac() -> str:
    b = [0x02, 0x00, 0x00, *secrets.token_bytes(3)]
    return ":".join(f"{x:02x}" for x in b)


def _default_serial(model: str) -> str:
    return f"{model}-{secrets.token_hex(6).upper()}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="UVL solo device smoke test (Phase 0)")
    p.add_argument("--controller", required=True, help="Inform URL, e.g. https://192.168.1.50")
    p.add_argument("--insecure", action="store_true", help="Skip TLS verification")
    p.add_argument("--model", default="USW24P250", help="Device model code")
    p.add_argument("--mac", default=None, help="Override MAC (default: random LAA)")
    p.add_argument("--serial", default=None, help="Override serial (default: derived from model)")
    p.add_argument("--firmware", default="8.3.42", help="Firmware version to report")
    return p.parse_args()


async def _run(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    spec = VirtualDeviceSpec(
        mac_address=args.mac or _default_mac(),
        serial_number=args.serial or _default_serial(args.model),
        model_code=args.model,
        firmware_version=args.firmware,
        controller_inform_url=args.controller,
        verify_tls=not args.insecure,
    )
    log.info(
        "solo_device.start  mac=%s serial=%s model=%s controller=%s",
        spec.mac_address,
        spec.serial_number,
        spec.model_code,
        spec.controller_inform_url,
    )

    device = VirtualDevice(spec)
    try:
        await device.connect()
        await device.heartbeat()
        log.info("solo_device.ok  state=%s", device.state.value)
        log.warning(
            "solo_device.note  inform protocol codec is stubbed; no bytes transmitted. "
            "Implement engine.protocol.codec once pcaps are available."
        )
        return 0
    except NotImplementedError as exc:
        log.error("solo_device.blocked  %s", exc)
        return 2
    except Exception:
        log.exception("solo_device.error")
        return 1


def main() -> None:
    args = parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
