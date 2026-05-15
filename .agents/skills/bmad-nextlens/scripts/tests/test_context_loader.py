from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


MODULE_PATH = Path(__file__).resolve().parent.parent / "context_loader.py"
SPEC = importlib.util.spec_from_file_location("nextlens_context_loader", MODULE_PATH)
CONTEXT_LOADER = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = CONTEXT_LOADER
SPEC.loader.exec_module(CONTEXT_LOADER)


def test_parse_context_yaml_accepts_direct_payload() -> None:
    loaded = CONTEXT_LOADER.parse_context_yaml(_context_yaml())

    assert loaded.envelope_key is None
    assert loaded.version_mismatch is False
    assert loaded.warnings == ()
    assert loaded.payload["system"]["id"] == "nextlens"
    assert loaded.payload["roles"][0]["id"] == "role-operator"


def test_load_context_file_accepts_top_down_context_envelope(tmp_path: Path) -> None:
    context_path = tmp_path / "top-down-context.yaml"
    context_path.write_text(_context_yaml(envelope=True), encoding="utf-8")

    loaded = CONTEXT_LOADER.load_context_file(context_path)

    assert loaded.source_path == context_path
    assert loaded.envelope_key == "top_down_context"
    assert loaded.payload["discoveryEpoch"]["id"] == "epoch-2026-05-14"


def test_parse_context_yaml_warns_on_schema_version_mismatch() -> None:
    loaded = CONTEXT_LOADER.parse_context_yaml(
        _context_yaml(schema_version="lens.topdown-context.v0")
    )

    assert loaded.version_mismatch is True
    assert len(loaded.warnings) == 1
    assert "expected 'lens.topdown-context.v1'" in loaded.warnings[0]


def test_parse_context_yaml_rejects_malformed_yaml() -> None:
    with pytest.raises(CONTEXT_LOADER.ContextValidationError) as exc_info:
        CONTEXT_LOADER.parse_context_yaml("top_down_context:\n  schemaVersion: [")

    assert "Failed to parse YAML" in str(exc_info.value)


def test_parse_context_yaml_reports_missing_root_field() -> None:
    with pytest.raises(CONTEXT_LOADER.ContextValidationError) as exc_info:
        CONTEXT_LOADER.parse_context_yaml(_context_yaml(include_system=False))

    message = str(exc_info.value)
    assert "Missing required field(s): system." in message


def test_parse_context_yaml_reports_missing_nested_field() -> None:
    with pytest.raises(CONTEXT_LOADER.ContextValidationError) as exc_info:
        CONTEXT_LOADER.parse_context_yaml(_context_yaml(include_role_id=False))

    assert "roles[0].id" in str(exc_info.value)


def test_evaluate_context_sufficiency_returns_ready_when_all_gates_pass() -> None:
    report = CONTEXT_LOADER.evaluate_context_sufficiency(_sufficient_context())

    assert report.status == "ready"
    assert report.recommendation == "continue"
    assert report.missing_required == ()
    assert report.warnings == ()
    assert [gate.name for gate in report.gate_results] == list(CONTEXT_LOADER.SUFFICIENCY_GATE_ORDER)
    assert all(gate.passed for gate in report.gate_results)


def test_evaluate_context_sufficiency_returns_ready_with_warnings() -> None:
    payload = _sufficient_context()
    payload["risks"] = ["risk-1"]
    payload["openQuestions"] = ["question-1", "question-2"]
    payload.pop("bmadConsumerContext")

    report = CONTEXT_LOADER.evaluate_context_sufficiency(payload)

    assert report.status == "ready_with_warnings"
    assert report.recommendation == "ask_for_confirmation"
    assert report.missing_required == ()
    assert "risks_captured has fewer than 3 risks (1)." in report.warnings
    assert "risks_captured has fewer than 3 open questions (2)." in report.warnings
    assert "bmad_hints is missing bmadConsumerContext." in report.warnings


def test_evaluate_context_sufficiency_returns_blocked_and_lists_failed_gates() -> None:
    payload = _sufficient_context()
    payload["system"]["thesis"] = ""
    payload["roles"] = []
    payload["outcomes"] = []
    payload["journeys"] = []
    payload["candidateFeatures"] = [{"id": "feature-context-gate"}]

    report = CONTEXT_LOADER.evaluate_context_sufficiency(payload)

    assert report.status == "blocked"
    assert report.recommendation == "return_to_discovery"
    assert report.missing_required == (
        "system_thesis",
        "role_coverage",
        "outcome_coverage",
        "journey_coverage",
        "candidate_traceability",
    )


def test_evaluate_context_sufficiency_accepts_journey_hypotheses() -> None:
    payload = _sufficient_context()
    payload["journeys"] = []
    payload["journeyHypotheses"] = [{"id": "journey-hypothesis-1"}]

    report = CONTEXT_LOADER.evaluate_context_sufficiency(payload)

    journey_gate = next(gate for gate in report.gate_results if gate.name == "journey_coverage")
    assert journey_gate.passed is True
    assert journey_gate.detail == "1 journeys"


