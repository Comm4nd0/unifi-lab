"""Replay a captured Wireshark pcap of a real inform exchange.

Used to bootstrap protocol implementation: we read a real device's inform
frames, decode them with our codec, and verify round-trip equality.

Phase 0 stub — once ``engine.protocol.codec`` is implemented, this script
iterates a .pcapng and dumps decoded frames as JSON.
"""

from __future__ import annotations

import argparse
import logging
import sys

log = logging.getLogger("uvl.engine.scripts.replay_pcap")


def main() -> None:
    p = argparse.ArgumentParser(description="Replay captured inform exchanges")
    p.add_argument("pcap", help="Path to .pcapng file")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO)
    log.info("replay_pcap.not_implemented  %s — awaiting engine.protocol.codec", args.pcap)
    sys.exit(2)


if __name__ == "__main__":
    main()
