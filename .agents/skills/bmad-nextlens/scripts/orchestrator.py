"""Orchestrator for NextLens NEW action pipeline.

This module coordinates the full stage pipeline for the 'new' action,
from context intake through confirmation, emission, and routing.
It ensures that after confirmation, the pipeline continues through
remaining stages (write, rebuild, validate, emit, route) instead of
stopping at the confirmation gate.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence

_STAGE_PIPELINE_PATH = Path(__file__).resolve().parent / "stage_pipeline.py"
_STAGE_PIPELINE_SPEC = importlib.util.spec_from_file_location(
    "bmad_nextlens_stage_pipeline", _STAGE_PIPELINE_PATH
)
if _STAGE_PIPELINE_SPEC is None or _STAGE_PIPELINE_SPEC.loader is None:
    raise ImportError(
        f"Could not load stage_pipeline module from '{_STAGE_PIPELINE_PATH}'. "
        "Ensure the file exists and is readable."
    )
_STAGE_PIPELINE_MOD = importlib.util.module_from_spec(_STAGE_PIPELINE_SPEC)
sys.modules.setdefault(_STAGE_PIPELINE_SPEC.name, _STAGE_PIPELINE_MOD)
_STAGE_PIPELINE_SPEC.loader.exec_module(_STAGE_PIPELINE_MOD)

NextLensStagePipeline = _STAGE_PIPELINE_MOD.NextLensStagePipeline
StageResult = _STAGE_PIPELINE_MOD.StageResult
PipelineInterrupted = _STAGE_PIPELINE_MOD.PipelineInterrupted


def _load_runtime_module(module_name: str, file_name: str):
    module_path = Path(__file__).resolve().parent / file_name
    spec = importlib.util.spec_from_file_location(f"nextlens_{module_name}_runtime", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Could not load {module_name} module from '{module_path}'. "
            "Ensure the file exists and is readable."
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


CONTEXT_LOADER = _load_runtime_module("context_loader", "context_loader.py")
DERIVED_GRAPH = _load_runtime_module("derived_graph", "derived_graph.py")
DOCTOR_CHECKS = _load_runtime_module("doctor_checks", "doctor_checks.py")
EVIDENCE_BUNDLE = _load_runtime_module("evidence_bundle", "evidence_bundle.py")
EXTRACTED_CONCEPTS = _load_runtime_module("extracted_concepts", "extracted_concepts.py")
FEATURE_PACKET_COMPOSER = _load_runtime_module("feature_packet_composer", "feature_packet_composer.py")
FEATURE_PACKET_EMITTER = _load_runtime_module("feature_packet_emitter", "feature_packet_emitter.py")
FEATURE_SCORING = _load_runtime_module("feature_scoring", "feature_scoring.py")
BMAD_HANDOFF = _load_runtime_module("bmad_handoff", "bmad_handoff.py")


@dataclass(frozen=True)
class _RuntimeLandscapeRelationship:
    relationship_name: str
    target_id: str
    target_entity: Any
    metadata: dict[str, Any]


@dataclass
class _RuntimeLandscapeEntity:
    entity_type: str
    semantic_id: str
    opaque_id: str
    name: str
    metadata: dict[str, Any]
    source_path: Path
    resolved_relationships: dict[str, tuple[_RuntimeLandscapeRelationship, ...]]


def create_new_action_handlers() -> dict[str, Callable[[dict[str, Any]], StageResult]]:
    """Create stage handlers for the 'new' action pipeline.
    
    Returns handlers for: intake, extract, sufficiency, rank, confirm, write,
    rebuild, validate, emit, route
    """
    return {
        "intake": _handle_intake,
        "extract": _handle_extract,
        "sufficiency": _handle_sufficiency,
        "rank": _handle_rank,
        "confirm": _handle_confirm,
        "write": _handle_write,
        "rebuild": _handle_rebuild,
        "validate": _handle_validate,
        "emit": _handle_emit,
        "route": _handle_route,
    }


def _handle_intake(context: dict[str, Any]) -> StageResult:
    """Load and normalize context from source."""
    source = context.get("context_source")
    if not source:
        return StageResult(
            status="fail",
            detail="context_source is required",
            remediation_hints=("Provide context_source in the input context",),
        )

    try:
        loaded = _load_top_down_context(source)
    except CONTEXT_LOADER.ContextValidationError as top_down_exc:
        try:
            extracted = EXTRACTED_CONCEPTS.load_extracted_concepts(source)
            intake_mode = "extracted_concepts"
        except EXTRACTED_CONCEPTS.ExtractedConceptsError:
            extracted = EXTRACTED_CONCEPTS.build_from_raw_material(source)
            intake_mode = "raw_discovery_material"
        return StageResult(
            status="pass",
            detail="Discovery material captured for extracted-concepts curation",
            state_patch={
                "context_loaded": False,
                "source": source,
                "intake_mode": intake_mode,
                "intake_warning": str(top_down_exc),
                "extracted_concepts": extracted,
            },
        )

    return StageResult(
        status="pass",
        detail="Context loaded",
        state_patch={
            "context_loaded": True,
            "source": source,
            "intake_mode": "top_down_context",
            "loaded_context": loaded.payload,
            "context_warnings": list(loaded.warnings),
            "context_source_path": str(loaded.source_path) if loaded.source_path else None,
        },
    )


def _handle_extract(context: dict[str, Any]) -> StageResult:
    """Capture or explicitly skip candidate concepts before top-down sufficiency."""
    docs_path = context.get("docs_path", ".nextlens")
    if context.get("context_loaded"):
        concepts = EXTRACTED_CONCEPTS.build_already_curated(context.get("loaded_context") or {})
        detail = "Extracted concepts skipped; top_down_context is already curated"
        stage_status = "warning"
    else:
        concepts = dict(context.get("extracted_concepts") or {})
        if not concepts:
            return StageResult(
                status="fail",
                detail="No top_down_context or extracted_concepts could be captured",
                next_action="Provide raw discovery material, extracted_concepts, or top_down_context.",
            )
        detail = "Extracted concepts captured; top_down_context still required before ranking"
        stage_status = "pass"

    artifact_path = EXTRACTED_CONCEPTS.write_extracted_concepts_artifact(docs_path, concepts)
    return StageResult(
        status=stage_status,
        detail=detail,
        state_patch={
            "extracted_concepts_decision": concepts.get("decision"),
            "extracted_concepts": concepts,
            "extracted_concepts_path": str(artifact_path),
        },
        remediation_hints=(str(concepts.get("rationale") or ""),),
    )


def _handle_sufficiency(context: dict[str, Any]) -> StageResult:
    """Validate that context has sufficient information for candidacy analysis."""
    state_patch: dict[str, Any] = {}
    if not context.get("context_loaded"):
        extracted_concepts = context.get("extracted_concepts")
        if not isinstance(extracted_concepts, Mapping) or not extracted_concepts:
            return StageResult(
                status="fail",
                detail="top_down_context is required before context sufficiency and candidate ranking",
                next_action="curate_top_down_context",
                remediation_hints=(
                    "Use the extracted_concepts artifact as candidate input, then provide authoritative top_down_context.",
                    "Raw prose or extracted_concepts must not be emitted directly as a Feature packet.",
                ),
                diagnostic_context={
                    "extracted_concepts_path": str(context.get("extracted_concepts_path") or ""),
                },
            )

        docs_path = context.get("docs_path", ".nextlens")
        curated_context = EXTRACTED_CONCEPTS.derive_curated_top_down_context(
            extracted_concepts,
            source_ref=context.get("source"),
        )
        curated_context_path = EXTRACTED_CONCEPTS.write_curated_top_down_context_artifact(
            docs_path,
            curated_context,
        )
        loaded = _load_top_down_context(str(curated_context_path))
        state_patch.update(
            {
                "context_loaded": True,
                "loaded_context": loaded.payload,
                "context_warnings": list(loaded.warnings),
                "context_source_path": str(curated_context_path),
                "top_down_context_curated": True,
                "top_down_context_curated_path": str(curated_context_path),
                "top_down_context_curated_from": str(context.get("extracted_concepts_path") or ""),
            }
        )

    report = CONTEXT_LOADER.evaluate_context_sufficiency(
        CONTEXT_LOADER.LoadedContext(
            payload=copy.deepcopy(dict((state_patch.get("loaded_context") or context.get("loaded_context")) or {})),
            warnings=tuple(
                str(item)
                for item in (state_patch.get("context_warnings") or context.get("context_warnings", ()))
            ),
            version_mismatch=bool(state_patch.get("context_warnings") or context.get("context_warnings")),
        )
    )
    if report.status == "blocked":
        return StageResult(
            status="fail",
            detail="Context sufficiency blocked packet emission",
            next_action=report.recommendation,
            remediation_hints=tuple(report.missing_required) or tuple(report.warnings),
            diagnostic_context={
                "missing_required": ", ".join(report.missing_required),
                "warnings": " | ".join(report.warnings),
            },
            rollback_action="No packet was composed or emitted; return to discovery and fill the missing top-down context.",
        )

    stage_status = "warning" if report.status == "ready_with_warnings" else "pass"
    return StageResult(
        status=stage_status,
        detail=(
            "Context meets sufficiency requirements"
            if stage_status == "pass"
            else "Context is ready with warnings"
        ),
        state_patch={
            **state_patch,
            "sufficiency_validated": True,
            "sufficiency_status": report.status,
            "sufficiency_warnings": list(report.warnings),
            "sufficiency_missing_required": list(report.missing_required),
        },
        remediation_hints=tuple(report.warnings),
    )


def _handle_rank(context: dict[str, Any]) -> StageResult:
    """Identify and rank candidate Feature slices from context."""
    if not context.get("sufficiency_validated"):
        return StageResult(
            status="fail",
            detail="Context not validated for sufficiency",
        )

    ranked_candidates = FEATURE_SCORING.rank_candidate_features(context.get("loaded_context") or {})
    if not ranked_candidates:
        return StageResult(
            status="fail",
            detail="No candidate Features were available for ranking",
            next_action="return_to_discovery",
            remediation_hints=("Add at least one traceable candidateFeature before continuing.",),
        )

    selected_candidate_id = str(
        context.get("selected_candidate_id") or ranked_candidates[0].candidate_id
    ).strip()
    ranked_ids = [candidate.candidate_id for candidate in ranked_candidates]
    if selected_candidate_id not in ranked_ids:
        return StageResult(
            status="fail",
            detail=f"Selected candidate '{selected_candidate_id}' is not present in ranked candidates",
            next_action="choose_ranked_candidate",
            remediation_hints=tuple(ranked_ids),
        )

    return StageResult(
        status="pass",
        detail=f"Candidates identified and ranked; selected candidate is {selected_candidate_id}",
        state_patch={
            "candidates_ranked": True,
            "candidate_count": len(ranked_candidates),
            "ranked_candidate_ids": ranked_ids,
            "selected_candidate_id": selected_candidate_id,
        },
    )


def _handle_confirm(context: dict[str, Any]) -> StageResult:
    """Final confirmation gate before emission.
    
    CRITICAL: After confirmation, the pipeline must CONTINUE to write, rebuild,
    validate, emit, and route stages. Do not stop at confirmation.
    """
    if not context.get("candidates_ranked"):
        return StageResult(
            status="fail",
            detail="Candidates not ranked",
        )

    confirmation_response = str(context.get("confirmation_response") or "").strip().lower()
    if confirmation_response not in {"y", "yes", "confirm", "confirmed", "true"}:
        return StageResult(
            status="fail",
            detail="Explicit confirmation is required before packet emission",
            next_action="confirm_ranked_candidate",
            remediation_hints=(
                f"selected_candidate_id={context.get('selected_candidate_id')}",
                "Provide confirmation_response=yes after reviewing the ranked candidate.",
            ),
            rollback_action="No packet was composed or emitted.",
        )

    return StageResult(
        status="pass",
        detail="Confirmation obtained; proceeding to packet emission",
        state_patch={
            "confirmation_obtained": True,
            "proceed_to_emission": True,
            "confirmed_at": _utc_timestamp(),
            "confirmation_response": confirmation_response,
        },
        next_action="continue to write stage",
    )


def _handle_write(context: dict[str, Any]) -> StageResult:
    """Compose the final Feature packet."""
    if not context.get("confirmation_obtained"):
        return StageResult(
            status="fail",
            detail="Confirmation not obtained",
        )

    ranked_candidates = FEATURE_SCORING.rank_candidate_features(context.get("loaded_context") or {})
    selected_candidate_id = str(context.get("selected_candidate_id") or "").strip()
    selected_candidate = next(
        (candidate for candidate in ranked_candidates if candidate.candidate_id == selected_candidate_id),
        None,
    )
    if selected_candidate is None:
        return StageResult(
            status="fail",
            detail=f"Selected candidate '{selected_candidate_id}' could not be resolved during packet composition",
            next_action="re-run ranking with a valid candidate id",
        )

    composition = FEATURE_PACKET_COMPOSER.compose_feature_packet(
        selected_candidate,
        ranked_candidates,
        context.get("loaded_context") or {},
        docs_path=context.get("docs_path", ".nextlens"),
    )
    if composition.status != "pass":
        return StageResult(
            status="fail",
            detail="Feature packet composition failed",
            next_action="repair packet composition inputs and retry",
            diagnostic_context={"packet_validation_status": composition.validation.status},
        )

    return StageResult(
        status="pass",
        detail="Feature packet composed",
        state_patch={
            "packet_composed": True,
            "packet_candidate": composition.packet,
            "selected_feature": composition.packet.get("selectedFeature"),
        },
    )


def _handle_rebuild(context: dict[str, Any]) -> StageResult:
    """Rebuild derived structures after packet composition."""
    if not context.get("packet_composed"):
        return StageResult(
            status="fail",
            detail="Packet not composed",
        )

    landscape_state = _build_landscape_state(context.get("loaded_context") or {}, context.get("docs_path", ".nextlens"))
    derived_graph_payload = DERIVED_GRAPH.rebuild_derived_graph(landscape_state).to_payload(
        source_state_ref="nextlens:new"
    )
    return StageResult(
        status="pass",
        detail="Derived structures updated",
        state_patch={
            "structures_rebuilt": True,
            "derived_graph": derived_graph_payload,
        },
    )


def _handle_validate(context: dict[str, Any]) -> StageResult:
    """Validate the composed packet against schema and governance rules."""
    if not context.get("structures_rebuilt"):
        return StageResult(
            status="fail",
            detail="Structures not rebuilt",
        )

    packet = copy.deepcopy(dict(context.get("packet_candidate") or {}))
    if not packet:
        return StageResult(
            status="fail",
            detail="Packet candidate missing before validation",
        )

    docs_path = context.get("docs_path", ".nextlens")
    packet_output_path = FEATURE_PACKET_EMITTER.packet_output_path(docs_path, str(packet.get("packetId") or ""))
    doctor_result = _run_packet_doctor_checks(
        context,
        packet,
        write_targets=[str(packet_output_path)],
    )
    if doctor_result.operation_blocked:
        return StageResult(
            status="fail",
            detail="Doctor validation blocked packet emission",
            next_action="repair packet traceability or required context before emission",
            remediation_hints=tuple(result.message for result in doctor_result.run_result.blocking_results)
            or tuple(result.message for result in doctor_result.run_result.advisory_results),
            diagnostic_context={
                "doctor_status": doctor_result.status,
                "doctor_report_path": str(doctor_result.report_path) if doctor_result.report_path else "",
            },
            rollback_action="No packet was emitted; fix the doctor findings and rerun validation.",
        )

    packet["doctorSummary"] = _doctor_summary_payload(doctor_result)
    stage_status = "warning" if doctor_result.status == "warning" else "pass"
    return StageResult(
        status=stage_status,
        detail="Packet validation passed" if stage_status == "pass" else "Packet validation completed with advisory findings",
        state_patch={
            "packet_validated": True,
            "packet_candidate": packet,
            "doctor_report_path": str(doctor_result.report_path) if doctor_result.report_path else None,
        },
        remediation_hints=tuple(result.message for result in doctor_result.run_result.advisory_results),
    )


def _handle_emit(context: dict[str, Any]) -> StageResult:
    """Emit the Feature packet to the configured output location."""
    if not context.get("packet_validated"):
        return StageResult(
            status="fail",
            detail="Packet not validated",
        )
    docs_path = context.get("docs_path", ".nextlens")
    packet = copy.deepcopy(dict(context.get("packet_candidate") or {}))
    handoff_enabled = context.get("bmad_handoff_enabled", True)
    handoff_status = "pending"
    handoff_paths: dict[str, str] = {}
    if handoff_enabled:
        handoff_result = BMAD_HANDOFF.generate_bmad_handoff_artifacts(docs_path, packet, update_packet=True)
        if handoff_result.status != "pass":
            return StageResult(
                status="fail",
                detail=handoff_result.error or "BMAD handoff artifact generation failed",
                rollback_action="Packet was not emitted; resolve handoff generation errors and retry emission.",
            )
        packet = handoff_result.packet
        handoff_paths = dict(handoff_result.artifact_paths)
        handoff_status = "pass"

    packet_output_path = FEATURE_PACKET_EMITTER.packet_output_path(docs_path, str(packet.get("packetId") or ""))
    final_doctor_result = _run_packet_doctor_checks(
        context,
        packet,
        write_targets=[str(packet_output_path), *handoff_paths.values()],
    )
    if final_doctor_result.operation_blocked:
        return StageResult(
            status="fail",
            detail="Final Doctor validation blocked packet emission",
            next_action="repair generated BMAD handoff artifacts before emission",
            remediation_hints=tuple(result.message for result in final_doctor_result.run_result.blocking_results)
            or tuple(result.message for result in final_doctor_result.run_result.advisory_results),
            diagnostic_context={
                "doctor_status": final_doctor_result.status,
                "doctor_report_path": str(final_doctor_result.report_path) if final_doctor_result.report_path else "",
            },
            rollback_action="Packet was not emitted; repair handoff artifacts and rerun emission.",
        )

    packet["doctorSummary"] = _doctor_summary_payload(final_doctor_result)
    final_doctor_report_path = str(final_doctor_result.report_path) if final_doctor_result.report_path else None

    emission = FEATURE_PACKET_EMITTER.emit_feature_packet(packet, docs_path)
    if emission.status != "pass":
        return StageResult(
            status="fail",
            detail=emission.error or "Feature packet emission failed",
            remediation_hints=tuple(emission.output_lines),
            rollback_action=emission.rollback_guidance,
        )
    evidence = EVIDENCE_BUNDLE.generate_nextlens_evidence_bundle(
        docs_path,
        packet=packet,
        artifact_refs={
            "inputAnalysisRef": "artifacts/input-analysis.json",
            "extractedConceptsRef": _relative_artifact_ref(
                docs_path,
                context.get("extracted_concepts_path"),
                fallback="artifacts/extracted-concepts.json",
            ),
            "topDownContextRef": _top_down_context_ref(context),
            "contextSufficiencyRef": "artifacts/context-sufficiency.json",
            "rankingTraceRef": "artifacts/ranking-trace.json",
            "doctorReportRef": _relative_artifact_ref(
                docs_path,
                final_doctor_report_path,
                fallback="artifacts/doctor-report.jsonl",
            ),
            "salmonRoutingRef": "artifacts/salmon-routing.json",
            "idempotencyDecisionRef": "artifacts/idempotency.json",
            "bmadHandoffRefs": handoff_paths,
            "derivedGraphRef": packet.get("derivedGraphRef"),
        },
        stage_outcomes={
            "intake": "pass",
            "extracted_concepts": _stage_outcome_for_extracted_concepts(context),
            "context_sufficiency": "pass",
            "ranking": "pass",
            "confirmation": "pass",
            "authoritative_write": "pass",
            "derived_graph_rebuild": "pass",
            "doctor": final_doctor_result.status,
            "packet_emission": "pass",
            "bmad_handoff": handoff_status,
            "bmad_artifacts": "pending",
            "stories": "pending",
            "implementation_evidence": "pending",
            "validation": "pending",
            "salmon": "none",
            "landscape_update": "pending",
            "derived_graph_refresh": "pending",
        },
    )
    if evidence.status != "pass":
        return StageResult(
            status="fail",
            detail=evidence.error or "Evidence bundle generation failed",
            rollback_action="Packet was emitted; generate the evidence bundle before downstream handoff.",
        )

    return StageResult(
        status="pass",
        detail=f"Feature packet emitted to {emission.packet_path}; evidence bundle written to {evidence.path}",
        state_patch={
            "packet_emitted": True,
            "emission_timestamp": _utc_timestamp(),
            "packet_path": str(emission.packet_path),
            "evidence_bundle_path": str(evidence.path),
            "bmad_handoff_paths": handoff_paths,
            "doctor_report_path": final_doctor_report_path,
        },
    )


def _handle_route(context: dict[str, Any]) -> StageResult:
    """Frame next steps for continuing the planning flow.
    
    This stage completes the NEW action by clarifying that after packet
    emission, the operator may run Doctor for non-mutating health validation,
    should continue through BMAD planning/implementation, and should run
    Validate only after BMAD implementation evidence exists.
    """
    if not context.get("packet_emitted"):
        return StageResult(
            status="fail",
            detail="Packet not emitted",
        )
    
    return StageResult(
        status="pass",
        detail=(
            "Pipeline complete. Optional Doctor health check; BMAD "
            "planning/implementation; then Validate after BMAD implementation evidence exists."
        ),
        state_patch={
            "next_steps_framed": True,
            "suggested_flow": (
                "1. Run `/bmad-nextlens-doctor` for non-mutating health validation if desired.\n"
                "2. Delegate Feature development to the normal top-down BMAD "
                "planning/implementation sequence:\n"
                "   - Clarify feature intent and boundaries\n"
                "   - Create PRD-level specifications\n"
                "   - Define architectural implications\n"
                "   - Generate stories and acceptance criteria\n"
                "   - Prepare execution handoff to implementation team\n"
                "   - Capture BMAD implementation evidence\n"
                "3. After BMAD implementation evidence exists, run `/bmad-nextlens-validate`.\n"
                "4. Validate generates a validation result, routes Salmon if needed, "
                "prepares Landscape proposal/apply output, and updates the evidence-bundle."
            ),
        },
    )


def _utc_timestamp() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_new_action_pipeline(
    context_source: str,
    docs_path: str | Path | None = None,
    *,
    resume_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the complete NEW action pipeline.
    
    This function orchestrates all stages from intake through routing,
    ensuring that the pipeline continues through all stages after
    confirmation instead of stopping at the confirmation gate.
    
    Args:
        context_source: Path or content of the discovery context
        docs_path: Optional path to the NextLens docs directory
        resume_state: Optional saved state to resume from
        
    Returns:
        Dictionary with pipeline execution results
    """
    if docs_path is None:
        docs_path = Path(".nextlens")
    else:
        docs_path = Path(docs_path)
    
    pipeline = NextLensStagePipeline(docs_path)
    handlers = create_new_action_handlers()
    
    context = {
        "context_source": context_source,
        "docs_path": str(docs_path),
    }
    
    execution = pipeline.run(
        mode="new",
        handlers=handlers,
        context=context,
        resume_state=resume_state,
    )
    
    return {
        "status": execution.status,
        "output": "\n".join(execution.output_lines),
        "completed_stages": list(execution.completed_stages),
        "current_stage": execution.current_stage,
        "next_action": execution.next_action,
        "resume_state": execution.resume_state,
    }


def _load_top_down_context(source: str) -> Any:
    source_path = Path(source)
    if source_path.exists():
        return CONTEXT_LOADER.load_context_file(source_path)
    return CONTEXT_LOADER.parse_context_yaml(source)


def _relative_artifact_ref(docs_path: str | Path, value: Any, *, fallback: str) -> str:
    if not value:
        return fallback
    try:
        return Path(value).resolve().relative_to((Path(docs_path) / ".nextlens").resolve()).as_posix()
    except (OSError, ValueError):
        return str(value).replace("\\", "/")


def _top_down_context_ref(context: Mapping[str, Any]) -> str:
    source_path = context.get("context_source_path")
    if source_path:
        return str(source_path)
    return "artifacts/top-down-context.yaml"


def _stage_outcome_for_extracted_concepts(context: Mapping[str, Any]) -> str:
    return "skipped" if context.get("extracted_concepts_decision") == "already_curated" else "pass"


def _run_packet_doctor_checks(
    context: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    write_targets: Sequence[str],
) -> Any:
    docs_path = context.get("docs_path", ".nextlens")
    landscape_state = _build_landscape_state(context.get("loaded_context") or {}, docs_path)
    return DOCTOR_CHECKS.run_preflight_doctor_checks(
        DOCTOR_CHECKS.DoctorCheckContext(
            landscape_state=landscape_state,
            derived_graph=context.get("derived_graph") or {},
            packet_candidate=copy.deepcopy(dict(packet)),
            selected_feature=context.get("selected_feature") or {},
            docs_path=docs_path,
            write_targets=tuple(write_targets),
        ),
        prompt_fn=lambda *_: str(context.get("confirmation_response") or "yes"),
    )


