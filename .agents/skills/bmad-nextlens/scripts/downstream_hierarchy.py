"""Downstream NextLens schema support for BMAD artifacts and implementation validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import PurePosixPath
import uuid
from typing import Any, Callable, Mapping, Sequence


BMAD_ARTIFACT_BUNDLE_SCHEMA_VERSION = "nextlens.bmad-artifact-bundle.v1"
IMPLEMENTATION_EVIDENCE_SCHEMA_VERSION = "nextlens.implementation-evidence.v1"
VALIDATION_RESULT_SCHEMA_VERSION = "nextlens.validation-result.v1"

VALIDATION_RESULT_STATUSES = ("pass", "pass_with_warnings", "failed", "salmon_required")

SCOPE_LEAK_TYPES = {"scope_leak", "scopeleak", "scope-leak"}
UPSTREAM_CHANGE_TYPES = {
    "upstream_assumption_change",
    "upstream_change",
    "assumption_change",
    "upstream-truth-change",
}


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    expected_type: str
    level: str = "error"
    actual_value: Any = None
    message: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "field": self.field,
            "expectedType": self.expected_type,
            "level": self.level,
            "message": self.message or f"{self.field} must be {self.expected_type}.",
        }
        if self.actual_value is not None:
            payload["actualValue"] = self.actual_value
        return payload


@dataclass(frozen=True)
class ValidationResult:
    status: str
    errors: tuple[ValidationIssue, ...] = field(default_factory=tuple)
    warnings: tuple[ValidationIssue, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "errors": [issue.to_payload() for issue in self.errors],
            "warnings": [issue.to_payload() for issue in self.warnings],
        }


@dataclass(frozen=True)
class ImplementationEvidenceValidationResult(ValidationResult):
    scope_leaks: tuple[str, ...] = field(default_factory=tuple)
    upstream_changes: tuple[str, ...] = field(default_factory=tuple)
    salmon_required: bool = False

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        payload.update(
            {
                "scopeLeaks": list(self.scope_leaks),
                "upstreamChanges": list(self.upstream_changes),
                "salmonRequired": self.salmon_required,
            }
        )
        return payload


def normalize_artifact_path(path: str) -> str:
    cleaned = str(path).strip().replace("\\", "/")
    normalized = str(PurePosixPath(cleaned))
    if not normalized or normalized == ".":
        raise ValueError("artifact path must be a non-empty file path.")
    if ".." in PurePosixPath(normalized).parts:
        raise ValueError("artifact path must be normalized without '..' segments.")
    return normalized


def build_bmad_artifact_bundle(
    *,
    packet_id: str,
    feature_id: str,
    artifacts: Sequence[Mapping[str, Any]],
    stories: Sequence[Mapping[str, Any]],
    bundle_id: str | None = None,
    now_factory: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    created_at = _utc_timestamp(now_factory)
    bundle = {
        "schemaVersion": BMAD_ARTIFACT_BUNDLE_SCHEMA_VERSION,
        "packetId": str(packet_id),
        "featureId": str(feature_id),
        "artifacts": [
            {
                "id": str(artifact.get("id") or ""),
                "type": str(artifact.get("type") or ""),
                "path": normalize_artifact_path(str(artifact.get("path") or "")),
                "status": str(artifact.get("status") or ""),
            }
            for artifact in artifacts
        ],
        "stories": [
            {
                "id": str(story.get("id") or ""),
                "title": str(story.get("title") or ""),
                "status": str(story.get("status") or ""),
                "tracesTo": _normalize_traces_to(story.get("tracesTo")),
                "createdAt": str(story.get("createdAt") or created_at),
            }
            for story in stories
        ],
        "createdAt": created_at,
    }
    if bundle_id:
        bundle["bundleId"] = str(bundle_id)
    return bundle


def validate_bmad_artifact_bundle(
    bundle: Mapping[str, Any],
    *,
    packet_trace: Mapping[str, Any] | None = None,
) -> ValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    if not isinstance(bundle, Mapping):
        return ValidationResult(
            status="fail",
            errors=(
                ValidationIssue(
                    field="bundle",
                    expected_type="object",
                    actual_value=bundle,
                    message="BMAD artifact bundle must be an object.",
                ),
            ),
        )

    _require_string(bundle, "schemaVersion", errors, expected_value=BMAD_ARTIFACT_BUNDLE_SCHEMA_VERSION)
    _require_string(bundle, "packetId", errors)
    _require_string(bundle, "featureId", errors)
    _require_array(bundle, "artifacts", errors)
    _require_array(bundle, "stories", errors)
    _require_timestamp(bundle, "createdAt", errors)

    artifacts = _sequence(bundle.get("artifacts"))
    stories = _sequence(bundle.get("stories"))
    artifact_ids: set[str] = set()

    for idx, artifact in enumerate(artifacts):
        prefix = f"artifacts[{idx}]"
        if not isinstance(artifact, Mapping):
            _append_issue(errors, prefix, "object", artifact)
            continue
        _require_string(artifact, f"{prefix}.id", errors)
        _require_string(artifact, f"{prefix}.type", errors)
        _require_string(artifact, f"{prefix}.status", errors)
        _require_normalized_path(artifact, f"{prefix}.path", errors)
        artifact_id = artifact.get("id")
        if isinstance(artifact_id, str) and artifact_id.strip():
            artifact_ids.add(artifact_id)

    packet_id = str(bundle.get("packetId") or "")
    feature_id = str(bundle.get("featureId") or "")
    trace_scope = _trace_scope(packet_trace or _mapping(bundle.get("trace")))
    for idx, story in enumerate(stories):
        prefix = f"stories[{idx}]"
        if not isinstance(story, Mapping):
            _append_issue(errors, prefix, "object", story)
            continue
        _require_string(story, f"{prefix}.id", errors)
        _require_string(story, f"{prefix}.title", errors)
        _require_string(story, f"{prefix}.status", errors)
        _require_timestamp(story, f"{prefix}.createdAt", errors)

        trace_info = _validate_story_traces(
            story.get("tracesTo"),
            field_name=f"{prefix}.tracesTo",
            errors=errors,
            allowed_artifact_ids=artifact_ids,
            packet_id=packet_id,
            feature_id=feature_id,
            trace_scope=trace_scope,
            require_lineage=not _is_optional_or_deferred_story(story),
            enforce_lineage_for_legacy=False,
        )
        if feature_id and not trace_info["has_feature"] and not trace_info["feature_present"]:
            errors.append(
                ValidationIssue(
                    field=f"{prefix}.tracesTo",
                    expected_type=f"include feature '{feature_id}'",
                    actual_value=story.get("tracesTo"),
                    message=f"{prefix}.tracesTo must include the selected feature id.",
                )
            )

    status = _status_from_issues(errors, warnings)
    return ValidationResult(status=status, errors=tuple(errors), warnings=tuple(warnings))


def build_implementation_evidence(
    *,
    packet_id: str,
    feature_id: str,
    source_type: str,
    bmad_artifact_bundle_ref: str,
    stories: Sequence[Mapping[str, Any]],
    scope_observations: Sequence[Mapping[str, Any]] | None = None,
    evidence_id: str | None = None,
    goal_evidence: Sequence[str] | None = None,
    outcome_evidence: Sequence[str] | None = None,
    journey_evidence: Sequence[str] | None = None,
    now_factory: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    created_at = _utc_timestamp(now_factory)
    return {
        "schemaVersion": IMPLEMENTATION_EVIDENCE_SCHEMA_VERSION,
        "evidenceId": str(evidence_id or uuid.uuid4()),
        "packetId": str(packet_id),
        "featureId": str(feature_id),
        "sourceType": str(source_type),
        "bmadArtifactBundleRef": str(bmad_artifact_bundle_ref),
        "stories": [
            {
                "id": str(story.get("id") or ""),
                "status": str(story.get("status") or ""),
                "tracesTo": _normalize_traces_to(story.get("tracesTo")),
                "evidenceRefs": list(_sequence(story.get("evidenceRefs"))),
            }
            for story in stories
        ],
        "goalEvidence": list(goal_evidence or []),
        "outcomeEvidence": list(outcome_evidence or []),
        "journeyEvidence": list(journey_evidence or []),
        "scopeObservations": [dict(obs) for obs in _sequence(scope_observations)],
        "createdAt": created_at,
    }


def validate_implementation_evidence(
    evidence: Mapping[str, Any],
    *,
    expected_packet_id: str | None = None,
    expected_feature_id: str | None = None,
    required_story_ids: Sequence[str] | None = None,
    optional_story_ids: Sequence[str] | None = None,
    packet_trace: Mapping[str, Any] | None = None,
) -> ImplementationEvidenceValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    if not isinstance(evidence, Mapping):
        return ImplementationEvidenceValidationResult(
            status="fail",
            errors=(
                ValidationIssue(
                    field="evidence",
                    expected_type="object",
                    actual_value=evidence,
                    message="Implementation evidence must be an object.",
                ),
            ),
        )

    _require_string(
        evidence,
        "schemaVersion",
        errors,
        expected_value=IMPLEMENTATION_EVIDENCE_SCHEMA_VERSION,
    )
    _require_string(evidence, "evidenceId", errors)
    _require_string(evidence, "packetId", errors)
    _require_string(evidence, "featureId", errors)
    _require_string(evidence, "sourceType", errors)
    _require_string(evidence, "bmadArtifactBundleRef", errors)
    _require_array(evidence, "stories", errors)
    _require_array(evidence, "scopeObservations", errors)
    _require_timestamp(evidence, "createdAt", errors)

    if expected_packet_id is not None and evidence.get("packetId") != expected_packet_id:
        errors.append(
            ValidationIssue(
                field="packetId",
                expected_type=f"string '{expected_packet_id}'",
                actual_value=evidence.get("packetId"),
                message="packetId must match the Feature packet id.",
            )
        )
    if expected_feature_id is not None and evidence.get("featureId") != expected_feature_id:
        errors.append(
            ValidationIssue(
                field="featureId",
                expected_type=f"string '{expected_feature_id}'",
                actual_value=evidence.get("featureId"),
                message="featureId must match the selected Feature.",
            )
        )

    packet_id = str(expected_packet_id or evidence.get("packetId") or "")
    feature_id = str(expected_feature_id or evidence.get("featureId") or "")
    trace_scope = _trace_scope(packet_trace or _mapping(evidence.get("trace")))
    top_level_outcomes = _sequence(evidence.get("outcomeEvidence"))
    top_level_journeys = _sequence(evidence.get("journeyEvidence"))
    optional_set = {str(item) for item in (optional_story_ids or []) if str(item).strip()}
    story_ids: set[str] = set()
    for idx, story in enumerate(_sequence(evidence.get("stories"))):
        prefix = f"stories[{idx}]"
        if not isinstance(story, Mapping):
            _append_issue(errors, prefix, "object", story)
            continue
        _require_string(story, f"{prefix}.id", errors)
        _require_string(story, f"{prefix}.status", errors)
        story_id = story.get("id")
        if isinstance(story_id, str) and story_id.strip():
            story_ids.add(story_id)
        require_lineage = (
            _is_completed_story(story)
            and str(story_id or "") not in optional_set
            and not _is_optional_or_deferred_story(story)
        )
        trace_info = _validate_story_traces(
            story.get("tracesTo"),
            field_name=f"{prefix}.tracesTo",
            errors=errors,
            allowed_artifact_ids=set(),
            packet_id=packet_id,
            feature_id=feature_id,
            trace_scope=trace_scope,
            require_lineage=require_lineage,
            enforce_lineage_for_legacy=require_lineage
            and (not top_level_outcomes or not top_level_journeys),
        )
        if feature_id and not trace_info["has_feature"] and not trace_info["feature_present"]:
            errors.append(
                ValidationIssue(
                    field=f"{prefix}.tracesTo",
                    expected_type=f"include feature '{feature_id}'",
                    actual_value=story.get("tracesTo"),
                    message=f"{prefix}.tracesTo must include the selected feature id.",
                )
            )

    required_set = {str(item) for item in (required_story_ids or []) if str(item).strip()}
    missing_required = sorted(required_set - story_ids)
    if missing_required:
        errors.append(
            ValidationIssue(
                field="stories.missing",
                expected_type="story evidence for required stories",
                actual_value=missing_required,
                message="Missing implementation evidence for required stories.",
            )
        )
    missing_optional = sorted(optional_set - story_ids)
    if missing_optional:
        warnings.append(
            ValidationIssue(
                field="stories.optional",
                expected_type="story evidence for optional stories",
                actual_value=missing_optional,
                message="Missing implementation evidence for optional stories.",
                level="warning",
            )
        )

    scope_leaks, upstream_changes, salmon_required = _scope_signals(
        _sequence(evidence.get("scopeObservations"))
    )

    status = _status_from_issues(errors, warnings)
    return ImplementationEvidenceValidationResult(
        status=status,
        errors=tuple(errors),
        warnings=tuple(warnings),
        scope_leaks=tuple(scope_leaks),
        upstream_changes=tuple(upstream_changes),
        salmon_required=salmon_required,
    )


def build_validation_result(
    evidence: Mapping[str, Any] | None,
    *,
    expected_packet_id: str | None = None,
    expected_feature_id: str | None = None,
    required_story_ids: Sequence[str] | None = None,
    optional_story_ids: Sequence[str] | None = None,
    required_outcome_ids: Sequence[str] | None = None,
    optional_outcome_ids: Sequence[str] | None = None,
    required_journey_ids: Sequence[str] | None = None,
    optional_journey_ids: Sequence[str] | None = None,
    packet_trace: Mapping[str, Any] | None = None,
    now_factory: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    created_at = _utc_timestamp(now_factory)
    if not isinstance(evidence, Mapping):
        return {
            "schemaVersion": VALIDATION_RESULT_SCHEMA_VERSION,
            "status": "failed",
            "packetId": expected_packet_id,
            "featureId": expected_feature_id,
            "evidenceId": None,
            "goalStatus": "warning",
            "outcomeStatus": "warning",
            "journeyStatus": "warning",
            "scopeStatus": "warning",
            "evidenceStatus": "missing",
            "salmonRequired": False,
            "findings": [
                {
                    "category": "evidence",
                    "severity": "error",
                    "message": "Implementation evidence is required but missing.",
                }
            ],
            "createdAt": created_at,
        }

    validation = validate_implementation_evidence(
        evidence,
        expected_packet_id=expected_packet_id,
        expected_feature_id=expected_feature_id,
        required_story_ids=required_story_ids,
        optional_story_ids=optional_story_ids,
        packet_trace=packet_trace,
    )

    findings: list[dict[str, Any]] = []
    for issue in validation.errors:
        findings.append(_finding("evidence", "error", issue.message, issue.field))
    for issue in validation.warnings:
        findings.append(_finding("evidence", "warning", issue.message, issue.field))

    evidence_status = _section_status(validation.errors, validation.warnings)

    goal_status, goal_findings = _goal_status(evidence)
    findings.extend(goal_findings)

    outcome_status, outcome_findings = _coverage_status(
        "outcome",
        _sequence(evidence.get("outcomeEvidence")),
        required_outcome_ids,
        optional_outcome_ids,
    )
    findings.extend(outcome_findings)

    journey_status, journey_findings = _coverage_status(
        "journey",
        _sequence(evidence.get("journeyEvidence")),
        required_journey_ids,
        optional_journey_ids,
    )
    findings.extend(journey_findings)

    scope_status, scope_findings, salmon_required = _scope_status(
        _sequence(evidence.get("scopeObservations"))
    )
    findings.extend(scope_findings)

    overall_status = _overall_validation_status(
        evidence_status=evidence_status,
        goal_status=goal_status,
        outcome_status=outcome_status,
        journey_status=journey_status,
        scope_status=scope_status,
        salmon_required=salmon_required or validation.salmon_required,
    )

    result = {
        "schemaVersion": VALIDATION_RESULT_SCHEMA_VERSION,
        "status": overall_status,
        "packetId": evidence.get("packetId"),
        "featureId": evidence.get("featureId"),
        "evidenceId": evidence.get("evidenceId"),
        "goalStatus": goal_status,
        "outcomeStatus": outcome_status,
        "journeyStatus": journey_status,
        "scopeStatus": scope_status,
        "evidenceStatus": evidence_status,
        "salmonRequired": salmon_required or validation.salmon_required,
        "findings": findings,
        "createdAt": created_at,
    }
    return result


def validate_validation_result(result: Mapping[str, Any]) -> ValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    if not isinstance(result, Mapping):
        return ValidationResult(
            status="fail",
            errors=(
                ValidationIssue(
                    field="validationResult",
                    expected_type="object",
                    actual_value=result,
                    message="Validation result must be an object.",
                ),
            ),
        )

    _require_string(result, "schemaVersion", errors, expected_value=VALIDATION_RESULT_SCHEMA_VERSION)
    _require_enum(result, "status", VALIDATION_RESULT_STATUSES, errors)
    _require_string(result, "goalStatus", errors)
    _require_string(result, "outcomeStatus", errors)
    _require_string(result, "journeyStatus", errors)
    _require_string(result, "scopeStatus", errors)
    _require_string(result, "evidenceStatus", errors)
    _require_array(result, "findings", errors)
    _require_timestamp(result, "createdAt", errors)

    for field_name in ("packetId", "featureId", "evidenceId"):
        value = result.get(field_name)
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            _append_issue(errors, field_name, "string or null", value)

    if "salmonRequired" in result and not isinstance(result.get("salmonRequired"), bool):
        _append_issue(errors, "salmonRequired", "boolean", result.get("salmonRequired"))

    status = _status_from_issues(errors, warnings)
    return ValidationResult(status=status, errors=tuple(errors), warnings=tuple(warnings))


def _goal_status(evidence: Mapping[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    goal_evidence = _sequence(evidence.get("goalEvidence"))
    if goal_evidence:
        return "pass", []
    return (
        "warning",
        [_finding("goal", "warning", "Goal evidence is missing.")],
    )


def _coverage_status(
    category: str,
    evidence_ids: Sequence[Any],
    required_ids: Sequence[str] | None,
    optional_ids: Sequence[str] | None,
) -> tuple[str, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    evidence_set = {str(item) for item in evidence_ids if str(item).strip()}
    required_set = {str(item) for item in (required_ids or []) if str(item).strip()}
    optional_set = {str(item) for item in (optional_ids or []) if str(item).strip()}

    missing_required = sorted(required_set - evidence_set)
    missing_optional = sorted(optional_set - evidence_set)

    status = "pass"
    if missing_required:
        status = "fail"
        findings.append(
            _finding(
                category,
                "error",
                f"Missing required {category} evidence: {', '.join(missing_required)}.",
            )
        )
    if missing_optional:
        if status != "fail":
            status = "warning"
        findings.append(
            _finding(
                category,
                "warning",
                f"Missing optional {category} evidence: {', '.join(missing_optional)}.",
            )
        )
    if not required_set and not optional_set and not evidence_set:
        status = "warning"
        findings.append(
            _finding(
                category,
                "warning",
                f"No {category} evidence was supplied.",
            )
        )
    return status, findings


def _scope_status(scope_observations: Sequence[Any]) -> tuple[str, list[dict[str, Any]], bool]:
    scope_leaks, upstream_changes, salmon_required = _scope_signals(scope_observations)
    findings: list[dict[str, Any]] = []
    status = "pass"

    for leak in scope_leaks:
        findings.append(_finding("scope", "error", leak))
    for change in upstream_changes:
        findings.append(_finding("scope", "warning", change))

    if scope_leaks:
        status = "warning" if salmon_required else "fail"
    elif upstream_changes:
        status = "warning"

    return status, findings, salmon_required


def _overall_validation_status(
    *,
    evidence_status: str,
    goal_status: str,
    outcome_status: str,
    journey_status: str,
    scope_status: str,
    salmon_required: bool,
) -> str:
    if evidence_status == "missing":
        return "failed"
    if salmon_required:
        return "salmon_required"
    if "fail" in {evidence_status, goal_status, outcome_status, journey_status, scope_status}:
        return "failed"
    if "warning" in {evidence_status, goal_status, outcome_status, journey_status, scope_status}:
        return "pass_with_warnings"
    return "pass"


def _scope_signals(scope_observations: Sequence[Any]) -> tuple[list[str], list[str], bool]:
    scope_leaks: list[str] = []
    upstream_changes: list[str] = []
    salmon_required = False
    for observation in scope_observations:
        if not isinstance(observation, Mapping):
            continue
        obs_type = _normalized_observation_type(observation)
        description = str(
            observation.get("description")
            or observation.get("message")
            or observation.get("summary")
            or obs_type
            or "Scope observation recorded."
        )
        if obs_type in SCOPE_LEAK_TYPES:
            scope_leaks.append(description)
        if obs_type in UPSTREAM_CHANGE_TYPES:
            upstream_changes.append(description)
            salmon_required = True
        if _truthy(observation.get("requiresSalmon") or observation.get("salmonRequired")):
            salmon_required = True
    return scope_leaks, upstream_changes, salmon_required


def _normalized_observation_type(observation: Mapping[str, Any]) -> str:
    raw = (
        observation.get("type")
        or observation.get("category")
        or observation.get("observationType")
        or ""
    )
    return str(raw).strip().lower().replace(" ", "_").replace("-", "_")


def _finding(category: str, severity: str, message: str, reference: str | None = None) -> dict[str, Any]:
    payload = {"category": category, "severity": severity, "message": message}
    if reference:
        payload["reference"] = reference
    return payload


def _require_string(
    payload: Mapping[str, Any],
    field_name: str,
    issues: list[ValidationIssue],
    *,
    expected_value: str | None = None,
) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, str) or not value.strip():
        _append_issue(issues, field_name, "string", value)
        return
    if expected_value is not None and value != expected_value:
        issues.append(
            ValidationIssue(
                field=field_name,
                expected_type=f"string '{expected_value}'",
                actual_value=value,
                message=f"{field_name} must equal '{expected_value}'.",
            )
        )


def _require_enum(
    payload: Mapping[str, Any],
    field_name: str,
    allowed_values: Sequence[str],
    issues: list[ValidationIssue],
) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, str) or value not in allowed_values:
        issues.append(
            ValidationIssue(
                field=field_name,
                expected_type="one of " + ", ".join(allowed_values),
                actual_value=value,
                message=f"{field_name} must be one of: {', '.join(allowed_values)}.",
            )
        )


def _require_array(payload: Mapping[str, Any], field_name: str, issues: list[ValidationIssue]) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, list):
        _append_issue(issues, field_name, "array", value)


def _require_timestamp(payload: Mapping[str, Any], field_name: str, issues: list[ValidationIssue]) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, str) or not value.strip():
        _append_issue(issues, field_name, "ISO 8601 timestamp string", value)
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        issues.append(
            ValidationIssue(
                field=field_name,
                expected_type="ISO 8601 timestamp string",
                actual_value=value,
                message=f"{field_name} must be a valid ISO 8601 timestamp string.",
            )
        )


def _require_normalized_path(
    payload: Mapping[str, Any],
    field_name: str,
    issues: list[ValidationIssue],
) -> None:
    value = payload.get(_leaf_name(field_name))
    if not isinstance(value, str) or not value.strip():
        _append_issue(issues, field_name, "normalized path string", value)
        return
    try:
        normalized = normalize_artifact_path(value)
    except ValueError as exc:
        issues.append(
            ValidationIssue(
                field=field_name,
                expected_type="normalized path string",
                actual_value=value,
                message=str(exc),
            )
        )
        return
    if value != normalized:
        issues.append(
            ValidationIssue(
                field=field_name,
                expected_type=f"normalized path '{normalized}'",
                actual_value=value,
                message=f"{field_name} must be normalized to '{normalized}'.",
            )
        )


def _append_issue(
    issues: list[ValidationIssue],
    field_name: str,
    expected_type: str,
    actual_value: Any,
    *,
    level: str = "error",
) -> None:
    message = (
        f"{field_name} is required and must be {expected_type}."
        if actual_value is None
        else f"{field_name} must be {expected_type}; got {type(actual_value).__name__}."
    )
    issues.append(
        ValidationIssue(
            field=field_name,
            expected_type=expected_type,
            actual_value=actual_value,
            message=message,
            level=level,
        )
    )


def _normalize_traces_to(value: Any) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for scalar_key in ("packetId", "featureId"):
            if scalar_key in value:
                normalized[scalar_key] = str(value.get(scalar_key) or "")
        for list_key in ("artifactIds", "outcomeIds", "journeyIds"):
            if list_key in value:
                normalized[list_key] = list(_sequence(value.get(list_key)))
        return normalized
    return list(_sequence(value))


def _validate_story_traces(
    value: Any,
    *,
    field_name: str,
    errors: list[ValidationIssue],
    allowed_artifact_ids: set[str],
    packet_id: str,
    feature_id: str,
    trace_scope: Mapping[str, set[str]],
    require_lineage: bool,
    enforce_lineage_for_legacy: bool,
) -> dict[str, bool]:
    if isinstance(value, Mapping):
        return _validate_object_traces(
            value,
            field_name=field_name,
            errors=errors,
            allowed_artifact_ids=allowed_artifact_ids,
            packet_id=packet_id,
            feature_id=feature_id,
            trace_scope=trace_scope,
            require_lineage=require_lineage,
        )

    _require_array({"tracesTo": value}, field_name, errors)
    has_feature = False
    if isinstance(value, list):
        allowed_traces = allowed_artifact_ids | {feature_id, packet_id}
        for trace in value:
            if not isinstance(trace, str) or not trace.strip():
                _append_issue(errors, field_name, "non-empty string", trace)
            elif allowed_artifact_ids and trace not in allowed_traces:
                errors.append(
                    ValidationIssue(
                        field=field_name,
                        expected_type="known artifact or feature reference",
                        actual_value=trace,
                        message=f"{field_name} must reference a known artifact or feature.",
                    )
                )
            if trace == feature_id:
                has_feature = True
    if enforce_lineage_for_legacy:
        errors.append(
            ValidationIssue(
                field=field_name,
                expected_type="outcome and journey proof",
                actual_value=value,
                message=f"{field_name} must preserve outcome and journey proof for completed stories.",
            )
        )
    return {
        "has_feature": has_feature,
        "feature_present": has_feature,
        "has_outcome": False,
        "has_journey": False,
    }


def _validate_object_traces(
    traces: Mapping[str, Any],
    *,
    field_name: str,
    errors: list[ValidationIssue],
    allowed_artifact_ids: set[str],
    packet_id: str,
    feature_id: str,
    trace_scope: Mapping[str, set[str]],
    require_lineage: bool,
) -> dict[str, bool]:
    packet_value = traces.get("packetId")
    if packet_value is not None:
        _require_string(traces, f"{field_name}.packetId", errors)
        if packet_id and packet_value != packet_id:
            errors.append(
                ValidationIssue(
                    field=f"{field_name}.packetId",
                    expected_type=f"string '{packet_id}'",
                    actual_value=packet_value,
                    message=f"{field_name}.packetId must match the Feature packet id.",
                )
            )

    feature_value = traces.get("featureId")
    if feature_value is not None:
        _require_string(traces, f"{field_name}.featureId", errors)
        if feature_id and feature_value != feature_id:
            errors.append(
                ValidationIssue(
                    field=f"{field_name}.featureId",
                    expected_type=f"string '{feature_id}'",
                    actual_value=feature_value,
                    message=f"{field_name}.featureId must match the selected Feature.",
                )
            )

    artifact_ids = _validate_trace_id_list(
        traces,
        field_name=f"{field_name}.artifactIds",
        key="artifactIds",
        errors=errors,
    )
    if allowed_artifact_ids:
        unresolved_artifacts = sorted(set(artifact_ids) - allowed_artifact_ids)
        if unresolved_artifacts:
            errors.append(
                ValidationIssue(
                    field=f"{field_name}.artifactIds",
                    expected_type="known artifact ids",
                    actual_value=unresolved_artifacts,
                    message=f"{field_name}.artifactIds contains unresolved artifact ids.",
                )
            )

    outcome_ids = _validate_trace_id_list(
        traces,
        field_name=f"{field_name}.outcomeIds",
        key="outcomeIds",
        errors=errors,
    )
    journey_ids = _validate_trace_id_list(
        traces,
        field_name=f"{field_name}.journeyIds",
        key="journeyIds",
        errors=errors,
    )

    _append_unresolved_trace_ids(
        errors,
        field_name=f"{field_name}.outcomeIds",
        trace_ids=outcome_ids,
        allowed_ids=trace_scope.get("outcomeIds", set()),
        label="outcome",
    )
    _append_unresolved_trace_ids(
        errors,
        field_name=f"{field_name}.journeyIds",
        trace_ids=journey_ids,
        allowed_ids=trace_scope.get("journeyIds", set()),
        label="journey",
    )

    if require_lineage and not outcome_ids:
        errors.append(
            ValidationIssue(
                field=f"{field_name}.outcomeIds",
                expected_type="at least one outcome id",
                actual_value=outcome_ids,
                message=f"{field_name}.outcomeIds must include at least one outcome for non-deferred stories.",
            )
        )
    if require_lineage and not journey_ids:
        errors.append(
            ValidationIssue(
                field=f"{field_name}.journeyIds",
                expected_type="at least one journey id",
                actual_value=journey_ids,
                message=f"{field_name}.journeyIds must include at least one journey for non-deferred stories.",
            )
        )

    return {
        "has_feature": feature_value == feature_id,
        "feature_present": feature_value is not None,
        "has_outcome": bool(outcome_ids),
        "has_journey": bool(journey_ids),
    }


def _validate_trace_id_list(
    payload: Mapping[str, Any],
    *,
    field_name: str,
    key: str,
    errors: list[ValidationIssue],
) -> list[str]:
    if key not in payload:
        return []
    _require_array(payload, field_name, errors)
    values: list[str] = []
    for item in _sequence(payload.get(key)):
        if not isinstance(item, str) or not item.strip():
            _append_issue(errors, field_name, "non-empty string", item)
            continue
        values.append(item)
    return values


def _append_unresolved_trace_ids(
    errors: list[ValidationIssue],
    *,
    field_name: str,
    trace_ids: Sequence[str],
    allowed_ids: set[str],
    label: str,
) -> None:
    if not allowed_ids:
        return
    unresolved = sorted(set(trace_ids) - allowed_ids)
    if unresolved:
        errors.append(
            ValidationIssue(
                field=field_name,
                expected_type=f"known packet trace {label} ids",
                actual_value=unresolved,
                message=f"{field_name} contains unresolved {label} ids.",
            )
        )


def _trace_scope(trace: Mapping[str, Any]) -> dict[str, set[str]]:
    return {
        "outcomeIds": {str(item) for item in _sequence(trace.get("outcomeIds")) if str(item).strip()},
        "journeyIds": {str(item) for item in _sequence(trace.get("journeyIds")) if str(item).strip()},
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _is_optional_or_deferred_story(story: Mapping[str, Any]) -> bool:
    status = str(story.get("status") or "").strip().lower()
    return (
        status in {"optional", "deferred"}
        or _truthy(story.get("optional"))
        or _truthy(story.get("deferred"))
    )


def _is_completed_story(story: Mapping[str, Any]) -> bool:
    return str(story.get("status") or "").strip().lower() in {"done", "completed", "complete"}


def _status_from_issues(errors: Sequence[ValidationIssue], warnings: Sequence[ValidationIssue]) -> str:
    if errors:
        return "fail"
    if warnings:
        return "pass_with_warnings"
    return "pass"


def _section_status(errors: Sequence[ValidationIssue], warnings: Sequence[ValidationIssue]) -> str:
    if errors:
        return "fail"
    if warnings:
        return "warning"
    return "pass"


def _leaf_name(field_name: str) -> str:
    return field_name.rsplit(".", 1)[-1]


def _sequence(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _truthy(value: Any) -> bool:
    return bool(value) is True


def _utc_timestamp(now_factory: Callable[[], datetime] | None) -> str:
    now = now_factory() if now_factory else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
