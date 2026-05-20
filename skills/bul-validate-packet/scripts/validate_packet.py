#!/usr/bin/env python3
"""Read-only Bottom-Up LENS packet validator."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

try:  # pragma: no cover - direct script fallback
    from validation_contract import build_validation_result, validate_packet_dict
    from readiness_check import check_bmad_readiness
except ImportError:  # pragma: no cover
    from .validation_contract import build_validation_result, validate_packet_dict
    from .readiness_check import check_bmad_readiness

import sys

CREATE_SCRIPTS = Path(__file__).resolve().parents[1].parent / "bul-create-packet" / "scripts"
if str(CREATE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CREATE_SCRIPTS))
from path_guard import guard_path  # noqa: E402


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("packet must be a JSON object")
    return data


def validate_packet(packet: dict[str, Any]) -> dict[str, Any]:
    return build_validation_result(packet, check_bmad_readiness(packet))


def write_report_atomic(result: dict[str, Any], report_path: Path, reports_output_path: Path) -> Path:
    guard = guard_path(report_path, [reports_output_path], "reportPath")
    if guard["status"] != "pass":
        raise ValueError(guard["pathGuard"]["message"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(report_path.parent), delete=False) as handle:
        handle.write(payload)
        tmp_path = Path(handle.name)
    tmp_path.replace(report_path)
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Bottom-Up LENS packet without mutating it.")
    parser.add_argument("--packet", required=True, help="Packet or draft JSON path")
    parser.add_argument("--report", help="Optional report JSON path")
    parser.add_argument("--reports-output-path", help="Allowed reports root when --report is supplied")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet_path = Path(args.packet).expanduser().resolve()
    packet = load_json(packet_path)
    result = validate_packet(packet)
    result["packetSource"] = str(packet_path)

    if args.report:
        if not args.reports_output_path:
            raise SystemExit("--reports-output-path is required when --report is supplied")
        report_path = write_report_atomic(result, Path(args.report).expanduser().resolve(), Path(args.reports_output_path).expanduser().resolve())
        result["reportPath"] = str(report_path)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["packetValid"]["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
