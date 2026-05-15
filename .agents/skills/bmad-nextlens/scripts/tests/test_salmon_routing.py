from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys

import pytest


MODULE_PATH = Path(__file__).resolve().parent.parent / "salmon_routing.py"
SPEC = importlib.util.spec_from_file_location("nextlens_salmon_routing", MODULE_PATH)
SALMON_ROUTING = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = SALMON_ROUTING
SPEC.loader.exec_module(SALMON_ROUTING)


@pytest.mark.parametrize(
    ("impact_level", "expected_action", "expected_path_fragment", "state_change"),
    [
        ("local_feature_note", "append_feature_note", ".nextlens/salmon/feature-notes/feature-password-recovery.md", False),
        ("feature_scope_change", "update_feature_scope", "landscape/feature/feature-password-recovery.yaml", True),
        ("journey_assumption_change", "update_journey_assumption", "landscape/journey/journey-account-recovery.yaml", True),
        ("outcome_reframe", "update_outcome_frame", "landscape/outcome/outcome-reduced-ambiguity.yaml", True),
        ("role_or_stakeholder_change", "update_role_or_stakeholder", "landscape/role/role-operator.yaml", True),
        ("operating_loop_change", "update_operating_loop", "landscape/operating_loop/loop-planning.yaml", True),
        ("capability_or_landscape_update", "upsert_capability_or_landscape", "landscape/capability/capability-routing.yaml", True),
        ("bmad_correct_course_required", "create_bmad_correct_course_record", ".nextlens/salmon/correct-course/feature-password-recovery.json", True),
    ],
)
def test_route_salmon_event_classifies_all_impact_levels(
    tmp_path: Path,
    impact_level: str,
    expected_action: str,
    expected_path_fragment: str,
    state_change: bool,
) -> None:
    decision = SALMON_ROUTING.route_salmon_event(
        _event(impact_level),
        tmp_path,
        now_factory=lambda: datetime(2026, 5, 14, 12, 34, 56, tzinfo=timezone.utc),
    )

    assert decision.impact_level == impact_level
    assert decision.action == expected_action
    assert decision.target_ref.replace("\\", "/").endswith(expected_path_fragment)
    assert decision.state_change is state_change
    assert decision.routing_result == {
        "status": "created",
        "targetRef": decision.target_ref,
        "timestamp": "2026-05-14T12:34:56Z",
    }


def test_routing_result_can_be_applied_to_event_payload(tmp_path: Path) -> None:
    event = _event("feature_scope_change")
    decision = SALMON_ROUTING.route_salmon_event(event, tmp_path, status="merged")

    routed_event = SALMON_ROUTING.apply_routing_result(event, decision)

    assert routed_event["routingResult"] == decision.routing_result
    assert routed_event["routingResult"]["status"] == "merged"


def test_outcome_and_role_routing_notify_impacted_scope(tmp_path: Path) -> None:
    outcome = SALMON_ROUTING.route_salmon_event(_event("outcome_reframe"), tmp_path)
    role = SALMON_ROUTING.route_salmon_event(_event("role_or_stakeholder_change"), tmp_path)

    assert outcome.notification_targets == (
        "feature:feature-password-recovery",
        "journey:journey-account-recovery",
    )
    assert role.notification_targets == (
        "feature:feature-password-recovery",
        "journey:journey-account-recovery",
        "outcome:outcome-reduced-ambiguity",
    )


def test_bmad_correct_course_routing_sets_tracking_flags(tmp_path: Path) -> None:
    decision = SALMON_ROUTING.route_salmon_event(_event("bmad_correct_course_required"), tmp_path)

    assert decision.requires_bmad_correct_course is True
    assert decision.creates_tracking_record is True
    assert decision.notification_targets == ("bmad:prd.md",)


def _event(impact_level: str) -> dict[str, object]:
    return {
        "discovery": {
            "impactLevel": impact_level,
            "impactedFeature": "feature-password-recovery",
        },
        "impactedNodes": {
            "features": ["feature-password-recovery"],
            "journeys": ["journey-account-recovery"],
            "outcomes": ["outcome-reduced-ambiguity"],
            "roles": ["role-operator"],
            "operatingLoops": ["loop-planning"],
            "capabilities": ["capability-routing"],
            "bmadArtifacts": ["prd.md"],
        },
    }