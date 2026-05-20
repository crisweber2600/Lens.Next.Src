#!/usr/bin/env python3
"""Handwritten Bottom-Up LENS packet validation contract.

The MVP validator intentionally uses only Python standard-library rules.  A
future JSON Schema bridge may be added after these handwritten rules and
fixtures pass; this module must not import or require jsonschema.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

SUPPORTED_SCHEMA_VERSION = "bul.feature-packet.v1"

PACKET_VALID_LABEL = "Feature packet is valid"
PACKET_NOT_READY_LABEL = "Feature packet is not ready yet"
BMAD_READY_LABEL = "Ready for BMAD: ready"
BMAD_NOT_READY_LABEL = "Ready for BMAD: not yet"

ERROR_SHAPE_KEYS = ("code", "field", "message", "recommendation")

RULE_INVENTORY: list[dict[str, str]] = [
    {
        "id": "schema-version",
        "category": "schemaVersion",
        "field": "schemaVersion",
        "description": "Packet schemaVersion must be bul.feature-packet.v1.",
    },
    {
        "id": "source-mode",
        "category": "sourceMode",
        "field": "sourceMode",
        "description": "sourceMode must be bottom_up and never inferred from Lens lifecycle state.",
    },
    {
        "id": "identity",
        "category": "identity",
        "field": "identity",
        "description": "Feature identity must include featureName, actor, problem, and outcome.",
    },
    {
        "id": "selected-feature",
        "category": "selectedFeature",
        "field": "selectedFeature",
        "description": "Exactly one local candidate feature must be selected.",
    },
    {
        "id": "scope",
        "category": "scope",
        "field": "scope",
        "description": "Included scope and explicit out-of-scope lists are both required.",
    },
    {
        "id": "constraints",
        "category": "constraints",
        "field": "constraints",
        "description": "Constraints must include anti-inference handoff instructions.",
    },
    {
        "id": "assumptions",
        "category": "assumptions",
        "field": "assumptions",
        "description": "Assumptions must remain unpromoted archive evidence.",
    },
    {
        "id": "provenance",
        "category": "provenance",
        "field": "provenance",
        "description": "Provenance must identify explicit source inputs and reject branch/editor/cwd inference.",
    },
    {
        "id": "receipt-reference",
        "category": "receiptReference",
        "field": "receiptReference",
        "description": "A receiptReference key is required; accepted packets include receipt and run metadata paths.",
    },
    {
        "id": "topology",
        "category": "topology",
        "field": "topology",
        "description": "Topology, landscape, graph, roadmap, and promotion fields must remain null/unpromoted.",
    },
    {
        "id": "non-effects",
        "category": "nonEffects",
        "field": "nonEffects",
        "description": "Packet claims must preserve no Lens governance, topology, release, or runtime side effects.",
    },
]

TOPOLOGY_NULL_FIELDS = [
    "domain",
    "service",
    "program",
    "landscape",
    "derivedGraph",
    "salmon",
    "promotion",
    "adjacency",
    "pressure",
    "roadmap",
    "branchTopology",
]

NON_EFFECT_FIELDS = [
    "featureYamlWritten",
    "governancePublished",
    "governanceMirrorWritten",
    "lensBranchesCreated",
    "constitutionRuntimeWritten",
    "releaseCloneWritten",
    "topDownRuntimeWritten",
    "landscapeWritten",
    "derivedGraphWritten",
    "salmonRouted",
    "topologyPromoted",
    "serviceDomainProgramTruthWritten",
]

INFERENCE_SOURCES = {"branch", "git-branch", "editor", "open-editor", "cwd", "current-working-directory"}


def make_error(code: str, field: str, message: str, recommendation: str) -> dict[str, str]:
    """Return the required structured error shape."""

    return {
        "code": code,
        "field": field,
        "message": message,
        "recommendation": recommendation,
    }


def rule_inventory() -> list[dict[str, str]]:
    return deepcopy(RULE_INVENTORY)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and any(item not in (None, "", [], {}) for item in value)


def _append_required_object_error(errors: list[dict[str, str]], field: str, code: str | None = None) -> bool:
    errors.append(
        make_error(
            code or "missingObject",
            field,
            f"{field} must be an object.",
            f"Provide a {field} object from explicit local context before validation.",
        )
    )
    return False


def _require_identity(packet: dict[str, Any], errors: list[dict[str, str]]) -> None:
    identity = packet.get("identity")
    if not isinstance(identity, dict):
        _append_required_object_error(errors, "identity")
        return
    for key in ("featureName", "actor", "problem", "outcome"):
        if not _non_empty_string(identity.get(key)):
            errors.append(
                make_error(
                    "missingIdentityField",
                    f"identity.{key}",
                    f"identity.{key} is required and must be explicit.",
                    "Collect actor, problem, and useful outcome directly from the operator; do not infer them from branch, editor, or cwd.",
                )
            )


def _require_candidate_selection(packet: dict[str, Any], errors: list[dict[str, str]]) -> None:
    selected_feature = packet.get("selectedFeature")
    candidate_features = packet.get("candidateFeatures")
    if not isinstance(selected_feature, dict):
        _append_required_object_error(errors, "selectedFeature")
        return
    if not _non_empty_string(selected_feature.get("id")) or not _non_empty_string(selected_feature.get("title")):
        errors.append(
            make_error(
                "missingSelectedFeature",
                "selectedFeature",
                "selectedFeature must include an id and title.",
                "Select exactly one candidate feature before composing or validating the packet.",
            )
        )
    if not isinstance(candidate_features, list):
        errors.append(
            make_error(
                "missingCandidateFeatures",
                "candidateFeatures",
                "candidateFeatures must list local candidate slices.",
                "Record the selected candidate and any deferred candidates as unranked notes only.",
            )
        )
        return

    selected_candidates = [candidate for candidate in candidate_features if isinstance(candidate, dict) and candidate.get("selected") is True]
    if len(selected_candidates) != 1:
        errors.append(
            make_error(
                "invalidCandidateSelection",
                "candidateFeatures",
                f"Exactly one candidate must be selected; found {len(selected_candidates)}.",
                "Choose one candidate or split the context before proceeding; do not write a packet with zero or multiple selections.",
            )
        )
    elif selected_candidates[0].get("id") != selected_feature.get("id"):
        errors.append(
            make_error(
                "selectedFeatureMismatch",
                "selectedFeature.id",
                "selectedFeature.id must match the one selected candidate.",
                "Update selectedFeature from the selected candidate instead of inferring a different identity.",
            )
        )

    for index, candidate in enumerate(candidate_features):
        if not isinstance(candidate, dict):
            continue
        if candidate.get("selected") is False and candidate.get("rank") not in (None, ""):
            errors.append(
                make_error(
                    "rankedDeferredCandidate",
                    f"candidateFeatures[{index}].rank",
                    "Deferred candidates must remain unranked notes.",
                    "Remove ranking, ordering, roadmap, adjacency, or dependency claims from deferred candidates.",
                )
            )
        if candidate.get("selected") is False and candidate.get("topology") not in (None, {}, {"status": "unpromoted"}):
            errors.append(
                make_error(
                    "deferredCandidateTopology",
                    f"candidateFeatures[{index}].topology",
                    "Deferred candidates must not carry topology truth.",
                    "Keep deferred candidates as audit notes only; topology belongs outside this MVP packet.",
                )
            )


def _require_scope(packet: dict[str, Any], errors: list[dict[str, str]]) -> None:
    scope = packet.get("scope")
    if not isinstance(scope, dict):
        _append_required_object_error(errors, "scope")
        return
    if not _non_empty_list(scope.get("included")):
        errors.append(
            make_error(
                "missingIncludedScope",
                "scope.included",
                "Included scope is required.",
                "List the smallest concrete behavior that is inside this one feature packet.",
            )
        )
    if not _non_empty_list(scope.get("explicitOutOfScope")):
        errors.append(
            make_error(
                "missingExplicitOutOfScope",
                "scope.explicitOutOfScope",
                "Explicit out-of-scope is required.",
                "List what this packet deliberately excludes so downstream agents do not infer it.",
            )
        )


def _require_acceptance_and_constraints(packet: dict[str, Any], errors: list[dict[str, str]]) -> None:
    if not _non_empty_list(packet.get("acceptanceCriteria")):
        errors.append(
            make_error(
                "missingAcceptanceCriteria",
                "acceptanceCriteria",
                "At least one acceptance criterion is required.",
                "Add concrete Given/When/Then acceptance criteria for the selected feature.",
            )
        )

    constraints = packet.get("constraints")
    if not _non_empty_list(constraints):
        errors.append(
            make_error(
                "missingConstraints",
                "constraints",
                "Constraints are required.",
                "Add local constraints, including explicit anti-inference instructions.",
            )
        )
        return
    joined = "\n".join(str(item).lower() for item in constraints)
    if not ("infer" in joined and "branch" in joined and "editor" in joined and ("cwd" in joined or "current working directory" in joined)):
        errors.append(
            make_error(
                "missingNonInferenceRules",
                "constraints",
                "Constraints must explicitly forbid branch, open-editor, and cwd inference.",
                "Add a constraint such as: Do not infer identity, phase, topology, or scope from branch name, open editor, or cwd.",
            )
        )


def _require_assumptions(packet: dict[str, Any], errors: list[dict[str, str]]) -> None:
    assumptions = packet.get("assumptions")
    if not _non_empty_list(assumptions):
        errors.append(
            make_error(
                "missingAssumptions",
                "assumptions",
                "At least one assumption record is required, even if it states none are known.",
                "Record assumptions as unpromoted evidence instead of promoting them into topology or roadmap truth.",
            )
        )
        return
    for index, assumption in enumerate(assumptions):
        if not isinstance(assumption, dict):
            errors.append(
                make_error(
                    "invalidAssumptionShape",
                    f"assumptions[{index}]",
                    "Each assumption must be an object with text and status.",
                    "Use {'text': '...', 'status': 'unpromoted'} for each assumption.",
                )
            )
            continue
        if not _non_empty_string(assumption.get("text")):
            errors.append(
                make_error(
                    "missingAssumptionText",
                    f"assumptions[{index}].text",
                    "Assumption text is required.",
                    "State the assumption explicitly or use an explicit 'No additional assumptions identified' record.",
                )
            )
        if assumption.get("status") != "unpromoted" or assumption.get("promoted") is True:
            errors.append(
                make_error(
                    "promotedAssumption",
                    f"assumptions[{index}].status",
                    "Assumptions must remain unpromoted.",
                    "Change the assumption status to unpromoted and keep it as packet evidence only.",
                )
            )


def _require_provenance(packet: dict[str, Any], errors: list[dict[str, str]]) -> None:
    provenance = packet.get("provenance")
    if not isinstance(provenance, dict):
        _append_required_object_error(errors, "provenance")
        return
    if provenance.get("explicitInputsOnly") is not True:
        errors.append(
            make_error(
                "explicitInputsOnlyRequired",
                "provenance.explicitInputsOnly",
                "Provenance must state explicitInputsOnly=true.",
                "Collect operator-provided context or configured paths instead of inferring from ambient state.",
            )
        )
    if provenance.get("noBranchEditorCwdInference") is not True:
        errors.append(
            make_error(
                "branchEditorCwdInferenceNotRejected",
                "provenance.noBranchEditorCwdInference",
                "Branch, open-editor, and cwd inference must be rejected.",
                "Set noBranchEditorCwdInference=true only after context was provided explicitly.",
            )
        )
    if not _non_empty_list(provenance.get("inputRefs")):
        errors.append(
            make_error(
                "missingInputRefs",
                "provenance.inputRefs",
                "Provenance must include explicit input references.",
                "Add local file paths, pasted context labels, or operator-provided source identifiers.",
            )
        )
    inference_sources = {str(item).lower() for item in provenance.get("inferenceSources", []) if item is not None}
    if inference_sources & INFERENCE_SOURCES or provenance.get("inferredFromBranch") or provenance.get("inferredFromEditor") or provenance.get("inferredFromCwd"):
        errors.append(
            make_error(
                "forbiddenContextInference",
                "provenance.inferenceSources",
                "Packet identity or scope must not be inferred from branch, open editor, or cwd.",
                "Remove ambient inference sources and ask for explicit context or module config instead.",
            )
        )


def _require_receipt_reference(packet: dict[str, Any], errors: list[dict[str, str]]) -> None:
    if "receiptReference" not in packet:
        errors.append(
            make_error(
                "missingReceiptReference",
                "receiptReference",
                "receiptReference key is required.",
                "Use null for drafts or include receiptPath and runMetadataPath for accepted packets.",
            )
        )
        return
    receipt_reference = packet.get("receiptReference")
    if packet.get("packetStatus") == "accepted":
        if not isinstance(receipt_reference, dict) or not _non_empty_string(receipt_reference.get("receiptPath")) or not _non_empty_string(receipt_reference.get("runMetadataPath")):
            errors.append(
                make_error(
                    "acceptedReceiptReferenceRequired",
                    "receiptReference",
                    "Accepted packets must reference receipt and run metadata artifacts.",
                    "Write and verify receipt/run metadata before marking a packet accepted.",
                )
            )


def _require_topology_null(packet: dict[str, Any], errors: list[dict[str, str]]) -> None:
    topology = packet.get("topology")
    if not isinstance(topology, dict):
        _append_required_object_error(errors, "topology")
        return
    if topology.get("status") != "unpromoted":
        errors.append(
            make_error(
                "topologyNotUnpromoted",
                "topology.status",
                "Topology status must be unpromoted.",
                "Keep all topology work outside the Bottom-Up LENS MVP packet.",
            )
        )
    for key in TOPOLOGY_NULL_FIELDS:
        if topology.get(key) is not None:
            errors.append(
                make_error(
                    "promotedTopology",
                    f"topology.{key}",
                    f"topology.{key} must remain null.",
                    "Remove Landscape, Derived Graph, roadmap, branch topology, promotion, adjacency, pressure, service, domain, or program truth from this packet.",
                )
            )


def _require_non_effects(packet: dict[str, Any], errors: list[dict[str, str]]) -> None:
    non_effects = packet.get("nonEffects")
    if not isinstance(non_effects, dict):
        _append_required_object_error(errors, "nonEffects")
        return
    for key in NON_EFFECT_FIELDS:
        if key not in non_effects:
            errors.append(
                make_error(
                    "missingNonEffectClaim",
                    f"nonEffects.{key}",
                    f"nonEffects.{key} is required.",
                    "Carry every explicit no-side-effect claim in the packet so receipt verification can audit it.",
                )
            )
        elif non_effects.get(key) is not False:
            errors.append(
                make_error(
                    "forbiddenSideEffectClaim",
                    f"nonEffects.{key}",
                    f"nonEffects.{key} must be false for a standalone packet.",
                    "Do not claim or perform Lens governance, topology, release clone, top-down runtime, or service/domain/program truth writes.",
                )
            )


def validate_packet_dict(packet: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []

    if packet.get("schemaVersion") != SUPPORTED_SCHEMA_VERSION:
        errors.append(
            make_error(
                "unsupportedSchemaVersion",
                "schemaVersion",
                f"schemaVersion must be {SUPPORTED_SCHEMA_VERSION}.",
                "Update the packet to the supported MVP schema before validation.",
            )
        )
    if packet.get("sourceMode") != "bottom_up":
        errors.append(
            make_error(
                "invalidSourceMode",
                "sourceMode",
                "sourceMode must be bottom_up.",
                "Use Bottom-Up LENS only for explicit bottom-up local context, not Lens lifecycle state.",
            )
        )

    _require_identity(packet, errors)
    _require_candidate_selection(packet, errors)
    _require_scope(packet, errors)
    _require_acceptance_and_constraints(packet, errors)
    _require_assumptions(packet, errors)
    _require_provenance(packet, errors)
    _require_receipt_reference(packet, errors)
    _require_topology_null(packet, errors)
    _require_non_effects(packet, errors)
    return errors


def packet_valid_result(errors: list[dict[str, str]]) -> dict[str, Any]:
    status = "pass" if not errors else "fail"
    return {
        "status": status,
        "label": PACKET_VALID_LABEL if status == "pass" else PACKET_NOT_READY_LABEL,
        "rulesEvaluated": [rule["id"] for rule in RULE_INVENTORY],
        "errors": errors,
    }


def build_validation_result(packet: dict[str, Any], bmad_ready: dict[str, Any] | None = None) -> dict[str, Any]:
    errors = validate_packet_dict(packet)
    bmad = bmad_ready or {"status": "not_checked", "label": BMAD_NOT_READY_LABEL, "reasons": []}
    return {
        "schemaVersion": SUPPORTED_SCHEMA_VERSION,
        "packetValid": packet_valid_result(errors),
        "bmadReady": bmad,
        "hardBlockers": errors,
        "advisories": [],
    }


def canonical_topology() -> dict[str, Any]:
    topology = {key: None for key in TOPOLOGY_NULL_FIELDS}
    topology["status"] = "unpromoted"
    return topology


def canonical_non_effects() -> dict[str, bool]:
    return {key: False for key in NON_EFFECT_FIELDS}
