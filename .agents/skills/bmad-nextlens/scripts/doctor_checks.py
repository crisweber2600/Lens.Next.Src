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
    for result in sorted(run_result.results, key=lambda item: item.check_id or ""):
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
    elif system_id not in entities_by_id:
        issues.append(f"systemId '{system_id}' does not resolve")
        references.append(system_id)

    role_ids = _as_list(trace.get("roleIds"))
    role_invalid = _invalid_references(role_ids, _ids_by_type(entities_by_id, "role"))
    if role_invalid:
        issues.append(f"trace.roleIds contains unresolved ids: {', '.join(role_invalid)}")
        references.extend(role_invalid)

    outcome_ids = _as_list(trace.get("outcomeIds"))
    outcome_invalid = _invalid_references(outcome_ids, _ids_by_type(entities_by_id, "outcome"))
    if outcome_invalid:
        issues.append(f"trace.outcomeIds contains unresolved ids: {', '.join(outcome_invalid)}")
        references.extend(outcome_invalid)

    journey_ids = _as_list(trace.get("journeyIds"))
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
            status="warning",
            severity="advisory",
            check_id="traceability",
            message="Traceability has unresolved references that does not resolve to valid landscape IDs.",
            references=tuple(_dedupe_values(references)),
            remediation="Align packet trace with valid landscape IDs or refresh candidate generation.",
        )
    return DoctorCheckResult(
        status="pass",
        severity="advisory",
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
    missing: list[str] = []
    hints = _as_mapping(packet.get("bmadConsumerHints"))
    if not hints:
        hints = _as_mapping(packet.get("bmadConsumerContext"))
    for field in ("prdInput", "uxInput", "architectureInput"):
        if not _has_meaningful_value(hints.get(field)):
            missing.append(field)

    system = _as_mapping(packet.get("system"))
    if not _has_meaningful_value(system.get("thesis")):
        missing.append("system.thesis")

    roles = _as_list(packet.get("roles"))
    outcomes = _as_list(packet.get("outcomes"))
    journeys = _as_list(packet.get("journeys"))
    if not roles:
        roles = _as_list(_extract_by_type(packet, "roles"))
        if not roles:
            missing.append("roles")
    if not outcomes:
        outcomes = _as_list(_extract_by_type(packet, "outcomes"))
        if not outcomes:
            missing.append("outcomes")
    if not journeys:
        journeys = _as_list(_extract_by_type(packet, "journeys"))
        if not journeys:
            missing.append("journeys")

    open_questions = _as_list(packet.get("openQuestions"))
    risks = _as_list(packet.get("risks"))
    if not open_questions:
        missing.append("openQuestions")
    if not risks:
        missing.append("risks")

    if missing:
        return DoctorCheckResult(
            status="warning",
            severity="advisory",
            check_id="context-readiness",
            message="Context readiness check found missing required data.",
            references=tuple(missing),
            remediation="Populate BMAD hints and missing context fields before emission.",
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
