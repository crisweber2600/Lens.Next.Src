"""Load and validate NextLens top-down discovery context."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover - exercised in runtime environments
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


EXPECTED_SCHEMA_VERSION = "lens.topdown-context.v1"
ENVELOPE_KEY = "top_down_context"
REQUIRED_ROOT_FIELDS = (
    "schemaVersion",
    "system",
    "discoveryEpoch",
    "roles",
    "outcomes",
    "journeys",
    "candidateFeatures",
)
REQUIRED_OBJECT_FIELDS = {
    "system": ("id", "name", "thesis", "status", "confidence"),
    "discoveryEpoch": ("id", "status", "sourceRefs"),
}
REQUIRED_COLLECTION_ITEM_FIELDS = {
    "roles": ("id",),
    "outcomes": ("id",),
    "journeys": ("id",),
    "candidateFeatures": ("id",),
}
SUFFICIENCY_GATE_ORDER = (
    "system_thesis",
    "role_coverage",
    "outcome_coverage",
    "journey_coverage",
    "candidate_traceability",
    "risks_captured",
    "bmad_hints",
)
CHECKMARK_SYMBOL = "✓"
CROSS_SYMBOL = "✗"


@dataclass(frozen=True)
class LoadedContext:
    payload: dict[str, Any]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    version_mismatch: bool = False
    source_path: Path | None = None
    envelope_key: str | None = None


class ContextValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ContextSufficiencyGate:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ContextSufficiencyReport:
    status: str
    recommendation: str
    missing_required: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    gate_results: tuple[ContextSufficiencyGate, ...] = field(default_factory=tuple)


def load_context_file(path: str | Path) -> LoadedContext:
    source_path = Path(path)
    try:
        raw_text = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContextValidationError(
            f"Failed to read context file '{source_path}': {exc}"
        ) from exc

    return parse_context_yaml(raw_text, source_path=source_path)


def parse_context_yaml(raw_text: str, *, source_path: str | Path | None = None) -> LoadedContext:
    yaml_module = _require_yaml_support()
    source_label = str(source_path) if source_path is not None else "<memory>"

    try:
        document = yaml_module.safe_load(raw_text)
    except yaml_module.YAMLError as exc:
        raise ContextValidationError(
            f"Failed to parse YAML from {source_label}: {exc}"
        ) from exc

    if not isinstance(document, Mapping):
        raise ContextValidationError(
            f"Context document from {source_label} must be a mapping at the root."
        )

    payload, envelope_key = _extract_payload(document, source_label)
    warnings = _validate_payload(payload, source_label)

    return LoadedContext(
        payload=copy.deepcopy(dict(payload)),
        warnings=tuple(warnings),
        version_mismatch=bool(warnings),
        source_path=Path(source_path) if source_path is not None else None,
        envelope_key=envelope_key,
    )


def evaluate_context_sufficiency(
    context: LoadedContext | Mapping[str, Any],
) -> ContextSufficiencyReport:
    payload, inherited_warnings = _normalize_context_input(context)
    warnings = list(inherited_warnings)
    missing_required: list[str] = []
    gate_results = [
        _evaluate_system_thesis(payload, missing_required),
        _evaluate_role_coverage(payload, missing_required),
        _evaluate_outcome_coverage(payload, missing_required),
        _evaluate_journey_coverage(payload, missing_required),
        _evaluate_candidate_traceability(payload, missing_required),
        _evaluate_risks_and_questions(payload, missing_required, warnings),
        _evaluate_bmad_consumer_context(payload, warnings),
    ]

    if missing_required:
        status = "blocked"
        recommendation = "return_to_discovery"
    elif warnings:
        status = "ready_with_warnings"
        recommendation = "ask_for_confirmation"
    else:
        status = "ready"
        recommendation = "continue"

    return ContextSufficiencyReport(
        status=status,
        recommendation=recommendation,
        missing_required=tuple(missing_required),
        warnings=tuple(warnings),
        gate_results=tuple(gate_results),
    )


def format_context_sufficiency_report(report: ContextSufficiencyReport) -> list[str]:
    gates_by_name = {gate.name: gate for gate in report.gate_results}
    lines = ["[stage:context-sufficiency]"]

    for gate_name in SUFFICIENCY_GATE_ORDER:
        gate = gates_by_name[gate_name]
        symbol = CHECKMARK_SYMBOL if gate.passed else CROSS_SYMBOL
        lines.append(f"{gate_name}: [{symbol}] {gate.detail}")

    lines.append(f"status: {report.status}")
    lines.append(f"recommendation: {report.recommendation}")

    if report.missing_required:
        lines.append("missing_required:")
        lines.extend(f"- {item}" for item in report.missing_required)

    if report.warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in report.warnings)

    if report.status == "ready_with_warnings":
        lines.append("confirmation_required: yes")

    return lines


def _require_yaml_support():
    if yaml is None:
        raise ContextValidationError(
            "PyYAML is required to load NextLens context files. "
            "Install PyYAML before running the context parser."
        ) from _YAML_IMPORT_ERROR
    return yaml


def _normalize_context_input(
    context: LoadedContext | Mapping[str, Any],
) -> tuple[Mapping[str, Any], tuple[str, ...]]:
    if isinstance(context, LoadedContext):
        return context.payload, context.warnings
    return context, ()


def _extract_payload(document: Mapping[str, Any], source_label: str) -> tuple[Mapping[str, Any], str | None]:
    if ENVELOPE_KEY not in document:
        return document, None

    payload = document[ENVELOPE_KEY]
    if not isinstance(payload, Mapping):
        raise ContextValidationError(
            f"Field '{ENVELOPE_KEY}' in {source_label} must contain a mapping."
        )
    return payload, ENVELOPE_KEY


def _validate_payload(payload: Mapping[str, Any], source_label: str) -> list[str]:
    missing_fields: list[str] = []
    invalid_fields: list[str] = []

    for field_name in REQUIRED_ROOT_FIELDS:
        if field_name not in payload:
            missing_fields.append(field_name)

    if "schemaVersion" in payload and _is_blank(payload.get("schemaVersion")):
        invalid_fields.append("schemaVersion must be a non-empty string")

    _validate_required_objects(payload, missing_fields, invalid_fields)
    _validate_required_collections(payload, missing_fields, invalid_fields)

    if missing_fields or invalid_fields:
        raise ContextValidationError(
            _build_validation_error_message(source_label, missing_fields, invalid_fields)
        )

    schema_version = str(payload["schemaVersion"]).strip()
    if schema_version != EXPECTED_SCHEMA_VERSION:
        return [
            "Schema version mismatch: expected "
            f"'{EXPECTED_SCHEMA_VERSION}' but received '{schema_version}'. Continuing with a warning."
        ]

    return []


def _validate_required_objects(
    payload: Mapping[str, Any],
    missing_fields: list[str],
    invalid_fields: list[str],
) -> None:
    for object_name, required_fields in REQUIRED_OBJECT_FIELDS.items():
        if object_name not in payload:
            continue

        value = payload[object_name]
        if not isinstance(value, Mapping):
            invalid_fields.append(f"{object_name} must be a mapping")
            continue

        for field_name in required_fields:
            field_path = f"{object_name}.{field_name}"
            if field_name not in value or _is_blank(value.get(field_name)):
                missing_fields.append(field_path)


def _validate_required_collections(
    payload: Mapping[str, Any],
    missing_fields: list[str],
    invalid_fields: list[str],
) -> None:
    for collection_name, required_fields in REQUIRED_COLLECTION_ITEM_FIELDS.items():
        if collection_name not in payload:
            continue

        value = payload[collection_name]
        if not isinstance(value, list):
            invalid_fields.append(f"{collection_name} must be a list")
            continue

        for index, item in enumerate(value):
            item_path = f"{collection_name}[{index}]"
            if not isinstance(item, Mapping):
                invalid_fields.append(f"{item_path} must be a mapping")
                continue

            for field_name in required_fields:
                field_path = f"{item_path}.{field_name}"
                if field_name not in item or _is_blank(item.get(field_name)):
                    missing_fields.append(field_path)


def _build_validation_error_message(
    source_label: str,
    missing_fields: list[str],
    invalid_fields: list[str],
) -> str:
    parts = [f"Context validation failed for {source_label}."]
    if missing_fields:
        parts.append("Missing required field(s): " + ", ".join(sorted(set(missing_fields))) + ".")
    if invalid_fields:
        parts.append("Invalid field(s): " + ", ".join(sorted(set(invalid_fields))) + ".")
    return " ".join(parts)


def _evaluate_system_thesis(
    payload: Mapping[str, Any],
    missing_required: list[str],
) -> ContextSufficiencyGate:
    system = payload.get("system")
    thesis = ""
    if isinstance(system, Mapping):
        thesis = str(system.get("thesis") or "").strip()
    passed = bool(thesis)
    if not passed:
        missing_required.append("system_thesis")
    return ContextSufficiencyGate(
        name="system_thesis",
        passed=passed,
        detail=thesis or "missing",
    )


def _evaluate_role_coverage(
    payload: Mapping[str, Any],
    missing_required: list[str],
) -> ContextSufficiencyGate:
    roles = _as_list(payload.get("roles"))
    count = len(roles)
    passed = count > 0
    if not passed:
        missing_required.append("role_coverage")
    return ContextSufficiencyGate(
        name="role_coverage",
        passed=passed,
        detail=f"{count} roles",
    )


def _evaluate_outcome_coverage(
    payload: Mapping[str, Any],
    missing_required: list[str],
) -> ContextSufficiencyGate:
    outcomes = _as_list(payload.get("outcomes"))
    count = len(outcomes)
    passed = count > 0
    if not passed:
        missing_required.append("outcome_coverage")
    return ContextSufficiencyGate(
        name="outcome_coverage",
        passed=passed,
        detail=f"{count} outcomes",
    )


def _evaluate_journey_coverage(
    payload: Mapping[str, Any],
    missing_required: list[str],
) -> ContextSufficiencyGate:
    journeys = _as_list(payload.get("journeys"))
    hypotheses = _journey_hypothesis_count(payload)
    count = len(journeys) + hypotheses
    passed = count > 0
    if not passed:
        missing_required.append("journey_coverage")
    return ContextSufficiencyGate(
        name="journey_coverage",
        passed=passed,
        detail=f"{count} journeys",
    )


def _evaluate_candidate_traceability(
    payload: Mapping[str, Any],
    missing_required: list[str],
) -> ContextSufficiencyGate:
    candidates = [item for item in _as_list(payload.get("candidateFeatures")) if isinstance(item, Mapping)]
    traceable_count = sum(1 for candidate in candidates if _candidate_has_traceability(candidate))
    passed = bool(candidates) and traceable_count == len(candidates)
    if not passed:
        missing_required.append("candidate_traceability")
    return ContextSufficiencyGate(
        name="candidate_traceability",
        passed=passed,
        detail=f"{traceable_count} candidates traceable",
    )


def _evaluate_risks_and_questions(
    payload: Mapping[str, Any],
    missing_required: list[str],
    warnings: list[str],
) -> ContextSufficiencyGate:
    risks = payload.get("risks")
    open_questions = payload.get("openQuestions")
    risks_list = _as_list(risks) if isinstance(risks, list) else None
    open_questions_list = _as_list(open_questions) if isinstance(open_questions, list) else None
    passed = risks_list is not None and open_questions_list is not None
    if not passed:
        missing_required.append("risks_captured")
        return ContextSufficiencyGate(
            name="risks_captured",
            passed=False,
            detail="missing",
        )

    if len(risks_list) < 3:
        warnings.append(f"risks_captured has fewer than 3 risks ({len(risks_list)}).")
    if len(open_questions_list) < 3:
        warnings.append(
            "risks_captured has fewer than 3 open questions "
            f"({len(open_questions_list)})."
        )

    return ContextSufficiencyGate(
        name="risks_captured",
        passed=True,
        detail=f"{len(risks_list)} risks",
    )


def _evaluate_bmad_consumer_context(
    payload: Mapping[str, Any],
    warnings: list[str],
) -> ContextSufficiencyGate:
    raw_value = payload.get("bmadConsumerContext")
    present = _has_meaningful_value(raw_value)
    if not present:
        warnings.append("bmad_hints is missing bmadConsumerContext.")
    return ContextSufficiencyGate(
        name="bmad_hints",
        passed=present,
        detail="present hints" if present else "missing hints",
    )


def _journey_hypothesis_count(payload: Mapping[str, Any]) -> int:
    total = 0
    for key in ("journeyHypotheses", "journey_hypotheses", "hypotheses"):
        value = payload.get(key)
        if isinstance(value, list):
            total += len(value)
    return total


def _candidate_has_traceability(candidate: Mapping[str, Any]) -> bool:
    for key in (
        "journeyId",
        "journeyRef",
        "outcomeId",
        "outcomeRef",
    ):
        if _has_meaningful_value(candidate.get(key)):
            return True

    for key in (
        "journeyIds",
        "journeyRefs",
        "journeys",
        "outcomeIds",
        "outcomeRefs",
        "outcomes",
    ):
        value = candidate.get(key)
        if isinstance(value, list) and any(_has_meaningful_value(item) for item in value):
            return True

    for key in ("trace", "lineage"):
        value = candidate.get(key)
        if isinstance(value, Mapping) and _candidate_has_traceability(value):
            return True

    return False


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, list):
        return any(_has_meaningful_value(item) for item in value)
    return True


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False