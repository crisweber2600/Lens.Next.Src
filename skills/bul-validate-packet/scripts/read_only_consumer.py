#!/usr/bin/env python3
"""Read-only Bottom-Up LENS packet consumer for future reporting/handoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SAFE_FIELDS = ["packetId", "packetStatus", "provenance", "packetValid", "bmadReady", "identity", "selectedFeature"]
MUTATION_FIELDS = ["topologyPromotion", "landscapeWrite", "derivedGraphWrite", "featureYamlUpdate", "governancePublish"]


def consume_packet_state(packet: dict[str, Any], validation_result: dict[str, Any] | None = None) -> dict[str, Any]:
    state = {
        "packetId": packet.get("packetId"),
        "packetStatus": packet.get("packetStatus"),
        "provenance": packet.get("provenance"),
        "identity": packet.get("identity"),
        "selectedFeature": packet.get("selectedFeature"),
        "packetValid": (validation_result or {}).get("packetValid"),
        "bmadReady": (validation_result or {}).get("bmadReady"),
        "readOnly": True,
        "mutatesPacketState": False,
        "promotesTopology": False,
        "safeFields": SAFE_FIELDS,
        "forbiddenMutationFields": MUTATION_FIELDS,
    }
    return state


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read packet state without mutating packet or topology.")
    parser.add_argument("--packet", required=True)
    parser.add_argument("--validation-result")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validation = load_json(Path(args.validation_result)) if args.validation_result else None
    print(json.dumps(consume_packet_state(load_json(Path(args.packet)), validation), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
