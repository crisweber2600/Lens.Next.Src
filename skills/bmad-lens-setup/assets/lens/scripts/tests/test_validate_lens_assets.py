from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[6]
VALIDATOR = REPO_ROOT / "skills/bmad-lens-setup/assets/lens/scripts/validate_lens_assets.py"


def test_validate_lens_assets_passes_for_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR), "--module-root", str(REPO_ROOT)],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    assert payload == {"status": "pass", "findings": []}
