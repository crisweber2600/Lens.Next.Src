"""Generate human-readable NextLens run traceability indexes."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class TraceabilityIndexResult:
    status: str
    path: Path | None = None
    markdown: str = ""
    error: str | None = None


def traceability_index_path(docs_path: str | Path) -> Path:
    return Path(docs_path) / ".nextlens" / "traceability-index.md"


def write_traceability_index(
    docs_path: str | Path,
    bundles: Sequence[Mapping[str, Any]],
    *,
    replace_fn: Callable[[str, str], None] | None = None,
) -> TraceabilityIndexResult:
    try:
        output_path = traceability_index_path(docs_path)
        markdown = render_traceability_index(bundles)
        _atomic_write_text(output_path, markdown, replace_fn=replace_fn)
        return TraceabilityIndexResult(status="pass", path=output_path, markdown=markdown)
    except Exception as exc:
        return TraceabilityIndexResult(status="fail", error=str(exc))


def render_traceability_index(bundles: Sequence[Mapping[str, Any]]) -> str:
    if not bundles:
        raise ValueError("at least one evidence bundle is required to render traceability index.")
    ordered_bundles = sorted(bundles, key=_completed_at, reverse=True)
    latest = ordered_bundles[0]
    lines = [
        "# NextLens Traceability Index",
        "",
        "## Recent Runs",
        "",
        "| Run ID | Timestamp | Feature Selected | Doctor Status | Result | Evidence | Packet |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for bundle in ordered_bundles:
        lines.append(_recent_run_row(bundle))
    lines.extend(["", "## Quick Links", ""])
    lines.extend(_quick_link_lines(latest))
    lines.extend(["", "## Lineage", ""])
    lines.extend(_lineage_lines(latest))
    lines.extend(["", "## Key Decisions", ""])
    lines.extend(_key_decision_lines(latest))
    return "\n".join(lines).rstrip() + "\n"


def _recent_run_row(bundle: Mapping[str, Any]) -> str:
    run = _mapping(bundle.get("run"))
    run_id = str(run.get("run_id") or "unknown")
    timestamp = str(run.get("completed_at") or run.get("started_at") or "unknown")
    feature = _selected_feature(bundle)
    doctor = _doctor_status(bundle)
    result = _run_result(bundle)
    artifacts = _mapping(bundle.get("artifacts"))
    evidence_link = _markdown_link("evidence", artifacts.get("evidence_bundle_yaml"))
    packet_link = _markdown_link("packet", artifacts.get("packet_json"))
    return f"| {run_id[:8]} | {timestamp} | {feature} | {doctor} | {result} | {evidence_link} | {packet_link} |"


def _quick_link_lines(bundle: Mapping[str, Any]) -> list[str]:
    artifacts = _mapping(bundle.get("artifacts"))
    salmon = _mapping(_records(bundle).get("salmon_routing"))
    return [
        f"- Latest evidence bundle: {_markdown_link('evidence', artifacts.get('evidence_bundle_yaml'))}",
        f"- Latest packet JSON: {_markdown_link('packet', artifacts.get('packet_json'))}",
        f"- Latest doctor report: {_markdown_link('doctor report', artifacts.get('doctor_report_jsonl'))}",
        f"- Latest salmon events summary: {_markdown_link('salmon summary', salmon.get('event_summary_path'))}",
    ]


def _lineage_lines(bundle: Mapping[str, Any]) -> list[str]:
    lineage = _mapping(bundle.get("lineage"))
    records = _records(bundle)
    feature = _mapping(records.get("feature_ranking")).get("top_candidate_selected")
    feature_payload = _mapping(feature)
    run = _mapping(bundle.get("run"))
    artifacts = _mapping(bundle.get("artifacts"))
    system = _mapping(lineage.get("system")) or {"id": "unknown-system", "name": "Unknown system"}
    roles = _mapping_sequence(lineage.get("roles")) or [{"id": "unknown-role", "name": "Unknown role"}]
    outcomes = _mapping_sequence(lineage.get("outcomes")) or [{"id": "unknown-outcome", "name": "Unknown outcome"}]
    journeys = _mapping_sequence(lineage.get("journeys")) or [{"id": "unknown-journey", "name": "Unknown journey"}]
    feature_id = str(feature_payload.get("id") or "unknown-feature")
    feature_name = str(feature_payload.get("name") or feature_id)
    packet_id = str(run.get("packet_id") or "no-packet")
    packet_path = str(artifacts.get("packet_json") or "no packet emitted")

    lines = [
        "System -> Roles -> Outcomes -> Journeys -> Feature -> Packet",
        f"- {_entity_label(system)}",
    ]
    for role in roles:
        lines.append(f"  -> {_entity_label(role)}")
    for outcome in outcomes:
        lines.append(f"    -> {_entity_label(outcome)}")
    for journey in journeys:
        lines.append(f"      -> {_entity_label(journey)}")
    lines.append(f"        -> {feature_id}: {feature_name}")
    lines.append(f"          -> {packet_id}: {packet_path}")
    return lines


def _key_decision_lines(bundle: Mapping[str, Any]) -> list[str]:
    records = _records(bundle)
    sufficiency = _mapping(records.get("context_sufficiency"))
    ranking = _mapping(records.get("feature_ranking"))
    doctor = _mapping(records.get("doctor_validation"))
    confirmations = _mapping_sequence(bundle.get("operator_confirmations"))
    warnings = ", ".join(str(item) for item in _sequence(sufficiency.get("warnings"))) or "none"
    top_candidate = _mapping(ranking.get("top_candidate_selected"))
    confirmation_summary = ", ".join(
        f"{item.get('stage_name', 'unknown')}={item.get('confirmation', 'unknown')}"
        for item in confirmations
    ) or "none"
    return [
        f"- Context sufficiency: {sufficiency.get('status', 'unknown')} ({sufficiency.get('recommendation', 'no recommendation')}); warnings: {warnings}",
        f"- Ranking: selected {top_candidate.get('id', 'unknown')} at score {top_candidate.get('score', 'unknown')}; tie break applied: {ranking.get('tie_break_applied', 'unknown')}",
        f"- Operator confirmations: {confirmation_summary}",
        f"- Doctor findings: status={doctor.get('status', 'unknown')}, blocking={doctor.get('blocking_findings', 0)}, advisory={doctor.get('advisory_findings', 0)}, informational={doctor.get('informational_findings', 0)}",
    ]


def _selected_feature(bundle: Mapping[str, Any]) -> str:
    ranking = _mapping(_records(bundle).get("feature_ranking"))
    selected = _mapping(ranking.get("top_candidate_selected"))
    feature_id = str(selected.get("id") or "unknown")
    feature_name = str(selected.get("name") or feature_id)
    return f"{feature_id}: {feature_name}"


def _doctor_status(bundle: Mapping[str, Any]) -> str:
    return str(_mapping(_records(bundle).get("doctor_validation")).get("status") or "unknown")


def _run_result(bundle: Mapping[str, Any]) -> str:
    doctor = _mapping(_records(bundle).get("doctor_validation"))
    errors = _mapping(bundle.get("errors_and_warnings")).get("errors")
    if _sequence(errors) or int(doctor.get("blocking_findings") or 0) > 0:
        return "blocked"
    if int(doctor.get("advisory_findings") or 0) > 0:
        return "advisory"
    return "success"


def _records(bundle: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(bundle.get("records"))


def _completed_at(bundle: Mapping[str, Any]) -> str:
    run = _mapping(bundle.get("run"))
    return str(run.get("completed_at") or run.get("started_at") or "")


def _entity_label(entity: Mapping[str, Any]) -> str:
    entity_id = str(entity.get("id") or "unknown")
    name = str(entity.get("name") or entity_id)
    return f"{entity_id}: {name}"


def _markdown_link(label: str, target: Any) -> str:
    if not target:
        return "n/a"
    return f"[{label}]({target})"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _mapping_sequence(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in _sequence(value) if isinstance(item, Mapping)]


def _atomic_write_text(
    path: Path,
    text: str,
    *,
    replace_fn: Callable[[str, str], None] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f"{path.stem}-", suffix=".tmp")
    temp_path = Path(temp_name)
    active_replace = replace_fn or os.replace
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        active_replace(str(temp_path), str(path))
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise