"""Extracted concept artifact support for pre-curation discovery input."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


SCHEMA_VERSION = "nextlens.extracted-concepts.v1"
ENVELOPE_KEY = "extracted_concepts"
ARTIFACT_REF = "artifacts/extracted-concepts.json"

POSSIBLE_COLLECTIONS = (
    "possibleRoles",
    "possibleStakeholders",
    "possibleOutcomes",
    "possibleOperatingLoops",
    "possibleJourneys",
    "possibleCandidateFeatures",
    "possibleRisks",
    "possibleOpenQuestions",
    "possibleRelationshipRefs",
)

TOP_DOWN_COLLECTIONS = {
    "possibleRoles": "roles",
    "possibleStakeholders": "stakeholders",
    "possibleOutcomes": "outcomes",
    "possibleOperatingLoops": "operatingLoops",
    "possibleJourneys": "journeys",
    "possibleCandidateFeatures": "candidateFeatures",
    "possibleRisks": "risks",
    "possibleOpenQuestions": "openQuestions",
    "possibleRelationshipRefs": "relationshipRefs",
}


CURATED_TOP_DOWN_ARTIFACT_REF = "artifacts/top-down-context.yaml"


class ExtractedConceptsError(ValueError):
    pass


def load_extracted_concepts(source: str) -> dict[str, Any]:
    raw_text = _source_text(source)
    yaml_module = _require_yaml_support()
    try:
        document = yaml_module.safe_load(raw_text)
    except yaml_module.YAMLError as exc:
        raise ExtractedConceptsError(f"Failed to parse extracted_concepts YAML: {exc}") from exc
    if not isinstance(document, Mapping):
        raise ExtractedConceptsError("extracted_concepts document must be a mapping.")
    payload = document.get(ENVELOPE_KEY, document)
    if not isinstance(payload, Mapping):
        raise ExtractedConceptsError("extracted_concepts must contain a mapping.")
    return normalize_extracted_concepts(payload, decision="consumed")


def build_from_raw_material(source: str) -> dict[str, Any]:
    raw_text = _source_text(source).strip()
    summary = raw_text[:240]
    open_question = "Curate top_down_context from the supplied discovery material before Feature packet emission."
    return normalize_extracted_concepts(
        {
            "schemaVersion": SCHEMA_VERSION,
            "decision": "captured",
            "rationale": "Raw discovery material was captured as candidate concepts; it is not authoritative top-down context.",
            "sourceSummary": summary,
            "possibleOpenQuestions": [{"id": "question-curate-top-down-context", "text": open_question}],
        },
        decision="captured",
    )


def build_already_curated(context: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "decision": "already_curated",
        "rationale": "top_down_context was supplied, so extracted concepts were explicitly skipped as already curated.",
    }
    for possible_key, context_key in TOP_DOWN_COLLECTIONS.items():
        payload[possible_key] = _list_value(context.get(context_key))
    return normalize_extracted_concepts(payload, decision="already_curated")


def normalize_extracted_concepts(payload: Mapping[str, Any], *, decision: str) -> dict[str, Any]:
    normalized = {
        "schemaVersion": str(payload.get("schemaVersion") or SCHEMA_VERSION),
        "decision": str(payload.get("decision") or decision),
        "rationale": str(payload.get("rationale") or ""),
    }
    for key in POSSIBLE_COLLECTIONS:
        normalized[key] = _list_value(payload.get(key))
    if payload.get("sourceSummary"):
        normalized["sourceSummary"] = str(payload["sourceSummary"])
    return normalized


def write_extracted_concepts_artifact(docs_path: str | Path, concepts: Mapping[str, Any]) -> Path:
    output_path = Path(docs_path) / ".nextlens" / ARTIFACT_REF
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(output_path.parent), prefix="extracted-concepts-", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(dict(concepts), handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(str(temp_path), str(output_path))
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    return output_path


def derive_curated_top_down_context(
    concepts: Mapping[str, Any],
    *,
    source_ref: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_extracted_concepts(concepts, decision=str(concepts.get("decision") or "captured"))
    source_summary = str(normalized.get("sourceSummary") or "").strip()
    rationale = str(normalized.get("rationale") or "").strip()
    thesis = source_summary or rationale or "Curated from extracted concepts for ranked Feature selection."

    roles = _normalize_named_collection(normalized.get("possibleRoles"), "role", "Operator")
    outcomes = _normalize_named_collection(
        normalized.get("possibleOutcomes"), "outcome", "Deliver bounded Feature value"
    )
    journeys = _normalize_named_collection(normalized.get("possibleJourneys"), "journey", "Top-down planning loop")
    stakeholders = _normalize_named_collection(normalized.get("possibleStakeholders"), "stakeholder", "Stakeholder")
    operating_loops = _normalize_named_collection(
        normalized.get("possibleOperatingLoops"), "operating-loop", "Planning operating loop"
    )
    relationship_refs = _normalize_relationship_refs(normalized.get("possibleRelationshipRefs"))
    risks = _normalize_risks(normalized.get("possibleRisks"))
    open_questions = _normalize_open_questions(normalized.get("possibleOpenQuestions"))

    if len(risks) < 3:
        risks.extend(
            [
                {"id": "risk.context-gaps", "name": "Top-down context remains partially inferred", "severity": "medium"},
                {"id": "risk.scope-expansion", "name": "Candidate scope may expand beyond one Feature", "severity": "high"},
                {"id": "risk.traceability-drift", "name": "Traceability evidence may be incomplete", "severity": "medium"},
            ][len(risks) :]
        )

    if len(open_questions) < 3:
        open_questions.extend(
            [
                {
                    "id": "question.confirm-candidate-selection",
                    "text": "Which ranked candidate should be explicitly selected for packet composition?",
                    "severity": "major",
                },
                {
                    "id": "question.confirm-scope-boundary",
                    "text": "Which adjacent journeys and future features must remain out of scope?",
                    "severity": "major",
                },
                {
                    "id": "question.confirm-evidence-coverage",
                    "text": "Which downstream evidence refs are mandatory for this packet?",
                    "severity": "medium",
                },
            ][len(open_questions) :]
        )

    system_id = "system.nextlens-curated"
    candidate_features = _normalize_candidate_features(
        normalized.get("possibleCandidateFeatures"),
        system_id=system_id,
        role_ids=[item["id"] for item in roles],
        outcome_ids=[item["id"] for item in outcomes],
        journey_ids=[item["id"] for item in journeys],
        risk_ids=[item["id"] for item in risks],
    )

    discovery_slug = _slugify(source_ref or source_summary or rationale or "discovery")
    discovery_epoch = {
        "id": f"epoch.{discovery_slug}",
        "status": "curated",
        "sourceRefs": [str(source_ref)] if source_ref else ["artifacts/extracted-concepts.json"],
    }

    return {
        "schemaVersion": "lens.topdown-context.v1",
        "sourceMode": "bottom_up" if normalized.get("decision") == "captured" else "top_down",
        "system": {
            "id": system_id,
            "name": "NextLens Curated Discovery Context",
            "thesis": thesis,
            "status": "active",
            "confidence": "medium",
        },
        "discoveryEpoch": discovery_epoch,
        "roles": roles,
        "stakeholders": stakeholders,
        "outcomes": outcomes,
        "operatingLoops": operating_loops,
        "journeys": journeys,
        "candidateFeatures": candidate_features,
        "risks": risks,
        "openQuestions": open_questions,
        "relationshipRefs": relationship_refs,
        "decisions": [
            {
                "id": f"decision.curated-{_utc_day_token()}",
                "name": "Curated top_down_context generated from extracted concepts",
                "rationale": "Preserve governed provenance and continue ranked candidate selection without ad hoc inline synthesis.",
            }
        ],
        "bmadConsumerContext": {
            "planningMode": "feature-packet",
            "consumer": "bmad",
            "curationSource": "extracted-concepts",
        },
    }


def write_curated_top_down_context_artifact(
    docs_path: str | Path,
    curated_context: Mapping[str, Any],
) -> Path:
    output_path = Path(docs_path) / ".nextlens" / CURATED_TOP_DOWN_ARTIFACT_REF
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"top_down_context": dict(curated_context)}

    fd, temp_name = tempfile.mkstemp(dir=str(output_path.parent), prefix="top-down-context-", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            if yaml is not None:
                yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=False)
            else:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
        os.replace(str(temp_path), str(output_path))
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    return output_path


def _source_text(source: str) -> str:
    source_path = Path(source)
    if source_path.exists():
        return source_path.read_text(encoding="utf-8")
    return source


def _list_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return [dict(item) if isinstance(item, Mapping) else item for item in value]
    return []


def _normalize_named_collection(value: Any, prefix: str, default_name: str) -> list[dict[str, Any]]:
    items = _list_value(value)
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, Mapping):
            item_id = str(item.get("id") or f"{prefix}.{index}").strip()
            item_name = str(item.get("name") or item.get("title") or default_name).strip()
            normalized.append({"id": item_id, "name": item_name})
        else:
            text = str(item).strip()
            if text:
                normalized.append({"id": f"{prefix}.{_slugify(text)}", "name": text})
    if not normalized:
        normalized.append({"id": f"{prefix}.default", "name": default_name})
    return normalized


def _normalize_relationship_refs(value: Any) -> list[str]:
    refs: list[str] = []
    for item in _list_value(value):
        text = str(item).strip()
        if text:
            refs.append(text)
    return refs


def _normalize_risks(value: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(_list_value(value), start=1):
        if isinstance(item, Mapping):
            risk_id = str(item.get("id") or f"risk.{index}").strip()
            name = str(item.get("name") or item.get("text") or "Risk").strip()
            severity = str(item.get("severity") or "medium").strip().lower()
            normalized.append({"id": risk_id, "name": name, "severity": severity})
        else:
            text = str(item).strip()
            if text:
                normalized.append(
                    {
                        "id": f"risk.{_slugify(text)}",
                        "name": text,
                        "severity": "medium",
                    }
                )
    return normalized


def _normalize_open_questions(value: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(_list_value(value), start=1):
        if isinstance(item, Mapping):
            question_id = str(item.get("id") or f"question.{index}").strip()
            text = str(item.get("text") or item.get("name") or "Open question").strip()
            severity = str(item.get("severity") or "major").strip().lower()
            normalized.append({"id": question_id, "text": text, "severity": severity})
        else:
            text = str(item).strip()
            if text:
                normalized.append(
                    {
                        "id": f"question.{_slugify(text)}",
                        "text": text,
                        "severity": "major",
                    }
                )
    return normalized


def _normalize_candidate_features(
    value: Any,
    *,
    system_id: str,
    role_ids: list[str],
    outcome_ids: list[str],
    journey_ids: list[str],
    risk_ids: list[str],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(_list_value(value), start=1):
        if isinstance(item, Mapping):
            base_id = str(item.get("id") or f"feature.curated.{index}").strip()
            name = str(item.get("name") or item.get("title") or "Curated candidate").strip()
            goal = str(item.get("goal") or item.get("summary") or f"Advance {name}").strip()
        else:
            text = str(item).strip()
            if not text:
                continue
            base_id = f"feature.{_slugify(text)}"
            name = text
            goal = f"Advance {text}"

        candidates.append(
            {
                "id": base_id,
                "name": name,
                "goal": goal,
                "summary": goal,
                "scope": {
                    "summary": "Deliver one bounded Feature slice with explicit containment.",
                    "outOfScope": [
                        "Adjacent journeys not selected in ranking",
                        "Future features beyond the selected candidate",
                        "Platform-wide architecture redesign",
                    ],
                },
                "trace": {
                    "systemId": system_id,
                    "roleIds": role_ids,
                    "outcomeIds": outcome_ids,
                    "journeyIds": journey_ids,
                    "featureId": base_id,
                },
                "roleIds": role_ids,
                "outcomeIds": outcome_ids,
                "journeyIds": journey_ids,
                "riskRefs": risk_ids,
            }
        )

    if not candidates:
        fallback_id = "feature.curated.default"
        candidates.append(
            {
                "id": fallback_id,
                "name": "Curated Feature Candidate",
                "goal": "Continue governed packet flow after extracted-concepts curation.",
                "summary": "Bounded candidate synthesized from extracted concepts.",
                "scope": {
                    "summary": "One selected Feature packet candidate.",
                    "outOfScope": [
                        "Adjacent journeys not selected in ranking",
                        "Future features beyond the selected candidate",
                        "Platform-wide architecture redesign",
                    ],
                },
                "trace": {
                    "systemId": system_id,
                    "roleIds": role_ids,
                    "outcomeIds": outcome_ids,
                    "journeyIds": journey_ids,
                    "featureId": fallback_id,
                },
                "roleIds": role_ids,
                "outcomeIds": outcome_ids,
                "journeyIds": journey_ids,
                "riskRefs": risk_ids,
            }
        )

    return candidates


def _slugify(value: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return collapsed or "value"


def _utc_day_token() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _require_yaml_support():
    if yaml is None:
        raise ExtractedConceptsError("PyYAML is required to load extracted_concepts.") from _YAML_IMPORT_ERROR
    return yaml