def test_evaluate_context_sufficiency_propagates_parser_warnings() -> None:
    loaded = CONTEXT_LOADER.LoadedContext(
        payload=_sufficient_context(),
        warnings=(
            "Schema version mismatch: expected 'lens.topdown-context.v1' but received "
            "'lens.topdown-context.v0'. Continuing with a warning.",
        ),
        version_mismatch=True,
    )
    report = CONTEXT_LOADER.evaluate_context_sufficiency(loaded)

    assert report.status == "ready_with_warnings"
    assert any("Schema version mismatch" in warning for warning in report.warnings)


def test_format_context_sufficiency_report_for_ready_status() -> None:
    report = CONTEXT_LOADER.evaluate_context_sufficiency(_sufficient_context())

    lines = CONTEXT_LOADER.format_context_sufficiency_report(report)

    assert lines[0] == "[stage:context-sufficiency]"
    assert "system_thesis: [✓] Improve planning fidelity" in lines
    assert "role_coverage: [✓] 1 roles" in lines
    assert "candidate_traceability: [✓] 1 candidates traceable" in lines
    assert "status: ready" in lines
    assert "recommendation: continue" in lines


def test_format_context_sufficiency_report_for_blocked_status() -> None:
    payload = _sufficient_context()
    payload["system"]["thesis"] = ""
    payload["roles"] = []
    payload["outcomes"] = []
    payload["journeys"] = []
    payload["candidateFeatures"] = [{"id": "feature-context-gate"}]
    report = CONTEXT_LOADER.evaluate_context_sufficiency(payload)

    lines = CONTEXT_LOADER.format_context_sufficiency_report(report)

    assert "system_thesis: [✗] missing" in lines
    assert "status: blocked" in lines
    assert "recommendation: return_to_discovery" in lines
    assert "missing_required:" in lines
    assert "- system_thesis" in lines
    assert "confirmation_required: yes" not in lines


def test_format_context_sufficiency_report_for_warnings_status() -> None:
    payload = _sufficient_context()
    payload["risks"] = ["risk-1"]
    payload["openQuestions"] = ["question-1", "question-2"]
    payload.pop("bmadConsumerContext")
    report = CONTEXT_LOADER.evaluate_context_sufficiency(payload)

    lines = CONTEXT_LOADER.format_context_sufficiency_report(report)

    assert "risks_captured: [✓] 1 risks" in lines
    assert "bmad_hints: [✗] missing hints" in lines
    assert "status: ready_with_warnings" in lines
    assert "recommendation: ask_for_confirmation" in lines
    assert "warnings:" in lines
    assert any("bmad_hints is missing bmadConsumerContext." in line for line in lines)
    assert "confirmation_required: yes" in lines


def _context_yaml(
    *,
    envelope: bool = False,
    schema_version: str = "lens.topdown-context.v1",
    include_system: bool = True,
    include_role_id: bool = True,
) -> str:
    body_lines = [
        f"schemaVersion: {schema_version}",
    ]

    if include_system:
        body_lines.extend(
            [
                "system:",
                "  id: nextlens",
                "  name: NextLens",
                "  thesis: Improve planning fidelity",
                "  status: active",
                "  confidence: high",
            ]
        )

    body_lines.extend(
        [
            "discoveryEpoch:",
            "  id: epoch-2026-05-14",
            "  status: synthesized",
            "  sourceRefs:",
            "    - docs/discovery.md",
            "roles:",
            "  - name: Operator" if not include_role_id else "  - id: role-operator",
            "    name: Operator",
            "outcomes:",
            "  - id: outcome-reduce-ambiguity",
            "    name: Reduce ambiguity",
            "journeys:",
            "  - id: journey-intake",
            "    name: Intake",
            "candidateFeatures:",
            "  - id: feature-context-gate",
            "    title: Context sufficiency gate",
            "stakeholders: []",
            "operatingLoops: []",
            "openQuestions: []",
            "risks: []",
            "decisions: []",
            "relationshipRefs: []",
        ]
    )

    if not envelope:
        return "\n".join(body_lines) + "\n"

    return "\n".join(["top_down_context:", *[f"  {line}" for line in body_lines]]) + "\n"


def _sufficient_context() -> dict[str, object]:
    return {
        "schemaVersion": "lens.topdown-context.v1",
        "system": {
            "id": "nextlens",
            "name": "NextLens",
            "thesis": "Improve planning fidelity",
            "status": "active",
            "confidence": "high",
        },
        "discoveryEpoch": {
            "id": "epoch-2026-05-14",
            "status": "synthesized",
            "sourceRefs": ["docs/discovery.md"],
        },
        "roles": [
            {"id": "role-operator", "name": "Operator"},
        ],
        "outcomes": [
            {"id": "outcome-reduce-ambiguity", "name": "Reduce ambiguity"},
        ],
        "journeys": [
            {"id": "journey-intake", "name": "Intake"},
        ],
        "candidateFeatures": [
            {
                "id": "feature-context-gate",
                "title": "Context sufficiency gate",
                "journeyIds": ["journey-intake"],
            },
        ],
        "stakeholders": [],
        "operatingLoops": [],
        "openQuestions": ["question-1", "question-2", "question-3"],
        "risks": ["risk-1", "risk-2", "risk-3"],
        "decisions": [],
        "relationshipRefs": [],
        "bmadConsumerContext": {
            "planningMode": "feature-packet",
            "consumer": "bmad",
        },
    }