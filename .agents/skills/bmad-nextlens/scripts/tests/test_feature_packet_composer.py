from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys


SCORING_PATH = Path(__file__).resolve().parent.parent / "feature_scoring.py"
SCORING_SPEC = importlib.util.spec_from_file_location("nextlens_feature_scoring_for_packet", SCORING_PATH)
FEATURE_SCORING = importlib.util.module_from_spec(SCORING_SPEC)
assert SCORING_SPEC is not None and SCORING_SPEC.loader is not None
sys.modules[SCORING_SPEC.name] = FEATURE_SCORING
SCORING_SPEC.loader.exec_module(FEATURE_SCORING)

MODULE_PATH = Path(__file__).resolve().parent.parent / "feature_packet_composer.py"
SPEC = importlib.util.spec_from_file_location("nextlens_feature_packet_composer", MODULE_PATH)
FEATURE_PACKET_COMPOSER = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = FEATURE_PACKET_COMPOSER
SPEC.loader.exec_module(FEATURE_PACKET_COMPOSER)


def test_compose_feature_packet_assembles_canonical_identity_fields_and_validates() -> None:
    context = _context()
    ranked = _ranked_candidates()

    result = FEATURE_PACKET_COMPOSER.compose_feature_packet(
        ranked[0],
        ranked,
        context,
        docs_path="docs/nextlens/src/feature-a",
        packet_id_factory=lambda: "550e8400-e29b-41d4-a716-446655440000",
        now_factory=lambda: datetime(2026, 5, 14, 12, 34, 56, tzinfo=timezone.utc),
        doctor_summary={"overall_status": "pass", "blocked": 0, "advisory": 1, "informational": 2},
    )

    assert result.status == "pass"
    assert result.validation.is_valid
    assert result.packet["schemaVersion"] == "nextlens.feature-packet.v1"
    assert result.packet["packetId"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result.packet["featureId"] == "feature-password-recovery"
    assert result.packet["sourceMode"] == "top_down"
    assert result.packet["createdAt"] == "2026-05-14T12:34:56Z"


def test_compose_feature_packet_populates_selected_feature_trace_and_rationale() -> None:
    context = _context()
    ranked = _ranked_candidates()

    packet = FEATURE_PACKET_COMPOSER.compose_feature_packet(
        ranked[0],
        ranked,
        context,
        docs_path="docs/nextlens/src/feature-a",
        packet_id_factory=lambda: "550e8400-e29b-41d4-a716-446655440000",
    ).packet

    assert packet["selectedFeature"] == {
        "id": "feature-password-recovery",
        "name": "Password Recovery",
        "goal": "Restore account access without widening scope.",
        "includedScope": ["password reset", "self-service recovery"],
        "explicitOutOfScope": [
            "admin triage",
            "adjacent journeys",
            "future Features",
            "platform architecture",
            "unrelated outcomes",
        ],
    }
    assert packet["trace"] == {
        "systemId": "system-nextlens",
        "discoveryEpochId": "epoch-2026-05-14",
        "roleIds": ["role-operator"],
        "outcomeIds": ["outcome-reduced-ambiguity"],
        "journeyIds": ["journey-account-recovery"],
        "operatingLoopIds": ["loop-planning"],
        "relationshipRefs": ["system-nextlens->role-operator"],
    }
    assert packet["selectionRationale"]["score"] == 88.5
    assert packet["selectionRationale"]["whyThisFeature"] == "Highest outcome alignment and readiness."
    assert packet["selectionRationale"]["rejectedAlternates"] == [
        {"id": "feature-admin-triage", "name": "Admin Triage", "score": 82.0},
        {"id": "feature-billing", "name": "Billing", "score": 78.0},
    ]


def test_compose_feature_packet_populates_refs_summaries_and_bmad_hints() -> None:
    ranked = _ranked_candidates()

    packet = FEATURE_PACKET_COMPOSER.compose_feature_packet(
        ranked[0],
        ranked,
        _context(),
        docs_path="docs/nextlens/src/feature-a",
        authoritative_state_ref="docs/nextlens/src/feature-a/landscape",
        derived_graph_ref="docs/nextlens/src/feature-a/derived/graph.json",
        doctor_summary={"status": "advisory", "blocking_count": 0, "advisory_count": 2, "informational_count": 1},
        salmon_routing_summary={"status": "created", "events": 1},
        packet_id_factory=lambda: "550e8400-e29b-41d4-a716-446655440000",
    ).packet

    assert packet["sourceContextRefs"] == [
        "product-brief.md",
        "prd.md",
        "ux-design.md",
        "architecture.md",
        "research.md",
        "brainstorm.md",
    ]
    assert packet["authoritativeStateRef"] == "docs/nextlens/src/feature-a/landscape"
    assert packet["derivedGraphRef"] == "docs/nextlens/src/feature-a/derived/graph.json"
    assert packet["doctorSummary"] == {
        "status": "advisory",
        "blocking_count": 0,
        "advisory_count": 2,
        "informational_count": 1,
    }
    assert packet["salmonRoutingSummary"] == {"status": "created", "events": 1}
    assert packet["system"]["thesis"] == "Improve planning fidelity through top-down discovery."
    assert packet["roles"] == [{"id": "role-operator", "name": "Operator"}]
    assert packet["outcomes"] == [{"id": "outcome-reduced-ambiguity", "name": "Reduce ambiguity"}]
    assert packet["journeys"] == [{"id": "journey-account-recovery", "name": "Account recovery"}]
    assert packet["operatingLoops"] == [{"id": "loop-planning", "name": "Planning loop"}]
    assert packet["openQuestions"] == ["Which proof points confirm candidate readiness?"]
    assert packet["risks"] == [{"id": "risk-missing-trace", "name": "Missing traceability"}]
    assert packet["bmadConsumerHints"]["scopeContainmentWarning"] == (
        "This packet represents one selected Feature from top-down discovery. "
        "Do not expand into adjacent journeys, future Features, platform architecture, "
        "or unrelated outcomes unless Salmon or correct-course signals scope change."
    )
    assert packet["bmadConsumerHints"]["prdInput"] == "PRD goal and key requirements."
    assert packet["bmadConsumerHints"]["readinessInput"] == "Implementation readiness is green."


def test_compose_feature_packet_adds_bmad_scope_containment_metadata() -> None:
    ranked = _ranked_candidates()

    packet = FEATURE_PACKET_COMPOSER.compose_feature_packet(
        ranked[0],
        ranked,
        _context(),
        docs_path="docs/nextlens/src/feature-a",
        packet_id_factory=lambda: "550e8400-e29b-41d4-a716-446655440000",
        now_factory=lambda: datetime(2026, 5, 14, 12, 34, 56, tzinfo=timezone.utc),
    ).packet
    hints = packet["bmadConsumerHints"]

    assert hints["selectedFeature"] == {
        "goal": "Restore account access without widening scope.",
        "includedScope": ["password reset", "self-service recovery"],
        "explicitOutOfScope": [
            "admin triage",
            "adjacent journeys",
            "future Features",
            "platform architecture",
            "unrelated outcomes",
        ],
    }
    assert hints["architectureConstraints"] == {
        "architectureRef": "architecture.md",
        "schemaVersion": "nextlens.feature-packet.v1",
        "packetCreatedAt": "2026-05-14T12:34:56Z",
        "constraints": [
            "single selected Feature packet",
            "deterministic top-down traceability",
            "BMAD scope containment",
        ],
    }
    assert hints["traceabilityLineage"] == (
        "system:system-nextlens -> role:role-operator -> outcome:outcome-reduced-ambiguity "
        "-> journey:journey-account-recovery -> Feature:feature-password-recovery"
    )


def test_compose_feature_packet_preserves_bottom_up_source_mode_and_structured_fields() -> None:
    ranked = _ranked_candidates()
    context = _context()
    context["sourceMode"] = "bottom_up"
    context["openQuestions"] = [
        {
            "id": "question-readiness",
            "text": "Which proof points confirm candidate readiness?",
            "severity": "medium",
        }
    ]

    result = FEATURE_PACKET_COMPOSER.compose_feature_packet(
        ranked[0],
        ranked,
        context,
        docs_path="docs/nextlens/src/feature-a",
        packet_id_factory=lambda: "550e8400-e29b-41d4-a716-446655440000",
    )

    assert result.status == "pass"
    assert result.validation.is_valid
    assert result.packet["sourceMode"] == "bottom_up"
    assert result.packet["openQuestions"] == [
        {
            "id": "question-readiness",
            "text": "Which proof points confirm candidate readiness?",
            "severity": "medium",
        }
    ]
    assert result.packet["risks"] == [{"id": "risk-missing-trace", "name": "Missing traceability"}]
    assert result.packet["decisions"] == [{"id": "decision-top-down", "name": "Require top-down context"}]


def _ranked_candidates() -> tuple[FEATURE_SCORING.ScoredCandidate, ...]:
    return (
        _scored_candidate("feature-password-recovery", "Password Recovery", 88.5),
        _scored_candidate("feature-admin-triage", "Admin Triage", 82.0),
        _scored_candidate("feature-billing", "Billing", 78.0),
    )


def _scored_candidate(candidate_id: str, name: str, score: float) -> FEATURE_SCORING.ScoredCandidate:
    factor_scores = tuple(
        FEATURE_SCORING.FactorScore(name=factor_name, score=score, detail=f"{factor_name} detail")
        for factor_name in FEATURE_SCORING.FACTOR_ORDER
    )
    return FEATURE_SCORING.ScoredCandidate(
        candidate_id=candidate_id,
        candidate_name=name,
        factor_scores=factor_scores,
        composite_score=score,
        unresolved_blockers=0,
        stable_candidate_timestamp="2026-05-14T12:00:00Z",
    )


def _context() -> dict[str, object]:
    return {
        "system": {
            "id": "system-nextlens",
            "name": "NextLens",
            "thesis": "Improve planning fidelity through top-down discovery.",
        },
        "discoveryEpoch": {"id": "epoch-2026-05-14", "status": "synthesized"},
        "roles": [{"id": "role-operator", "name": "Operator"}],
        "outcomes": [{"id": "outcome-reduced-ambiguity", "name": "Reduce ambiguity"}],
        "journeys": [{"id": "journey-account-recovery", "name": "Account recovery"}],
        "operatingLoops": [{"id": "loop-planning", "name": "Planning loop"}],
        "openQuestions": ["Which proof points confirm candidate readiness?"],
        "risks": [{"id": "risk-missing-trace", "name": "Missing traceability"}],
        "decisions": [{"id": "decision-top-down", "name": "Require top-down context"}],
        "relationshipRefs": ["system-nextlens->role-operator"],
        "candidateFeatures": [
            {
                "id": "feature-password-recovery",
                "name": "Password Recovery",
                "goal": "Restore account access without widening scope.",
                "includedScope": ["password reset", "self-service recovery"],
                "outOfScope": ["admin triage"],
                "roleIds": ["role-operator"],
                "outcomeIds": ["outcome-reduced-ambiguity"],
                "journeyIds": ["journey-account-recovery"],
                "operatingLoopIds": ["loop-planning"],
                "relationshipRefs": ["system-nextlens->role-operator"],
                "selectionRationale": "Highest outcome alignment and readiness.",
                "whyNow": "Unblocks downstream planning.",
                "bmadConsumerHints": {
                    "prdInput": "PRD goal and key requirements.",
                    "uxInput": "UX patterns and key flows.",
                    "architectureInput": "Architecture decisions affecting this Feature.",
                    "epicStoryInput": "Estimated epic/story breakdown.",
                    "readinessInput": "Implementation readiness is green.",
                },
            }
        ],
    }