#!/usr/bin/env python3
"""Prompt-start preflight wrapper for /nextlens-bugfix."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Lens preflight before nextlens bugfix flow.")
    parser.add_argument("--caller", default="nextlens-bugfix")
    parser.add_argument("--project-root", default=".")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = Path(args.project_root).resolve()
    script = root / "skills" / "lens-preflight" / "scripts" / "lens_preflight.py"

    if not script.exists():
        print(
            "[LENS:PREFLIGHT] FAIL - missing preflight script at "
            f"{script.as_posix()}",
            file=sys.stderr,
        )
        return 1

    command = [sys.executable, str(script), str(root)]
    result = subprocess.run(command)

    if result.returncode != 0:
        print(
            "[LENS:PREFLIGHT] FAIL - blocked preflight for caller "
            f"{args.caller}",
            file=sys.stderr,
        )

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