def _build_landscape_state(context: Mapping[str, Any], docs_path: str | Path) -> SimpleNamespace:
    docs_root = Path(docs_path)
    entities_by_id: dict[str, _RuntimeLandscapeEntity] = {}

    system_payload = context.get("system") if isinstance(context.get("system"), Mapping) else {}
    system_id = str(system_payload.get("id") or "").strip()
    if system_id:
        entities_by_id[system_id] = _make_entity("system", system_payload, docs_root)

    roles = _register_entities(entities_by_id, "role", context.get("roles"), docs_root)
    outcomes = _register_entities(entities_by_id, "outcome", context.get("outcomes"), docs_root)
    journeys = _register_entities(entities_by_id, "journey", context.get("journeys"), docs_root)
    operating_loops = _register_entities(entities_by_id, "operating_loop", context.get("operatingLoops"), docs_root)

    if system_id and roles:
        entities_by_id[system_id].resolved_relationships["roles"] = tuple(
            _make_relationship("roles", role) for role in roles
        )
    for role in roles:
        if outcomes:
            role.resolved_relationships["outcomes"] = tuple(
                _make_relationship("outcomes", outcome) for outcome in outcomes
            )
    for outcome in outcomes:
        if journeys:
            outcome.resolved_relationships["journeys"] = tuple(
                _make_relationship("journeys", journey) for journey in journeys
            )
    for journey in journeys:
        if operating_loops:
            journey.resolved_relationships["operatingLoops"] = tuple(
                _make_relationship("operatingLoops", operating_loop) for operating_loop in operating_loops
            )

    return SimpleNamespace(
        entities_by_id=entities_by_id,
        warnings=(),
        load_sequence=tuple(entities_by_id.keys()),
    )


