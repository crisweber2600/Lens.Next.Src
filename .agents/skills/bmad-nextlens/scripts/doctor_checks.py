"""Pluggable non-mutating doctor check framework for NextLens."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import importlib.util
import sys
import uuid
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence


DOCTOR_CATEGORIES = frozenset({"schema", "scope", "traceability", "readiness"})
DOCTOR_SEVERITIES = frozenset({"blocking", "advisory", "informational"})
DOCTOR_STATUSES = frozenset({"pass", "warning", "fail"})
ADVISORY_CONFIRMATION_PROMPT = "Proceed with advisory findings? [Y/n]"
DEFAULT_DOCS_SUBPATH = ".nextlens"
DOCTOR_REPORT_NAME_TEMPLATE = "doctor-{run_id}.jsonl"
HANDOFF_REQUIRED_HINTS = ("prdInput", "uxInput", "architectureInput")
HANDOFF_OPTIONAL_HINTS = ("epicStoryInput", "readinessInput")


@dataclass(frozen=True)
class DoctorCheckContext:
    landscape_state: Any
    derived_graph: Mapping[str, Any]
    packet_candidate: Mapping[str, Any] | None = None
    selected_feature: Mapping[str, Any] | None = None
    docs_path: str | Path | None = None
    write_targets: Sequence[str] | None = None

    def read_only(self) -> "DoctorCheckContext":
        return DoctorCheckContext(
            landscape_state=_freeze_mapping(self.landscape_state),
            derived_graph=_freeze_mapping(self.derived_graph),
            packet_candidate=_freeze_mapping(self.packet_candidate or {}),
            selected_feature=_freeze_mapping(self.selected_feature or {}),
            docs_path=self.docs_path,
            write_targets=tuple(self.write_targets or ()),
        )


@dataclass(frozen=True)
class DoctorCheckResult:
    status: str
    severity: str
    message: str
    references: tuple[str, ...] = field(default_factory=tuple)
    remediation: str = ""
    check_id: str | None = None

    def __post_init__(self) -> None:
        if self.status not in DOCTOR_STATUSES:
            raise ValueError(f"Unsupported doctor status '{self.status}'.")
        if self.severity not in DOCTOR_SEVERITIES:
            raise ValueError(f"Unsupported doctor severity '{self.severity}'.")

    def to_payload(self, *, include_check_id: bool = False) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "severity": self.severity,
            "message": self.message,
            "references": list(self.references),
            "remediation": self.remediation,
        }
        if include_check_id and self.check_id:
            payload["check_id"] = self.check_id
        return payload


@dataclass(frozen=True)
class DoctorCheck:
    check_id: str
    name: str
    category: str
    severity: str
    description: str
    remediation: str
    execute: Callable[[DoctorCheckContext], DoctorCheckResult]

    def __post_init__(self) -> None:
        if not self.check_id.strip():
            raise ValueError("Doctor check requires a stable check_id.")
        if self.category not in DOCTOR_CATEGORIES:
            raise ValueError(f"Unsupported doctor category '{self.category}'.")
        if self.severity not in DOCTOR_SEVERITIES:
            raise ValueError(f"Unsupported doctor severity '{self.severity}'.")
        if not callable(self.execute):
            raise ValueError("Doctor check requires an execute function.")


@dataclass(frozen=True)
class DoctorExecutionLogEntry:
    check_id: str
    started_at: str
    completed_at: str
    status: str

    def to_payload(self) -> dict[str, str]:
        return {
            "checkId": self.check_id,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "status": self.status,
        }


@dataclass(frozen=True)
class DoctorRunResult:
    results: tuple[DoctorCheckResult, ...]
    blocking_results: tuple[DoctorCheckResult, ...]
    advisory_results: tuple[DoctorCheckResult, ...]
    informational_results: tuple[DoctorCheckResult, ...]
    execution_log: tuple[DoctorExecutionLogEntry, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "results": [result.to_payload(include_check_id=True) for result in self.results],
            "blockingResults": [result.to_payload() for result in self.blocking_results],
            "advisoryResults": [result.to_payload() for result in self.advisory_results],
            "informationalResults": [result.to_payload() for result in self.informational_results],
            "executionLog": [entry.to_payload() for entry in self.execution_log],
        }


@dataclass(frozen=True)
class DoctorPreFlightResult:
    run_id: str
    status: str
    allow_emission: bool
    report_path: Path | None
    operation_blocked: bool
    operator_prompted: bool
    operator_response: str | None
    run_result: DoctorRunResult

    def to_payload(self) -> dict[str, Any]:
        return {
            "runId": self.run_id,
            "status": self.status,
            "allowEmission": self.allow_emission,
            "operationBlocked": self.operation_blocked,
            "operatorPrompted": self.operator_prompted,
            "operatorResponse": self.operator_response,
            "reportPath": str(self.report_path) if self.report_path else None,
            "runResult": self.run_result.to_payload(),
        }


class DoctorCheckRegistry:
    def __init__(self) -> None:
        self._checks: dict[str, DoctorCheck] = {}

    def register(self, check: DoctorCheck) -> None:
        if check.check_id in self._checks:
            raise ValueError(f"Doctor check '{check.check_id}' is already registered.")
        self._checks[check.check_id] = check

    def list_checks(self) -> tuple[DoctorCheck, ...]:
        return tuple(self._checks[check_id] for check_id in sorted(self._checks))

    def run_all(self, context: DoctorCheckContext) -> DoctorRunResult:
        read_only_context = context.read_only()
        results: list[DoctorCheckResult] = []
        execution_log: list[DoctorExecutionLogEntry] = []

        for check in self.list_checks():
            started_at = _utc_timestamp()
            result = check.execute(read_only_context)
            completed_at = _utc_timestamp()

            if result.severity != check.severity:
                result = DoctorCheckResult(
                    status=result.status,
                    severity=check.severity,
                    message=result.message,
                    references=result.references,
                    remediation=result.remediation or check.remediation,
                    check_id=check.check_id,
                )
            elif result.check_id != check.check_id:
                result = DoctorCheckResult(
                    status=result.status,
                    severity=result.severity,
                    message=result.message,
                    references=result.references,
                    remediation=result.remediation or check.remediation,
                    check_id=check.check_id,
                )
            elif not result.check_id:
                result = DoctorCheckResult(
                    status=result.status,
                    severity=result.severity,
                    message=result.message,
                    references=result.references,
                    remediation=result.remediation,
                    check_id=check.check_id,
                )

            if result.status == "fail" and result.severity not in {"blocking", "advisory", "informational"}:
                raise ValueError("Invalid doctor result severity.")

            results.append(result)
            execution_log.append(
                DoctorExecutionLogEntry(
                    check_id=check.check_id,
                    started_at=started_at,
                    completed_at=completed_at,
                    status=result.status,
                )
            )

        return DoctorRunResult(
            results=tuple(results),
            blocking_results=tuple(
                result for result in results if result.severity == "blocking" and result.status == "fail"
            ),
            advisory_results=tuple(
                result for result in results
                if result.severity == "advisory" and result.status == "warning"
            ),
            informational_results=tuple(
                result for result in results
                if result.severity == "informational" and result.status == "warning"
            ),
            execution_log=tuple(execution_log),
        )


def build_default_doctor_check_registry() -> DoctorCheckRegistry:
    registry = DoctorCheckRegistry()
    for check in (
        _build_schema_validity_check(),
        _build_feature_scope_check(),
        _build_traceability_check(),
        _build_context_readiness_check(),
        _build_write_boundary_check(),
        _build_graph_consistency_check(),
        _build_handoff_required_artifacts_check(),
        _build_handoff_optional_artifacts_check(),
        _build_handoff_scope_check(),
        _build_bmad_artifact_bundle_check(),
        _build_bmad_story_trace_check(),
        _build_implementation_evidence_schema_check(),
        _build_implementation_evidence_identity_check(),
        _build_validation_result_schema_check(),
        _build_salmon_signal_schema_check(),
        _build_landscape_update_schema_check(),
        _build_derived_graph_authority_check(),
        _build_derived_graph_stale_check(),
        _build_review_evidence_check(),
    ):
        registry.register(check)
    return registry


def write_doctor_jsonl_report(
    run_result: DoctorRunResult,
    docs_path: str | Path,
    *,
    run_id: str | None = None,
) -> Path:
    run_id = run_id or _run_id()
    output_path = _doctor_report_path(docs_path, run_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    checks_run = len(run_result.results)
    passed = len([result for result in run_result.results if result.status != "fail"])
    blocked = len([result for result in run_result.blocking_results if result.status == "fail"])
    advisory = len(run_result.advisory_results)
    overall_status = _overall_doctor_status(run_result)
    payload_lines = []
    for result in sorted(
        run_result.results,
        key=lambda item: (0 if item.check_id == "context-readiness" else 1, item.check_id or ""),
    ):
        payload_lines.append(
            json.dumps(
                {
                    "timestamp": _utc_timestamp(),
                    "check_id": result.check_id,
                    **result.to_payload(include_check_id=False),
                },
                sort_keys=True,
            )
        )
    payload_lines.append(
        json.dumps(
            {
                "timestamp": _utc_timestamp(),
                "checks_run": checks_run,
                "passed": passed,
                "blocked": blocked,
                "advisory": advisory,
                "overall_status": overall_status,
            },
            sort_keys=True,
        )
    )
    output_path.write_text("\n".join(payload_lines) + "\n", encoding="utf-8")
    return output_path


def run_preflight_doctor_checks(
    context: DoctorCheckContext,
    registry: DoctorCheckRegistry | None = None,
    *,
    run_id: str | None = None,
    docs_path: str | Path | None = None,
    prompt_fn: Callable[[str], str] | None = None,
    include_report: bool = True,
) -> DoctorPreFlightResult:
    registry = registry or build_default_doctor_check_registry()
    run_id = run_id or _run_id()
    prompt = prompt_fn or input
    run_result = registry.run_all(context)
    report_output_path = docs_path or context.docs_path
    report_path = (
        write_doctor_jsonl_report(run_result, report_output_path, run_id=run_id)
        if include_report
        and report_output_path
        else None
    )
    if run_result.blocking_results:
        return DoctorPreFlightResult(
            run_id=run_id,
            status="blocked",
            allow_emission=False,
            report_path=report_path,
            operation_blocked=True,
            operator_prompted=False,
            operator_response=None,
            run_result=run_result,
        )

    if run_result.advisory_results:
        raw_response = prompt(ADVISORY_CONFIRMATION_PROMPT).strip().lower()
        proceed = raw_response in {"", "y", "yes"}
        return DoctorPreFlightResult(
            run_id=run_id,
            status="warning" if proceed else "blocked",
            allow_emission=proceed,
            report_path=report_path,
            operation_blocked=not proceed,
            operator_prompted=True,
            operator_response=raw_response,
            run_result=run_result,
        )

    return DoctorPreFlightResult(
        run_id=run_id,
        status="pass",
        allow_emission=True,
        report_path=report_path,
        operation_blocked=False,
        operator_prompted=False,
        operator_response=None,
        run_result=run_result,
    )


def _build_schema_validity_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="schema-validity",
        name="Schema validity",
        category="schema",
        severity="blocking",
        description="Validate all landscape entities and entity file integrity.",
        remediation="Re-run landscape extraction and repair invalid files.",
        execute=_check_schema_validity,
    )


def _build_feature_scope_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="feature-scope",
        name="Feature scope control",
        category="scope",
        severity="blocking",
        description="Validate selected feature scope does not spill beyond containment boundaries.",
        remediation="Constrain packet scope and populate explicitOutOfScope.",
        execute=_check_feature_scope,
    )


def _build_traceability_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="traceability",
        name="Feature traceability",
        category="traceability",
        severity="advisory",
        description="Validate packet trace links to authoritative landscape entities.",
        remediation="Update packet trace fields to include resolvable IDs.",
        execute=_check_traceability,
    )


def _build_context_readiness_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="context-readiness",
        name="Context readiness",
        category="readiness",
        severity="advisory",
        description="Validate top-down context readiness fields required by downstream stages.",
        remediation="Populate BMAD hints, thesis, roles, outcomes, journeys, risks, and open questions.",
        execute=_check_context_readiness,
    )


def _build_write_boundary_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="write-boundary",
        name="Write boundary",
        category="scope",
        severity="blocking",
        description="Validate write targets are within allowed docs path and outside protected boundaries.",
        remediation="Rewrite write targets to approved .nextlens/ control paths.",
        execute=_check_write_boundary,
    )


def _build_graph_consistency_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="graph-consistency",
        name="Derived graph consistency",
        category="schema",
        severity="advisory",
        description="Validate derived graph consistency against authoritative landscape state.",
        remediation="Rebuild graph from current landscape state and re-run checks.",
        execute=_check_graph_consistency,
    )


def _build_handoff_required_artifacts_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="handoff-artifacts-required",
        name="BMAD handoff artifacts required",
        category="readiness",
        severity="blocking",
        description="Verify required BMAD handoff artifacts referenced by the packet exist.",
        remediation="Generate BMAD handoff artifacts and update packet hints before downstream planning.",
        execute=_check_handoff_artifacts_required,
    )


def _build_handoff_optional_artifacts_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="handoff-artifacts-optional",
        name="BMAD handoff artifacts optional",
        category="readiness",
        severity="advisory",
        description="Check for optional BMAD handoff artifacts referenced by the packet.",
        remediation="Generate optional BMAD handoff artifacts when available.",
        execute=_check_handoff_artifacts_optional,
    )


def _build_handoff_scope_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="handoff-scope",
        name="BMAD handoff scope boundary",
        category="scope",
        severity="blocking",
        description="Ensure BMAD handoff files retain scope containment boundaries.",
        remediation="Add scope containment warning and avoid inviting scope expansion in handoff files.",
        execute=_check_handoff_scope,
    )


def _build_bmad_artifact_bundle_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="bmad-artifact-bundle",
        name="BMAD artifact bundle schema",
        category="schema",
        severity="blocking",
        description="Validate BMAD artifact bundle schema and required fields.",
        remediation="Repair BMAD artifact bundle schema issues before validation.",
        execute=_check_bmad_artifact_bundle,
    )


def _build_bmad_story_trace_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="bmad-story-trace",
        name="BMAD story traceability",
        category="traceability",
        severity="blocking",
        description="Validate BMAD story traces reference known artifacts or features.",
        remediation="Update BMAD story traces to reference valid artifacts and features.",
        execute=_check_bmad_story_trace,
    )


def _build_implementation_evidence_schema_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="implementation-evidence-schema",
        name="Implementation evidence schema",
        category="schema",
        severity="blocking",
        description="Validate implementation evidence schema when validation is requested.",
        remediation="Provide complete implementation evidence before validation.",
        execute=_check_implementation_evidence_schema,
    )


def _build_implementation_evidence_identity_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="implementation-evidence-identity",
        name="Implementation evidence identity",
        category="traceability",
        severity="blocking",
        description="Ensure implementation evidence packetId/featureId match the packet.",
        remediation="Align implementation evidence identifiers with the emitted packet.",
        execute=_check_implementation_evidence_identity,
    )


def _build_validation_result_schema_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="validation-result-schema",
        name="Validation result schema",
        category="schema",
        severity="blocking",
        description="Validate downstream validation result schema.",
        remediation="Repair validation result payload before downstream processing.",
        execute=_check_validation_result_schema,
    )


def _build_salmon_signal_schema_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="salmon-signal-schema",
        name="Salmon signal schema",
        category="schema",
        severity="blocking",
        description="Validate Salmon signal schema payloads.",
        remediation="Repair invalid Salmon signals before routing.",
        execute=_check_salmon_signal_schema,
    )


def _build_landscape_update_schema_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="landscape-update-schema",
        name="Landscape update schema",
        category="schema",
        severity="blocking",
        description="Validate landscape update proposal schema.",
        remediation="Repair landscape update payloads before applying.",
        execute=_check_landscape_update_schema,
    )


def _build_derived_graph_authority_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="derived-graph-authority",
        name="Derived graph authority",
        category="scope",
        severity="blocking",
        description="Prevent derived graph projections from being treated as authoritative.",
        remediation="Mark only curated landscape state as authoritative truth.",
        execute=_check_derived_graph_authority,
    )


def _build_derived_graph_stale_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="derived-graph-stale",
        name="Derived graph staleness",
        category="schema",
        severity="advisory",
        description="Detect stale derived graph projections.",
        remediation="Rebuild derived graph from current landscape state.",
        execute=_check_derived_graph_stale,
    )


def _build_review_evidence_check() -> DoctorCheck:
    return DoctorCheck(
        check_id="review-evidence",
        name="Optional review evidence",
        category="readiness",
        severity="advisory",
        description="Confirm optional review evidence is available for downstream validation.",
        remediation="Add goal, outcome, and journey evidence when available.",
        execute=_check_review_evidence,
    )


def _check_schema_validity(context: DoctorCheckContext) -> DoctorCheckResult:
    entities_by_id = _extract_landscape_entities(context.landscape_state)
    failures: list[str] = []
    if not entities_by_id:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="schema-validity",
            message="Landscape state has no entities.",
            references=("landscape_state",),
            remediation="Load landscape entities before running doctor checks.",
        )

    for entity_id, entity in entities_by_id.items():
        required_failures = _validate_entity_schema(entity_id, entity)
        failures.extend(required_failures)

    orphaned_files = _find_orphaned_files(context.landscape_state, context.docs_path)
    failures.extend(orphaned_files)

    warnings = _extract_entity_warnings(context.landscape_state)
    if warnings:
        failures.extend(warnings)

    if failures:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="schema-validity",
            message="Schema validity check found issues.",
            references=tuple(_dedupe_values(failures)),
            remediation="Rebuild invalid landscape state and refresh derived projection.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="schema-validity",
        message="All landscape entities pass schema checks.",
        references=tuple(sorted(entities_by_id)),
        remediation="",
    )


def _check_feature_scope(context: DoctorCheckContext) -> DoctorCheckResult:
    selected_feature = _as_mapping(context.selected_feature)
    included_scope = _as_list(selected_feature.get("includedScope"))
    explicit_out_of_scope = _as_list(selected_feature.get("explicitOutOfScope"))
    findings: list[str] = []
    offending: list[str] = []

    if not included_scope:
        findings.append("selectedFeature.includedScope must contain at least one scoped item")

    for scope_entry in included_scope:
        label = _scope_label(scope_entry)
        issue = _scope_issue(label)
        if issue:
            findings.append(issue)
            offending.append(label)

    if not explicit_out_of_scope:
        findings.append("selectedFeature.explicitOutOfScope must be populated")

    if findings:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="feature-scope",
            message="Feature scope check found blocking spillage risk.",
            references=tuple(_dedupe_values(offending)),
            remediation="Remove adjacent journeys, future features, and unrelated platform scopes from includedScope; populate explicitOutOfScope.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="feature-scope",
        message="Feature scope is constrained correctly.",
        references=(selected_feature.get("id", "selectedFeature"),),
        remediation="",
    )


def _check_traceability(context: DoctorCheckContext) -> DoctorCheckResult:
    landscape_state = context.landscape_state
    entities_by_id = _extract_landscape_entities(landscape_state)
    packet = _as_mapping(context.packet_candidate)
    trace = _as_mapping(packet.get("trace"))
    issues: list[str] = []
    references: list[str] = []

    system_id = str(trace.get("systemId") or "").strip()
    if not system_id:
        issues.append("packet.trace.systemId is missing")
        references.append("packet.trace.systemId")
    elif system_id not in entities_by_id:
        issues.append(f"systemId '{system_id}' does not resolve")
        references.append(system_id)

    discovery_epoch_id = str(trace.get("discoveryEpochId") or "").strip()
    if not discovery_epoch_id:
        issues.append("packet.trace.discoveryEpochId is missing")
        references.append("packet.trace.discoveryEpochId")

    role_ids = _as_list(trace.get("roleIds"))
    if not role_ids:
        issues.append("packet.trace.roleIds is missing")
        references.append("packet.trace.roleIds")
    role_invalid = _invalid_references(role_ids, _ids_by_type(entities_by_id, "role"))
    if role_invalid:
        issues.append(f"trace.roleIds contains unresolved ids: {', '.join(role_invalid)}")
        references.extend(role_invalid)

    outcome_ids = _as_list(trace.get("outcomeIds"))
    if not outcome_ids:
        issues.append("packet.trace.outcomeIds is missing")
        references.append("packet.trace.outcomeIds")
    outcome_invalid = _invalid_references(outcome_ids, _ids_by_type(entities_by_id, "outcome"))
    if outcome_invalid:
        issues.append(f"trace.outcomeIds contains unresolved ids: {', '.join(outcome_invalid)}")
        references.extend(outcome_invalid)

    journey_ids = _as_list(trace.get("journeyIds"))
    if not journey_ids:
        issues.append("packet.trace.journeyIds is missing")
        references.append("packet.trace.journeyIds")
    journey_invalid = _invalid_references(journey_ids, _ids_by_type(entities_by_id, "journey"))
    if journey_invalid:
        issues.append(f"trace.journeyIds contains unresolved ids: {', '.join(journey_invalid)}")
        references.extend(journey_invalid)

    selection_rationale = packet.get("selectionRationale")
    if not _has_meaningful_value(selection_rationale):
        issues.append("selectionRationale is required")
        references.append("packet.selectionRationale")

    if issues:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="traceability",
            message="Traceability is missing required top-down lineage or contains unresolved references.",
            references=tuple(_dedupe_values(references)),
            remediation="Populate discovery epoch, role, outcome, and journey trace fields with valid landscape IDs before emission.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="traceability",
        message="Packet traceability is resolvable.",
        references=(
            f"system:{system_id}",
            f"roles:{len(role_ids)}",
            f"outcomes:{len(outcome_ids)}",
            f"journeys:{len(journey_ids)}",
        ),
        remediation="",
    )


def _check_context_readiness(context: DoctorCheckContext) -> DoctorCheckResult:
    packet = _as_mapping(context.packet_candidate)
    blocking_missing: list[str] = []
    advisory_missing: list[str] = []
    hints = _as_mapping(packet.get("bmadConsumerHints"))
    if not hints:
        hints = _as_mapping(packet.get("bmadConsumerContext"))
    for field in ("prdInput", "uxInput", "architectureInput"):
        if not _has_meaningful_value(hints.get(field)):
            advisory_missing.append(field)

    system = _as_mapping(packet.get("system"))
    if not _has_meaningful_value(system.get("thesis")):
        blocking_missing.append("system.thesis")

    roles = _as_list(packet.get("roles"))
    outcomes = _as_list(packet.get("outcomes"))
    journeys = _as_list(packet.get("journeys"))
    if not roles:
        roles = _as_list(_extract_by_type(packet, "roles"))
        if not roles:
            blocking_missing.append("roles")
    if not outcomes:
        outcomes = _as_list(_extract_by_type(packet, "outcomes"))
        if not outcomes:
            blocking_missing.append("outcomes")
    if not journeys:
        journeys = _as_list(_extract_by_type(packet, "journeys"))
        if not journeys:
            blocking_missing.append("journeys")

    open_questions = _as_list(packet.get("openQuestions"))
    risks = _as_list(packet.get("risks"))
    if not open_questions:
        advisory_missing.append("openQuestions")
    if not risks:
        advisory_missing.append("risks")

    if blocking_missing:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="context-readiness",
            message="Context readiness check found missing required top-down context.",
            references=tuple(blocking_missing),
            remediation="Populate system thesis, role, outcome, and journey context before emission.",
        )
    if advisory_missing:
        return DoctorCheckResult(
            status="warning",
            severity="advisory",
            check_id="context-readiness",
            message="Context readiness check found advisory gaps.",
            references=tuple(advisory_missing),
            remediation="Populate BMAD hints, open questions, and risks before emission when available.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="advisory",
        check_id="context-readiness",
        message="Context readiness checks passed.",
        references=(
            "bmadConsumerHints",
            "roles",
            "outcomes",
            "journeys",
            "openQuestions",
            "risks",
        ),
        remediation="",
    )


def _check_write_boundary(context: DoctorCheckContext) -> DoctorCheckResult:
    if not context.docs_path:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="write-boundary",
            message="docs_path is required for boundary validation.",
            references=("docs_path",),
            remediation="Provide docs_path before running write-boundary check.",
        )

    docs_root = Path(context.docs_path).resolve()
    write_targets = tuple(context.write_targets or ())
    if not write_targets:
        return DoctorCheckResult(
            status="pass",
            severity="blocking",
            check_id="write-boundary",
            message="No write targets were submitted; boundary check skipped.",
            references=(),
            remediation="",
        )

    bad_targets: list[str] = []
    invalid_reasons: list[str] = []
    for raw_target in write_targets:
        if not isinstance(raw_target, str):
            invalid_reasons.append("Non-string write target.")
            continue
        target = Path(raw_target)
        target = target if target.is_absolute() else docs_root / target
        normalized_target = target.resolve()
        if not _is_within_docs_root(normalized_target, docs_root):
            bad_targets.append(raw_target)
            invalid_reasons.append(f"{raw_target} is outside docs path")
            continue

        target_parts = {part.lower() for part in normalized_target.parts}
        if "governance" in target_parts:
            bad_targets.append(raw_target)
            invalid_reasons.append(f"{raw_target} targets governance path")
            continue
        if "release" in target_parts or "release-clone" in target_parts:
            bad_targets.append(raw_target)
            invalid_reasons.append(f"{raw_target} targets release clone path")

    if bad_targets:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="write-boundary",
            message="Write boundary check found one or more blocked targets.",
            references=tuple(_dedupe_values(invalid_reasons)),
            remediation="Move all writes to control docs path within .nextlens and avoid governance/release targets.",
        )

    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="write-boundary",
        message="All write targets are within approved boundaries.",
        references=tuple(write_targets),
        remediation="",
    )


def _check_graph_consistency(context: DoctorCheckContext) -> DoctorCheckResult:
    derived_graph = _load_runtime_module("derived_graph", "derived_graph.py")

    graph_payload = _as_mapping(context.derived_graph)
    graph_payload = dict(
        graph_payload.items()
    )
    for key in ("nodes", "edges"):
        value = graph_payload.get(key, ())
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            graph_payload[key] = list(value)

    if not graph_payload:
        return DoctorCheckResult(
            status="warning",
            severity="advisory",
            check_id="graph-consistency",
            message="No derived graph payload was provided.",
            references=("derived_graph",),
            remediation="Build a derived graph and persist it before running the consistency check.",
        )

    try:
        validation = derived_graph.validate_graph_consistency(graph_payload, context.landscape_state)
    except Exception as exc:
        return DoctorCheckResult(
            status="warning",
            severity="advisory",
            check_id="graph-consistency",
            message=f"Derived graph consistency validation failed: {exc}",
            references=(),
            remediation="Regenerate derived graph from valid landscape entities and re-run checks.",
        )

    issues = tuple(issue.message for issue in validation.issues)
    if validation.status == "pass":
        return DoctorCheckResult(
            status="pass",
            severity="advisory",
            check_id="graph-consistency",
            message="Derived graph is consistent with authoritative landscape.",
            references=(),
            remediation="",
        )
    if validation.status == "advisory":
        return DoctorCheckResult(
            status="warning",
            severity="advisory",
            check_id="graph-consistency",
            message="Derived graph has consistency warnings.",
            references=tuple(_dedupe_values(issues)),
            remediation="Review warnings and rebuild the graph if needed.",
        )
    return DoctorCheckResult(
        status="warning",
        severity="advisory",
        check_id="graph-consistency",
        message="Derived graph has consistency problems.",
        references=tuple(_dedupe_values(issues)),
        remediation="Rebuild derived graph and repair referenced relationships before emission.",
    )


def _check_handoff_artifacts_required(context: DoctorCheckContext) -> DoctorCheckResult:
    packet = _as_mapping(context.packet_candidate)
    hints = _extract_handoff_hints(packet)
    if not hints:
        return DoctorCheckResult(
            status="pass",
            severity="blocking",
            check_id="handoff-artifacts-required",
            message="No BMAD handoff hints were provided.",
            references=(),
            remediation="",
        )

    docs_root = Path(context.docs_path) if context.docs_path else None
    missing: list[str] = []
    unresolved: list[str] = []
    for field in HANDOFF_REQUIRED_HINTS:
        raw_value = hints.get(field)
        path = _resolve_handoff_path(raw_value, docs_root)
        if path is None:
            continue
        if docs_root is None and not path.is_absolute():
            unresolved.append(field)
            continue
        if not path.exists():
            missing.append(f"{field}:{path}")

    if unresolved:
        return DoctorCheckResult(
            status="warning",
            severity="blocking",
            check_id="handoff-artifacts-required",
            message="docs_path is required to validate required BMAD handoff artifacts.",
            references=tuple(sorted(set(unresolved))),
            remediation="Provide docs_path to verify handoff artifacts.",
        )
    if missing:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="handoff-artifacts-required",
            message="Required BMAD handoff artifacts are missing.",
            references=tuple(_dedupe_values(missing)),
            remediation="Generate required BMAD handoff artifacts before downstream planning.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="handoff-artifacts-required",
        message="Required BMAD handoff artifacts are present.",
        references=tuple(sorted(HANDOFF_REQUIRED_HINTS)),
        remediation="",
    )


def _check_handoff_artifacts_optional(context: DoctorCheckContext) -> DoctorCheckResult:
    packet = _as_mapping(context.packet_candidate)
    hints = _extract_handoff_hints(packet)
    if not hints:
        return DoctorCheckResult(
            status="pass",
            severity="advisory",
            check_id="handoff-artifacts-optional",
            message="No BMAD handoff hints were provided.",
            references=(),
            remediation="",
        )

    docs_root = Path(context.docs_path) if context.docs_path else None
    missing: list[str] = []
    unresolved: list[str] = []
    for field in HANDOFF_OPTIONAL_HINTS:
        raw_value = hints.get(field)
        path = _resolve_handoff_path(raw_value, docs_root)
        if path is None:
            continue
        if docs_root is None and not path.is_absolute():
            unresolved.append(field)
            continue
        if not path.exists():
            missing.append(f"{field}:{path}")

    if unresolved:
        return DoctorCheckResult(
            status="warning",
            severity="advisory",
            check_id="handoff-artifacts-optional",
            message="docs_path is required to validate optional BMAD handoff artifacts.",
            references=tuple(sorted(set(unresolved))),
            remediation="Provide docs_path to verify optional handoff artifacts.",
        )
    if missing:
        return DoctorCheckResult(
            status="warning",
            severity="advisory",
            check_id="handoff-artifacts-optional",
            message="Optional BMAD handoff artifacts are missing.",
            references=tuple(_dedupe_values(missing)),
            remediation="Generate optional BMAD handoff artifacts when available.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="advisory",
        check_id="handoff-artifacts-optional",
        message="Optional BMAD handoff artifacts are present.",
        references=tuple(sorted(HANDOFF_OPTIONAL_HINTS)),
        remediation="",
    )


def _check_handoff_scope(context: DoctorCheckContext) -> DoctorCheckResult:
    packet = _as_mapping(context.packet_candidate)
    hints = _extract_handoff_hints(packet)
    docs_root = Path(context.docs_path) if context.docs_path else None
    if not hints or docs_root is None:
        return DoctorCheckResult(
            status="pass",
            severity="blocking",
            check_id="handoff-scope",
            message="No BMAD handoff files were provided for scope validation.",
            references=(),
            remediation="",
        )

    handoff_module = _load_runtime_module("bmad_handoff", "bmad_handoff.py")
    issues: list[str] = []
    for raw_value in hints.values():
        path = _resolve_handoff_path(raw_value, docs_root)
        if path is None or not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(f"{path}: unable to read ({exc})")
            continue

        boundary_issues = _handoff_boundary_issues(content, handoff_module)
        issues.extend(f"{path}: {issue}" for issue in boundary_issues)
        expansion_lines = _handoff_expansion_invites(content)
        issues.extend(f"{path}: {line}" for line in expansion_lines)

    if issues:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="handoff-scope",
            message="BMAD handoff scope boundary violations detected.",
            references=tuple(_dedupe_values(issues)),
            remediation="Restore scope containment warning and remove expansion invitations from handoff files.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="handoff-scope",
        message="BMAD handoff files preserve scope boundaries.",
        references=(),
        remediation="",
    )


def _check_bmad_artifact_bundle(context: DoctorCheckContext) -> DoctorCheckResult:
    bundle, errors = _load_downstream_payload(context, "bmad_artifact_bundle")
    if errors:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="bmad-artifact-bundle",
            message="Failed to load BMAD artifact bundle.",
            references=tuple(_dedupe_values(errors)),
            remediation="Repair BMAD artifact bundle references before validation.",
        )
    if not bundle:
        return DoctorCheckResult(
            status="pass",
            severity="blocking",
            check_id="bmad-artifact-bundle",
            message="No BMAD artifact bundle was supplied.",
            references=(),
            remediation="",
        )

    downstream = _load_runtime_module("downstream_hierarchy", "downstream_hierarchy.py")
    validation = downstream.validate_bmad_artifact_bundle(bundle)
    if validation.errors:
        issues = [issue.message or issue.field for issue in validation.errors]
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="bmad-artifact-bundle",
            message="BMAD artifact bundle schema validation failed.",
            references=tuple(_dedupe_values(issues)),
            remediation="Repair BMAD artifact bundle schema errors before downstream validation.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="bmad-artifact-bundle",
        message="BMAD artifact bundle schema is valid.",
        references=(),
        remediation="",
    )


def _check_bmad_story_trace(context: DoctorCheckContext) -> DoctorCheckResult:
    bundle, errors = _load_downstream_payload(context, "bmad_artifact_bundle")
    if errors or not bundle:
        return DoctorCheckResult(
            status="pass",
            severity="blocking",
            check_id="bmad-story-trace",
            message="No BMAD artifact bundle was supplied for story trace checks.",
            references=(),
            remediation="",
        )

    downstream = _load_runtime_module("downstream_hierarchy", "downstream_hierarchy.py")
    validation = downstream.validate_bmad_artifact_bundle(bundle)
    trace_errors = [
        issue.message or issue.field
        for issue in validation.errors
        if "tracesTo" in issue.field
    ]
    if trace_errors:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="bmad-story-trace",
            message="BMAD story traceability is invalid.",
            references=tuple(_dedupe_values(trace_errors)),
            remediation="Ensure BMAD story traces reference known artifacts or feature identifiers.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="bmad-story-trace",
        message="BMAD story traceability is valid.",
        references=(),
        remediation="",
    )


def _check_implementation_evidence_schema(context: DoctorCheckContext) -> DoctorCheckResult:
    packet = _as_mapping(context.packet_candidate)
    evidence, errors = _load_downstream_payload(context, "implementation_evidence")
    validation_requested = _validation_requested(packet)
    if errors:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="implementation-evidence-schema",
            message="Failed to load implementation evidence.",
            references=tuple(_dedupe_values(errors)),
            remediation="Repair implementation evidence references before validation.",
        )
    if not evidence:
        if validation_requested:
            return DoctorCheckResult(
                status="fail",
                severity="blocking",
                check_id="implementation-evidence-schema",
                message="Implementation evidence is required for validation but missing.",
                references=("implementationEvidence",),
                remediation="Provide implementation evidence before running validation.",
            )
        return DoctorCheckResult(
            status="pass",
            severity="blocking",
            check_id="implementation-evidence-schema",
            message="No implementation evidence supplied.",
            references=(),
            remediation="",
        )

    downstream = _load_runtime_module("downstream_hierarchy", "downstream_hierarchy.py")
    validation = downstream.validate_implementation_evidence(evidence)
    schema_errors = [
        issue.message or issue.field
        for issue in validation.errors
        if issue.field not in {"packetId", "featureId"}
    ]
    if schema_errors and validation_requested:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="implementation-evidence-schema",
            message="Implementation evidence schema validation failed.",
            references=tuple(_dedupe_values(schema_errors)),
            remediation="Repair implementation evidence schema issues before validation.",
        )
    if schema_errors:
        return DoctorCheckResult(
            status="warning",
            severity="blocking",
            check_id="implementation-evidence-schema",
            message="Implementation evidence schema has issues.",
            references=tuple(_dedupe_values(schema_errors)),
            remediation="Repair implementation evidence schema issues before validation.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="implementation-evidence-schema",
        message="Implementation evidence schema is valid.",
        references=(),
        remediation="",
    )


def _check_implementation_evidence_identity(context: DoctorCheckContext) -> DoctorCheckResult:
    packet = _as_mapping(context.packet_candidate)
    evidence, errors = _load_downstream_payload(context, "implementation_evidence")
    if errors or not evidence:
        return DoctorCheckResult(
            status="pass",
            severity="blocking",
            check_id="implementation-evidence-identity",
            message="No implementation evidence supplied for identity checks.",
            references=(),
            remediation="",
        )

    downstream = _load_runtime_module("downstream_hierarchy", "downstream_hierarchy.py")
    validation = downstream.validate_implementation_evidence(
        evidence,
        expected_packet_id=str(packet.get("packetId") or "") or None,
        expected_feature_id=str(packet.get("featureId") or "") or None,
    )
    mismatch_errors = [
        issue.message or issue.field
        for issue in validation.errors
        if issue.field in {"packetId", "featureId"}
    ]
    if mismatch_errors:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="implementation-evidence-identity",
            message="Implementation evidence identifiers do not match packet.",
            references=tuple(_dedupe_values(mismatch_errors)),
            remediation="Align implementation evidence packetId/featureId with the emitted packet.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="implementation-evidence-identity",
        message="Implementation evidence identifiers match packet.",
        references=(),
        remediation="",
    )


def _check_validation_result_schema(context: DoctorCheckContext) -> DoctorCheckResult:
    result_payload, errors = _load_downstream_payload(context, "validation_result")
    if errors:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="validation-result-schema",
            message="Failed to load validation result payload.",
            references=tuple(_dedupe_values(errors)),
            remediation="Repair validation result references before downstream processing.",
        )
    if not result_payload:
        return DoctorCheckResult(
            status="pass",
            severity="blocking",
            check_id="validation-result-schema",
            message="No validation result payload supplied.",
            references=(),
            remediation="",
        )

    downstream = _load_runtime_module("downstream_hierarchy", "downstream_hierarchy.py")
    validation = downstream.validate_validation_result(result_payload)
    if validation.errors:
        issues = [issue.message or issue.field for issue in validation.errors]
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="validation-result-schema",
            message="Validation result schema is invalid.",
            references=tuple(_dedupe_values(issues)),
            remediation="Repair validation result schema before downstream processing.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="validation-result-schema",
        message="Validation result schema is valid.",
        references=(),
        remediation="",
    )


def _check_salmon_signal_schema(context: DoctorCheckContext) -> DoctorCheckResult:
    events = _load_downstream_events(context)
    if not events:
        return DoctorCheckResult(
            status="pass",
            severity="blocking",
            check_id="salmon-signal-schema",
            message="No Salmon signals were supplied.",
            references=(),
            remediation="",
        )

    salmon_model = _load_runtime_module("salmon_event_model", "salmon_event_model.py")
    issues: list[str] = []
    for idx, event in enumerate(events):
        validation = salmon_model.validate_salmon_event(event)
        if not validation.is_valid:
            for error in validation.errors:
                issues.append(f"event[{idx}]: {error.message or error.field}")
    if issues:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="salmon-signal-schema",
            message="Salmon signal schema validation failed.",
            references=tuple(_dedupe_values(issues)),
            remediation="Repair Salmon signal payloads before routing.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="salmon-signal-schema",
        message="Salmon signal schema is valid.",
        references=(),
        remediation="",
    )


def _check_landscape_update_schema(context: DoctorCheckContext) -> DoctorCheckResult:
    updates = _load_downstream_updates(context)
    if not updates:
        return DoctorCheckResult(
            status="pass",
            severity="blocking",
            check_id="landscape-update-schema",
            message="No landscape updates were supplied.",
            references=(),
            remediation="",
        )

    downstream = _load_runtime_module("downstream_salmon_landscape", "downstream_salmon_landscape.py")
    issues: list[str] = []
    for idx, update in enumerate(updates):
        issues.extend(
            f"update[{idx}]: {issue}"
            for issue in _validate_landscape_update(update, downstream)
        )
    if issues:
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="landscape-update-schema",
            message="Landscape update schema validation failed.",
            references=tuple(_dedupe_values(issues)),
            remediation="Repair landscape update payloads before applying.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="landscape-update-schema",
        message="Landscape update schema is valid.",
        references=(),
        remediation="",
    )


def _check_derived_graph_authority(context: DoctorCheckContext) -> DoctorCheckResult:
    packet = _as_mapping(context.packet_candidate)
    if _has_authoritative_graph_flag(packet):
        return DoctorCheckResult(
            status="fail",
            severity="blocking",
            check_id="derived-graph-authority",
            message="Derived graph was marked as authoritative.",
            references=("derivedGraphAuthoritative",),
            remediation="Ensure derived graph outputs remain non-authoritative projections.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="blocking",
        check_id="derived-graph-authority",
        message="Derived graph remains non-authoritative.",
        references=(),
        remediation="",
    )


def _check_derived_graph_stale(context: DoctorCheckContext) -> DoctorCheckResult:
    graph_payload = _prepare_graph_payload(context.derived_graph)
    if not graph_payload:
        return DoctorCheckResult(
            status="pass",
            severity="advisory",
            check_id="derived-graph-stale",
            message="No derived graph payload was supplied.",
            references=(),
            remediation="",
        )

    derived_graph = _load_runtime_module("derived_graph", "derived_graph.py")
    try:
        validation = derived_graph.validate_graph_consistency(graph_payload, context.landscape_state)
    except Exception as exc:
        return DoctorCheckResult(
            status="warning",
            severity="advisory",
            check_id="derived-graph-stale",
            message=f"Derived graph staleness check failed: {exc}",
            references=(),
            remediation="Rebuild derived graph from current landscape state.",
        )

    stale_issues = [
        issue.message
        for issue in validation.issues
        if getattr(issue, "code", "") == "graph_checksum_stale"
        or "checksum" in issue.message.lower()
    ]
    if stale_issues:
        return DoctorCheckResult(
            status="warning",
            severity="advisory",
            check_id="derived-graph-stale",
            message="Derived graph appears stale.",
            references=tuple(_dedupe_values(stale_issues)),
            remediation="Rebuild derived graph from current landscape state.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="advisory",
        check_id="derived-graph-stale",
        message="Derived graph is current.",
        references=(),
        remediation="",
    )


def _check_review_evidence(context: DoctorCheckContext) -> DoctorCheckResult:
    evidence, errors = _load_downstream_payload(context, "implementation_evidence")
    if errors or not evidence:
        return DoctorCheckResult(
            status="pass",
            severity="advisory",
            check_id="review-evidence",
            message="No implementation evidence supplied for review evidence checks.",
            references=(),
            remediation="",
        )

    missing: list[str] = []
    if not _as_list(evidence.get("goalEvidence")):
        missing.append("goalEvidence")
    if not _as_list(evidence.get("outcomeEvidence")):
        missing.append("outcomeEvidence")
    if not _as_list(evidence.get("journeyEvidence")):
        missing.append("journeyEvidence")

    if missing:
        return DoctorCheckResult(
            status="warning",
            severity="advisory",
            check_id="review-evidence",
            message="Optional review evidence is missing.",
            references=tuple(missing),
            remediation="Provide goal, outcome, and journey evidence when available.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="advisory",
        check_id="review-evidence",
        message="Optional review evidence is present.",
        references=(),
        remediation="",
    )


def _extract_handoff_hints(packet: Mapping[str, Any]) -> Mapping[str, Any]:
    hints = _as_mapping(packet.get("bmadConsumerHints"))
    if not hints:
        hints = _as_mapping(packet.get("bmadConsumerContext"))
    return hints


def _resolve_handoff_path(value: Any, docs_root: Path | None) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    if not _looks_like_path(value):
        return None
    path = Path(value).expanduser()
    if not path.is_absolute() and docs_root:
        path = docs_root / path
    return path


def _looks_like_path(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered.endswith((".md", ".markdown")):
        return True
    if "/" in lowered or "\\" in lowered:
        return True
    return False


def _handoff_boundary_issues(content: str, handoff_module: Any) -> list[str]:
    lowered = content.lower()
    issues: list[str] = []
    warning_text = str(getattr(handoff_module, "DEFAULT_SCOPE_CONTAINMENT_WARNING", "")).lower()
    has_warning = "scope containment warning" in lowered or (warning_text and warning_text in lowered)
    if not has_warning:
        issues.append("missing scope containment warning")

    boundary_lines = [str(item).lower() for item in getattr(handoff_module, "BMAD_EXPANSION_BOUNDARY", ())]
    has_boundary_header = "bmad expansion boundary" in lowered
    has_boundary_line = any(line and line in lowered for line in boundary_lines)
    if not (has_boundary_header or has_boundary_line):
        issues.append("missing BMAD expansion boundary")
    return issues


def _handoff_expansion_invites(content: str) -> list[str]:
    invites: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if not line:
            continue
        if ("adjacent journey" in lower or "adjacent journeys" in lower) and _looks_like_expansion(lower):
            invites.append(f"invites adjacent journeys: {line}")
        if ("future feature" in lower or "future features" in lower) and _looks_like_expansion(lower):
            invites.append(f"invites future features: {line}")
    return invites


def _looks_like_expansion(line: str) -> bool:
    if any(term in line for term in ("do not", "don't", "avoid", "never")):
        return False
    return any(term in line for term in ("build", "implement", "expand", "include", "add"))


def _validation_requested(packet: Mapping[str, Any]) -> bool:
    if bool(packet.get("validationRequested") or packet.get("validationRequired")):
        return True
    downstream = _extract_downstream_mapping(packet)
    for key in ("validationResult", "validation", "validationResultRef"):
        if _has_meaningful_value(downstream.get(key) if downstream else None):
            return True
    return False


def _extract_downstream_mapping(packet: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("downstreamArtifacts", "downstreamHierarchy", "downstream", "downstream_hierarchy"):
        value = packet.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _load_downstream_payload(context: DoctorCheckContext, payload_key: str) -> tuple[Mapping[str, Any] | None, list[str]]:
    packet = _as_mapping(context.packet_candidate)
    downstream = _extract_downstream_mapping(packet)
    key_map = {
        "bmad_artifact_bundle": ("bmadArtifactBundle", "artifactBundle", "bmad_artifact_bundle"),
        "implementation_evidence": ("implementationEvidence", "implementation_evidence"),
        "validation_result": ("validationResult", "validation_result", "validation"),
    }
    ref_map = {
        "bmad_artifact_bundle": ("bmadArtifactBundleRef", "artifactBundleRef", "bmadArtifactBundlePath"),
        "implementation_evidence": ("implementationEvidenceRef", "implementationEvidencePath"),
        "validation_result": ("validationResultRef", "validationResultPath"),
    }
    payload = _first_value(downstream, key_map.get(payload_key, ())) or _first_value(packet, key_map.get(payload_key, ()))
    errors: list[str] = []
    if isinstance(payload, Mapping):
        return payload, errors
    if isinstance(payload, str) and payload.strip():
        payload, load_errors = _load_payload_from_ref(payload, context.docs_path)
        errors.extend(load_errors)
        return payload, errors

    ref = _first_value(downstream, ref_map.get(payload_key, ())) or _first_value(packet, ref_map.get(payload_key, ()))
    if isinstance(ref, str) and ref.strip():
        payload, load_errors = _load_payload_from_ref(ref, context.docs_path)
        errors.extend(load_errors)
        return payload, errors
    return None, errors


def _load_payload_from_ref(ref: str, docs_path: str | Path | None) -> tuple[Mapping[str, Any] | None, list[str]]:
    errors: list[str] = []
    path = Path(ref)
    if not path.is_absolute() and docs_path:
        path = Path(docs_path) / path
    if not path.exists():
        return None, [f"missing payload at {path}"]
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"unable to read payload at {path}: {exc}"]

    if path.suffix.lower() in {".json"}:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            return None, [f"invalid JSON at {path}: {exc}"]
        if not isinstance(payload, Mapping):
            return None, [f"payload at {path} must be an object"]
        return payload, []
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ModuleNotFoundError as exc:
            return None, [f"PyYAML not available for {path}: {exc}"]
        payload = yaml.safe_load(raw)
        if not isinstance(payload, Mapping):
            return None, [f"payload at {path} must be an object"]
        return payload, []
    return None, [f"unsupported payload format at {path}"]


def _first_value(mapping: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return None


def _load_downstream_events(context: DoctorCheckContext) -> list[Mapping[str, Any]]:
    packet = _as_mapping(context.packet_candidate)
    downstream = _extract_downstream_mapping(packet)
    for key in ("salmonSignals", "salmonEvents", "salmonSignal"):
        value = downstream.get(key) if downstream else packet.get(key)
        if isinstance(value, Mapping):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _load_downstream_updates(context: DoctorCheckContext) -> list[Mapping[str, Any]]:
    packet = _as_mapping(context.packet_candidate)
    downstream = _extract_downstream_mapping(packet)
    for key in ("landscapeUpdates", "landscapeUpdate", "landscapeUpdateProposal"):
        value = downstream.get(key) if downstream else packet.get(key)
        if isinstance(value, Mapping):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _validate_landscape_update(update: Mapping[str, Any], downstream_module: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(update, Mapping):
        return ["landscape update must be an object"]

    schema_version = str(update.get("schemaVersion") or "")
    if schema_version != downstream_module.LANDSCAPE_UPDATE_SCHEMA_VERSION:
        issues.append("schemaVersion mismatch")

    update_id = str(update.get("updateId") or "")
    if not update_id.strip():
        issues.append("updateId is required")

    status = str(update.get("status") or "").strip().lower()
    if status not in downstream_module.LANDSCAPE_UPDATE_STATUSES:
        issues.append("status is invalid")

    source_refs = update.get("sourceRefs")
    if source_refs is not None and not isinstance(source_refs, Mapping):
        issues.append("sourceRefs must be an object")

    updates = update.get("updates")
    if not isinstance(updates, list):
        issues.append("updates must be an array")
    else:
        for item in updates:
            if not isinstance(item, Mapping):
                issues.append("updates entries must be objects")
                continue
            try:
                downstream_module._normalize_update(item)
            except Exception as exc:
                issues.append(str(exc))
    return issues


def _has_authoritative_graph_flag(payload: Any) -> bool:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            lowered = str(key).lower()
            if lowered in {
                "derivedgraphauthoritative",
                "derivedgraphisauthoritative",
                "derived_graph_authoritative",
                "authoritativederivedgraph",
            } and _is_truthy_flag(value):
                return True
            if _has_authoritative_graph_flag(value):
                return True
    if isinstance(payload, list):
        return any(_has_authoritative_graph_flag(item) for item in payload)
    return False


def _is_truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


def _prepare_graph_payload(raw_payload: Any) -> Mapping[str, Any]:
    graph_payload = _as_mapping(raw_payload)
    if not graph_payload:
        return {}
    graph_payload = dict(graph_payload.items())
    for key in ("nodes", "edges"):
        value = graph_payload.get(key, ())
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            graph_payload[key] = list(value)
    return graph_payload


def _doctor_report_path(docs_path: str | Path, run_id: str) -> Path:
    return Path(docs_path) / DEFAULT_DOCS_SUBPATH / DOCTOR_REPORT_NAME_TEMPLATE.format(run_id=run_id)


def _extract_landscape_entities(landscape_state: Any) -> dict[str, Any]:
    if landscape_state is None:
        return {}

    entities_by_id = getattr(landscape_state, "entities_by_id", None)
    if isinstance(landscape_state, Mapping):
        entities_by_id = landscape_state.get("entities_by_id")
    if isinstance(entities_by_id, Mapping):
        normalized: dict[str, Any] = {}
        for entity_id, entity in entities_by_id.items():
            normalized[str(entity_id)] = entity
        return normalized
    return {}


def _extract_entity_warnings(landscape_state: Any) -> tuple[str, ...]:
    warnings = getattr(landscape_state, "warnings", ())
    if isinstance(warnings, (list, tuple)):
        return tuple(str(item) for item in warnings)
    return tuple()


def _validate_entity_schema(entity_id: str, entity: Any) -> tuple[str, ...]:
    required_fields = {
        "entity_type": "entity_type",
        "semantic_id": "semantic_id",
        "opaque_id": "opaque_id",
        "name": "name",
    }
    issues: list[str] = []
    for key, field_name in required_fields.items():
        value = _lookup_field(entity, key)
        if not _has_meaningful_value(value):
            issues.append(f"{entity_id}: missing '{field_name}'")
    return tuple(issues)


def _find_orphaned_files(landscape_state: Any, docs_path: str | Path | None) -> tuple[str, ...]:
    if not docs_path:
        return ()

    ids = _extract_landscape_entities(landscape_state).keys()
    base_path = Path(docs_path) / "landscape"
    if not base_path.exists():
        return ()

    orphaned: list[str] = []
    landscape_module = _load_runtime_module("landscape_store", "landscape_store.py")
    entity_directories = getattr(
        landscape_module,
        "LANDSCAPE_ENTITY_DIRECTORIES",
        ("system", "role", "outcome", "journey", "operating_loop", "capability", "decision", "risk"),
    )

    for entity_directory in entity_directories:
        for file_path in sorted((base_path / entity_directory).glob("*.yaml")):
            if file_path.stem not in ids:
                orphaned.append(str(file_path))
    return tuple(orphaned)


def _extract_by_type(payload: Mapping[str, Any], key: str) -> list[Any]:
    if not isinstance(payload, Mapping):
        return []
    for candidate in (key, key.replace("s", ""), key.replace("ies", "y")):
        value = payload.get(candidate)
        if isinstance(value, list):
            return value
    return []


def _ids_by_type(entities_by_id: Mapping[str, Any], entity_type: str) -> set[str]:
    entity_type = str(entity_type).strip().lower()
    ids: set[str] = set()
    for entity_id, entity in entities_by_id.items():
        mapped_type = str(_lookup_field(entity, "entity_type") or "").strip().lower()
        if mapped_type == entity_type:
            ids.add(str(entity_id))
    return ids


def _invalid_references(values: list[Any], valid_ids: set[str]) -> list[str]:
    invalid: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in valid_ids:
            invalid.append(item)
    return invalid


def _scope_label(value: Any) -> str:
    if isinstance(value, Mapping):
        raw = str(
            value.get("id")
            or value.get("item")
            or value.get("value")
            or value.get("scope")
            or value.get("type")
        )
    else:
        raw = str(value)
    return raw.strip().lower()


def _scope_issue(value: str) -> str | None:
    if _contains_word(value, "adjacent") and _contains_word(value, "journey"):
        return f"{value} contains adjacent journey scope"
    if _contains_word(value, "future") and _contains_word(value, "feature"):
        return f"{value} includes future feature scope"
    if _contains_word(value, "platform") and _contains_word(value, "architecture"):
        return f"{value} includes unrelated platform architecture scope"
    return None


def _contains_word(value: str, word: str) -> bool:
    return word.lower() in value.lower()


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, tuple):
        return list(value)
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
    if isinstance(value, tuple):
        return any(_has_meaningful_value(item) for item in value)
    return True


def _load_runtime_module(module_name: str, file_name: str):
    module_path = Path(__file__).resolve().parent / file_name
    spec = importlib.util.spec_from_file_location(f"nextlens_{module_name}_runtime", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {module_name} module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _lookup_field(obj: Any, key: str) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key)
    return getattr(obj, key, None)


def _is_within_docs_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _run_id() -> str:
    return uuid.uuid4().hex


def _overall_doctor_status(run_result: DoctorRunResult) -> str:
    if run_result.blocking_results:
        return "blocked"
    if run_result.advisory_results:
        return "advisory"
    return "pass"


def _dedupe_values(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values).keys())


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _freeze_mapping(value: Any) -> Any:
    if isinstance(value, DoctorCheckContext):
        return value
    if value is None:
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(item, Mapping):
                frozen[key] = _freeze_mapping(item)
            elif isinstance(item, list):
                frozen[key] = tuple(_freeze_mapping(child) for child in item)
            elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
                frozen[key] = tuple(_freeze_mapping(child) for child in item)
            else:
                frozen[key] = item
        return MappingProxyType(frozen)
    if isinstance(value, list):
        return tuple(_freeze_mapping(item) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, MappingProxyType)):
        return tuple(_freeze_mapping(item) for item in value)
    return copy.deepcopy(value)
