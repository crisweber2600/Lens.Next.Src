from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parent.parent / "downstream_salmon_landscape.py"
SPEC = importlib.util.spec_from_file_location("nextlens_downstream_salmon_landscape", MODULE_PATH)
DOWNSTREAM = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = DOWNSTREAM
SPEC.loader.exec_module(DOWNSTREAM)


def test_generate_salmon_signals_from_validation_creates_routed_deduped_event(tmp_path: Path) -> None:
    validation = {
        "status": "pass",
        "salmonRequired": True,
        "featureId": "feature-password-recovery",
        "packetId": "packet-123",
        "validationId": "validation-001",
        "findings": [
            {
                "impactLevel": "journey_assumption_change",
                "issueDescription": "Journey assumption no longer holds for the selected feature.",
                "impactedNodes": {
                    "features": ["feature-password-recovery"],
                    "journeys": ["journey-onboard"],
                    "outcomes": [],
                    "roles": [],
                    "operatingLoops": [],
                    "capabilities": [],
                    "bmadArtifacts": [],
                },
                "severity": "advisory",
            }
        ],
    }

    result = DOWNSTREAM.generate_salmon_signals_from_validation(
        validation,
        tmp_path,
        now_factory=lambda: datetime(2026, 5, 14, 12, 34, 56, tzinfo=timezone.utc),
    )

    assert result.status == "pass"
    assert len(result.events) == 1
    event = result.events[0]
    assert event["schemaVersion"] == "nextlens.salmon-signal.v1"
    assert event["source"]["type"] == "validation"
    assert event["discovery"]["impactLevel"] == "journey_assumption_change"
    assert event["routingResult"]["targetRef"].replace("\\", "/").endswith(
        "landscape/journey/journey-onboard.yaml"
    )
    assert event["recommendedAction"]["type"] == "landscape_update"
    assert len(event["dedupFingerprint"]) == 64
    assert event["createdAt"] == "2026-05-14T12:34:56Z"


def test_generate_salmon_signals_from_validation_skips_without_salmon_required(tmp_path: Path) -> None:
    validation = {
        "status": "pass",
        "salmonRequired": False,
        "findings": [],
    }

    result = DOWNSTREAM.generate_salmon_signals_from_validation(validation, tmp_path)

    assert result.status == "skipped"
    assert result.events == ()