def _register_entities(
    entities_by_id: dict[str, _RuntimeLandscapeEntity],
    entity_type: str,
    values: Any,
    docs_root: Path,
) -> list[_RuntimeLandscapeEntity]:
    registered: list[_RuntimeLandscapeEntity] = []
    if not isinstance(values, list):
        return registered
    for value in values:
        if not isinstance(value, Mapping):
            continue
        entity = _make_entity(entity_type, value, docs_root)
        if not entity.semantic_id:
            continue
        entities_by_id[entity.semantic_id] = entity
        registered.append(entity)
    return registered


def _make_entity(entity_type: str, payload: Mapping[str, Any], docs_root: Path) -> _RuntimeLandscapeEntity:
    semantic_id = str(payload.get("id") or payload.get("semanticId") or "").strip()
    name = str(payload.get("name") or payload.get("title") or semantic_id).strip()
    return _RuntimeLandscapeEntity(
        entity_type=entity_type,
        semantic_id=semantic_id,
        opaque_id=f"opaque-{semantic_id}",
        name=name,
        metadata={str(key): value for key, value in payload.items() if key not in {"id", "semanticId", "name", "title"}},
        source_path=docs_root / "landscape" / entity_type / f"{semantic_id}.yaml",
        resolved_relationships={},
    )


def _make_relationship(name: str, target_entity: _RuntimeLandscapeEntity) -> _RuntimeLandscapeRelationship:
    return _RuntimeLandscapeRelationship(
        relationship_name=name,
        target_id=target_entity.semantic_id,
        target_entity=target_entity,
        metadata={},
    )


def _doctor_summary_payload(result: Any) -> dict[str, Any]:
    return {
        "status": result.status,
        "blocking_count": len(result.run_result.blocking_results),
        "advisory_count": len(result.run_result.advisory_results),
        "informational_count": len(result.run_result.informational_results),
        "reportPath": str(result.report_path) if result.report_path else None,
    }
