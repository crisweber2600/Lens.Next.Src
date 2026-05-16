"""Extracted concept artifact support for pre-curation discovery input."""

from __future__ import annotations

import json
import os
from pathlib import Path
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


def _source_text(source: str) -> str:
    source_path = Path(source)
    if source_path.exists():
        return source_path.read_text(encoding="utf-8")
    return source


def _list_value(value: Any) -> list[Any]:
    if isinstance(value, list):
        return [dict(item) if isinstance(item, Mapping) else item for item in value]
    return []


def _require_yaml_support():
    if yaml is None:
        raise ExtractedConceptsError("PyYAML is required to load extracted_concepts.") from _YAML_IMPORT_ERROR
    return yaml
