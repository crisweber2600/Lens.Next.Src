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
EXTRACTION_COVERAGE_ARTIFACT_REF = "artifacts/extraction-coverage.json"

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
    extracted = _extract_raw_discovery_inventory(raw_text, source_ref=_source_ref(source))
    open_questions = list(extracted["possibleOpenQuestions"])
    open_questions.append(
        {
            "id": "question-curate-top-down-context",
            "text": "Curate top_down_context from the supplied discovery material before Feature packet emission.",
            "severity": "major",
        }
    )
    if extracted["extractionCoverage"]["extractionConfidence"] == "low":
        open_questions.append(
            {
                "id": "question-candidate-inventory-insufficient",
                "text": "Candidate inventory is sparse; return to discovery or provide structured idea markers before ranking.",
                "severity": "blocking",
            }
        )
    return normalize_extracted_concepts(
        {
            "schemaVersion": SCHEMA_VERSION,
            "decision": "captured",
            "rationale": "Raw discovery material was captured as candidate concepts; it is not authoritative top-down context.",
            "sourceSummary": summary,
            "possibleRoles": extracted["possibleRoles"],
            "possibleStakeholders": extracted["possibleStakeholders"],
            "possibleOutcomes": extracted["possibleOutcomes"],
            "possibleOperatingLoops": extracted["possibleOperatingLoops"],
            "possibleJourneys": extracted["possibleJourneys"],
            "possibleCandidateFeatures": extracted["possibleCandidateFeatures"],
            "possibleRisks": extracted["possibleRisks"],
            "possibleOpenQuestions": open_questions,
            "possibleRelationshipRefs": extracted["possibleRelationshipRefs"],
            "extractionCoverage": extracted["extractionCoverage"],
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
    if isinstance(payload.get("extractionCoverage"), Mapping):
        normalized["extractionCoverage"] = dict(payload["extractionCoverage"])
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


def write_extraction_coverage_artifact(docs_path: str | Path, concepts: Mapping[str, Any]) -> Path | None:
    coverage = concepts.get("extractionCoverage")
    if not isinstance(coverage, Mapping):
        return None
    output_path = Path(docs_path) / ".nextlens" / EXTRACTION_COVERAGE_ARTIFACT_REF
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(output_path.parent), prefix="extraction-coverage-", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(dict(coverage), handle, indent=2, sort_keys=True)
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
            source_refs = _list_value(item.get("sourceRefs"))
            extraction_confidence = str(item.get("extractionConfidence") or "").strip()
        else:
            text = str(item).strip()
            if not text:
                continue
            base_id = f"feature.{_slugify(text)}"
            name = text
            goal = f"Advance {text}"
            source_refs = []
            extraction_confidence = ""

        candidate_payload = {
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
                "bmadInputs": {"prd": True, "ux": True, "architecture": True},
            }
        if source_refs:
            candidate_payload["sourceRefs"] = [str(ref) for ref in source_refs]
            candidate_payload["relationshipRefs"] = [f"{base_id}->{ref}" for ref in candidate_payload["sourceRefs"]]
        if extraction_confidence:
            candidate_payload["extractionConfidence"] = extraction_confidence
        candidates.append(candidate_payload)

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


def _extract_raw_discovery_inventory(raw_text: str, *, source_ref: str) -> dict[str, Any]:
    sections = _raw_sections(raw_text)
    ideas = _extract_idea_markers(raw_text, sections, source_ref=source_ref)
    fallback_warnings: list[str] = []
    if not ideas and raw_text:
        fallback_warnings.append("No markdown headings or bracketed idea labels were detected; generated a low-confidence fallback candidate.")
        ideas = [
            {
                "marker": "fallback",
                "id": "feature.curated.default",
                "name": "Curated Feature Candidate",
                "goal": "Continue governed packet flow after extracted-concepts curation.",
                "sourceRefs": [source_ref],
                "section": "raw-discovery",
                "line": 1,
                "confidence": "low",
            }
        ]

    candidate_features = [
        {
            "id": idea["id"],
            "name": idea["name"],
            "goal": idea["goal"],
            "sourceRefs": idea["sourceRefs"],
            "extractionConfidence": idea["confidence"],
        }
        for idea in ideas
    ]
    source_idea_refs = [
        {
            "marker": idea["marker"],
            "candidateId": idea["id"],
            "section": idea["section"],
            "line": idea["line"],
            "sourceRefs": idea["sourceRefs"],
        }
        for idea in ideas
    ]
    confidence = "low" if not candidate_features or any(idea["confidence"] == "low" for idea in ideas) else "medium"
    if len(candidate_features) >= 6:
        confidence = "high"
    return {
        "possibleRoles": _keyword_concepts(
            raw_text,
            "role",
            {
                "student": "Student",
                "teacher": "Teacher",
                "parent": "Parent",
                "joey": "Joey AI coach",
                "systems coach": "Systems coach",
            },
        ),
        "possibleStakeholders": _keyword_concepts(
            raw_text,
            "stakeholder",
            {
                "student": "Student",
                "teacher": "Teacher",
                "parent": "Parent",
                "administrator": "Administrator",
                "rti": "RtI team",
            },
        ),
        "possibleOutcomes": _keyword_concepts(
            raw_text,
            "outcome",
            {
                "assessment": "Assessment evidence",
                "mastery": "Mastery visibility",
                "writing": "Writing growth",
                "micro-credential": "Teacher capability growth",
                "reporting": "Family reporting clarity",
                "mood": "Student readiness and belonging",
            },
        ),
        "possibleOperatingLoops": _keyword_concepts(
            raw_text,
            "loop",
            {
                "daily": "Daily learning evidence loop",
                "workshop": "Workshop model loop",
                "benchmark": "Benchmark assessment loop",
                "rti": "RtI response loop",
                "conference": "Shared conference loop",
            },
        ),
        "possibleJourneys": _keyword_concepts(
            raw_text,
            "journey",
            {
                "joey": "Student Joey coaching journey",
                "teacher dashboard": "Teacher dashboard journey",
                "assessment": "Assessment battery journey",
                "writing": "Writing evidence journey",
                "parent": "Parent reporting journey",
                "unit": "Unit and standards journey",
            },
        ),
        "possibleCandidateFeatures": candidate_features,
        "possibleRisks": [
            {"id": "risk.raw-discovery-overreach", "name": "Raw discovery may overstate implementation scope", "severity": "medium"},
            {"id": "risk.candidate-collisions", "name": "Nearby ideas may need clustering before packet emission", "severity": "medium"},
            {"id": "risk.source-coverage-gaps", "name": "Some source ideas may require human curation", "severity": "medium"},
        ],
        "possibleOpenQuestions": [
            {
                "id": "question-confirm-candidate-clustering",
                "text": "Which extracted idea should become the one selected Feature, and which adjacent ideas stay out of scope?",
                "severity": "major",
            }
        ],
        "possibleRelationshipRefs": [
            f"{idea['id']}->{ref}"
            for idea in ideas
            for ref in idea["sourceRefs"]
        ],
        "extractionCoverage": {
            "inputSourceRefs": [source_ref],
            "extractedCandidateCount": len(candidate_features),
            "sourceIdeaCount": len(source_idea_refs),
            "sourceIdeaRefs": source_idea_refs,
            "groupedSourceSections": sections,
            "unclusteredIdeaRefs": [],
            "droppedIdeaRefs": [],
            "extractionWarnings": fallback_warnings,
            "extractionConfidence": confidence,
        },
    }


def _extract_idea_markers(raw_text: str, sections: list[dict[str, Any]], *, source_ref: str) -> list[dict[str, Any]]:
    lines = raw_text.splitlines()
    bracket_pattern = re.compile(r"^\s*(?:[-*]\s*)?\[(?P<label>[A-Za-z][^\]#]{0,48})\s*#(?P<number>\d+)\]\s*(?P<title>.*)$")
    heading_pattern = re.compile(r"^\s{0,3}#{2,5}\s+(?P<title>.+?)\s*$")
    bullet_pattern = re.compile(r"^\s*[-*]\s+(?P<title>.+?)\s*$")
    ideas: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, line in enumerate(lines):
        match = bracket_pattern.match(line)
        if match:
            label = match.group("label").strip()
            number = match.group("number").strip()
            title = _clean_title(match.group("title")) or label
            marker = f"{label} #{number}"
            candidate_id = f"feature.{_slugify(label)}-{number}"
            section = _section_for_line(sections, index + 1)
            goal = _nearby_goal(lines, index, title)
            _append_unique_idea(
                ideas,
                seen_ids,
                {
                    "marker": marker,
                    "id": candidate_id,
                    "name": title,
                    "goal": goal,
                    "sourceRefs": [f"{source_ref}#line-{index + 1}", f"{source_ref}#{_slugify(section)}"],
                    "section": section,
                    "line": index + 1,
                    "confidence": "high",
                },
            )
            continue

        heading_match = heading_pattern.match(line)
        if heading_match:
            title = _clean_title(heading_match.group("title"))
            if _heading_is_candidate(title):
                section = title
                _append_unique_idea(
                    ideas,
                    seen_ids,
                    {
                        "marker": f"heading:{title}",
                        "id": f"feature.{_slugify(title)}",
                        "name": title,
                        "goal": _nearby_goal(lines, index, title),
                        "sourceRefs": [f"{source_ref}#line-{index + 1}", f"{source_ref}#{_slugify(section)}"],
                        "section": section,
                        "line": index + 1,
                        "confidence": "medium",
                    },
                )
            continue

        bullet_match = bullet_pattern.match(line)
        if bullet_match:
            title = _clean_title(bullet_match.group("title"))
            if _heading_is_candidate(title) and len(title.split()) <= 24:
                section = _section_for_line(sections, index + 1)
                _append_unique_idea(
                    ideas,
                    seen_ids,
                    {
                        "marker": f"bullet:{title}",
                        "id": f"feature.{_slugify(title)}",
                        "name": title,
                        "goal": _nearby_goal(lines, index, title),
                        "sourceRefs": [f"{source_ref}#line-{index + 1}", f"{source_ref}#{_slugify(section)}"],
                        "section": section,
                        "line": index + 1,
                        "confidence": "medium",
                    },
                )
    return ideas


def _append_unique_idea(ideas: list[dict[str, Any]], seen_ids: set[str], idea: dict[str, Any]) -> None:
    if idea["id"] in seen_ids:
        return
    seen_ids.add(idea["id"])
    ideas.append(idea)


def _nearby_goal(lines: list[str], start_index: int, title: str) -> str:
    snippets: list[str] = []
    for line in lines[start_index + 1 : start_index + 7]:
        stripped = line.strip(" -*\t")
        if not stripped:
            continue
        if stripped.startswith("#") or re.match(r"^\[[A-Za-z].*#\d+\]", stripped):
            break
        if stripped.lower().startswith(("concept:", "novelty:", "goal:", "outcome:", "summary:")):
            stripped = stripped.split(":", 1)[1].strip()
        snippets.append(stripped)
        if len(" ".join(snippets)) >= 160:
            break
    goal = " ".join(snippets).strip()
    return goal[:260] if goal else f"Advance {title} as a bounded Feature candidate."


def _raw_sections(raw_text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw_text.splitlines(), start=1):
        match = re.match(r"^\s{0,3}(#{1,5})\s+(.+?)\s*$", line)
        if match:
            sections.append(
                {
                    "title": _clean_title(match.group(2)),
                    "level": len(match.group(1)),
                    "line": line_number,
                }
            )
    return sections


def _section_for_line(sections: list[dict[str, Any]], line_number: int) -> str:
    current = "raw-discovery"
    for section in sections:
        if int(section.get("line") or 0) <= line_number:
            current = str(section.get("title") or current)
        else:
            break
    return current


def _heading_is_candidate(title: str) -> bool:
    lowered = title.lower()
    if len(title.split()) > 16:
        return False
    keywords = (
        "coach",
        "dashboard",
        "assessment",
        "benchmark",
        "hfw",
        "writing",
        "spelling",
        "unit",
        "workshop",
        "credential",
        "report",
        "rti",
        "store",
        "reward",
        "feature",
        "concept",
    )
    return any(keyword in lowered for keyword in keywords)


def _keyword_concepts(raw_text: str, prefix: str, terms: Mapping[str, str]) -> list[dict[str, Any]]:
    lowered = raw_text.lower()
    concepts = [
        {"id": f"{prefix}.{_slugify(name)}", "name": name}
        for term, name in terms.items()
        if term in lowered
    ]
    if not concepts:
        concepts.append({"id": f"{prefix}.operator", "name": "Operator"})
    return concepts


def _clean_title(value: str) -> str:
    cleaned = re.sub(r"^[\s:,-]+|[\s:,-]+$", "", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _source_ref(source: str) -> str:
    source_path = Path(source)
    if source_path.exists():
        return source_path.name
    return "raw-discovery"


def _slugify(value: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return collapsed or "value"


def _utc_day_token() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _require_yaml_support():
    if yaml is None:
        raise ExtractedConceptsError("PyYAML is required to load extracted_concepts.") from _YAML_IMPORT_ERROR
    return yaml
