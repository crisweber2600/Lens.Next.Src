#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Placeholder cleanup hook for Bottom-Up LENS setup.

Later setup stories may expand this into an installer cleanup routine. The scaffold
keeps the script present so the module follows BMad Builder multi-skill setup
conventions from the first story.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report legacy Bottom-Up LENS setup cleanup status.")
    parser.add_argument("--legacy-dir", default="")
    parser.add_argument("--module-code", default="bul")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    legacy_dir = Path(args.legacy_dir) if args.legacy_dir else None
    print(json.dumps({
        "status": "noop",
        "module_code": args.module_code,
        "legacy_dir": str(legacy_dir) if legacy_dir else None,
        "detail": "No legacy Bottom-Up LENS directories are removed by the scaffold placeholder.",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
