#!/usr/bin/env python3
"""Bottom-Up LENS create workflow primitives and headless packet creator."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATE_SCRIPTS = SCRIPT_DIR.parent.parent / "bul-validate-packet" / "scripts"
VERIFY_SCRIPTS = SCRIPT_DIR.parent.parent / "bul-verify-receipt" / "scripts"
for candidate in (SCRIPT_DIR, VALIDATE_SCRIPTS, VERIFY_SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from path_guard import guard_path, guard_write_plan  # noqa: E402
from validation_contract import (  # noqa: E402
    BMAD_NOT_READY_LABEL,
    BMAD_READY_LABEL,
    PACKET_NOT_READY_LABEL,
    PACKET_VALID_LABEL,
    SUPPORTED_SCHEMA_VERSION,
    canonical_non_effects,
    canonical_topology,
)
from validate_packet import validate_packet  # noqa: E402
from verify_receipt import verify_receipt  # noqa: E402

STAGE_LABELS = [
    "context-intake",
    "candidate-selection",
    "local-sufficiency",
    "scope-boundary",
    "preview",
    "confirmation",
    "write",
    "receipt",
]

CONFIRMATION_TOKEN = "CREATE PACKET"
RUN_STATE_SCHEMA_VERSION = "bul.run-state.v1"
SECRET_MARKERS = ("secret", "token", "password", "credential", "api_key", "apikey", "authorization", "environment")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "bottom-up-feature"


def stable_packet_id(selected_feature: dict[str, Any]) -> str:
    base = f"{selected_feature.get('id', '')}|{selected_feature.get('title', '')}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]
    return f"bul-{slugify(str(selected_feature.get('title') or selected_feature.get('id') or 'feature'))}-{digest}"


def display_context(explicit_context: dict[str, Any], packet_output_path: str | Path, reports_output_path: str | Path) -> dict[str, Any]:
    missing = [key for key in ("contextSource", "operatorIntent") if not explicit_context.get(key)]
    inference_flags = [key for key in ("branch", "openEditor", "cwd") if explicit_context.get(f"inferredFrom{key[0].upper()}{key[1:]}")]
    status = "pass" if not missing and not inference_flags else "fail"
    return {
        "stage": "context-intake",
        "status": status,
        "explicitModuleContext": {
            "contextSource": explicit_context.get("contextSource"),
            "operatorIntent": explicit_context.get("operatorIntent"),
        },
        "packetOutputPath": str(Path(packet_output_path).expanduser()),
        "reportsOutputPath": str(Path(reports_output_path).expanduser()),
        "runtimeWriteScope": ["packet_output_path", "reports_output_path"],
        "blockedInferenceSources": inference_flags,
        "missingExplicitInputs": missing,
        "message": "Explicit context and configured output paths are displayed before any mutation-capable stage.",
    }


def extract_candidates(raw_context: str) -> list[dict[str, Any]]:
    lines = [line.strip(" -\t") for line in raw_context.splitlines() if line.strip(" -\t")]
    candidate_lines = [line for line in lines if line.lower().startswith(("feature:", "candidate:", "slice:"))]
    if not candidate_lines and raw_context.strip():
        candidate_lines = [raw_context.strip().splitlines()[0].strip()]
    candidates: list[dict[str, Any]] = []
    for index, line in enumerate(candidate_lines, start=1):
        title = re.sub(r"^(feature|candidate|slice):\s*", "", line, flags=re.IGNORECASE).strip()
        candidates.append({"id": f"candidate-{index}", "title": title, "selected": False, "deferredNote": None})
    return candidates


def select_candidate(candidates: list[dict[str, Any]], selected_id: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    selected_count = 0
    result: list[dict[str, Any]] = []
    for candidate in candidates:
        copy = dict(candidate)
        copy["selected"] = candidate.get("id") == selected_id
        if copy["selected"]:
            selected_count += 1
        else:
            copy["deferredNote"] = copy.get("deferredNote") or "Deferred unranked local note; not topology, roadmap, adjacency, or priority truth."
            copy.pop("rank", None)
        result.append(copy)
    if selected_count != 1:
        errors.append({
            "code": "candidateSelectionRequired",
            "field": "candidateFeatures",
            "message": "Exactly one selected candidate is required before proceeding.",
            "recommendation": "Select one candidate explicitly; zero or multiple selections write no packet.",
        })
    return result, errors


def compose_packet_draft(
    *,
    raw_context: str,
    selected_candidate: dict[str, Any],
    candidate_features: list[dict[str, Any]],
    actor: str,
    problem: str,
    outcome: str,
    acceptance_criteria: list[str],
    constraints: list[str],
    assumptions: list[str],
    included_scope: list[str],
    explicit_out_of_scope: list[str],
    input_refs: list[str],
    implementation_context: str = "",
) -> dict[str, Any]:
    packet_id = stable_packet_id(selected_candidate)
    return {
        "schemaVersion": SUPPORTED_SCHEMA_VERSION,
        "packetId": packet_id,
        "packetStatus": "draft",
        "sourceMode": "bottom_up",
        "identity": {
            "featureName": selected_candidate["title"],
            "actor": actor,
            "problem": problem,
            "outcome": outcome,
        },
        "selectedFeature": {"id": selected_candidate["id"], "title": selected_candidate["title"]},
        "candidateFeatures": candidate_features,
        "scope": {"included": included_scope, "explicitOutOfScope": explicit_out_of_scope},
        "acceptanceCriteria": acceptance_criteria,
        "constraints": constraints,
        "assumptions": [{"text": text, "status": "unpromoted"} for text in assumptions],
        "provenance": {
            "rawUserWording": raw_context,
            "inputRefs": input_refs,
            "explicitInputsOnly": True,
            "noBranchEditorCwdInference": True,
            "inferenceSources": [],
        },
        "handoff": {
            "implementationContext": implementation_context,
            "antiInferenceInstructions": "Use only packet fields and explicit inputRefs; do not infer from branch, open editor, or cwd/current working directory.",
        },
        "receiptReference": None,
        "topology": canonical_topology(),
        "nonEffects": canonical_non_effects(),
    }


def compose_packet_from_json(source: dict[str, Any]) -> dict[str, Any]:
    raw_context = str(source.get("rawContext") or source.get("rawUserWording") or "")
    candidates = source.get("candidateFeatures")
    if not isinstance(candidates, list) or not candidates:
        candidates = extract_candidates(raw_context)
    selected_id = source.get("selectedCandidateId") or source.get("selectedFeature", {}).get("id") or (candidates[0].get("id") if len(candidates) == 1 else None)
    selected_candidates, errors = select_candidate(candidates, str(selected_id) if selected_id else "")
    if errors:
        raise ValueError(errors[0]["message"])
    selected = next(candidate for candidate in selected_candidates if candidate.get("selected") is True)
    return compose_packet_draft(
        raw_context=raw_context,
        selected_candidate=selected,
        candidate_features=selected_candidates,
        actor=str(source.get("actor") or source.get("identity", {}).get("actor") or ""),
        problem=str(source.get("problem") or source.get("identity", {}).get("problem") or ""),
        outcome=str(source.get("outcome") or source.get("identity", {}).get("outcome") or ""),
        acceptance_criteria=list(source.get("acceptanceCriteria") or []),
        constraints=list(source.get("constraints") or []),
        assumptions=list(source.get("assumptions") or ["No additional assumptions identified."]),
        included_scope=list(source.get("includedScope") or source.get("scope", {}).get("included") or []),
        explicit_out_of_scope=list(source.get("explicitOutOfScope") or source.get("scope", {}).get("explicitOutOfScope") or []),
        input_refs=list(source.get("inputRefs") or source.get("provenance", {}).get("inputRefs") or ["explicit-headless-input"]),
        implementation_context=str(source.get("implementationContext") or source.get("handoff", {}).get("implementationContext") or ""),
    )


def render_preview(packet: dict[str, Any], packet_output_path: str | Path, reports_output_path: str | Path) -> str:
    validation = validate_packet(packet)
    target = Path(packet_output_path).expanduser().resolve() / f"{packet['packetId']}.json"
    guard = guard_path(target, [packet_output_path], "packetPath")
    bmad = validation["bmadReady"]
    return "\n".join(
        [
            "# Bottom-Up LENS Packet Preview",
            "",
            f"Selected feature: {packet['identity']['featureName']}",
            f"Included scope: {', '.join(map(str, packet['scope']['included']))}",
            f"Explicit out-of-scope: {', '.join(map(str, packet['scope']['explicitOutOfScope']))}",
            f"Assumptions: {', '.join(item['text'] for item in packet['assumptions'])}",
            f"Acceptance criteria: {len(packet['acceptanceCriteria'])}",
            f"Constraints: {len(packet['constraints'])}",
            f"Provenance: {', '.join(map(str, packet['provenance']['inputRefs']))}",
            f"Intended write target: {target}",
            f"Packet validity: {validation['packetValid']['label']}",
            f"BMAD readiness: {bmad['label']}",
            "",
            "Will write:",
            f"- Packet JSON under {Path(packet_output_path).expanduser()}",
            f"- Run metadata and receipt JSON under {Path(packet_output_path).expanduser()}",
            "",
            "Will not write:",
            "- Lens feature.yaml, governance publish or mirrors, branch topology, constitution runtime, release clones, current top-down runtime, Landscape, Derived Graph, Salmon, promotion, adjacency, pressure, roadmap, or service/domain/program truth paths.",
            "",
            f"Path guard: {guard['status']}",
            "Confirmation token: CREATE PACKET",
            f"Reports output path: {Path(reports_output_path).expanduser()}",
        ]
    )


def confirmation_allows_write(*, interactive_token: str | None = None, headless: bool = False, confirm_flag: bool = False) -> bool:
    if headless:
        return confirm_flag is True
    return interactive_token == CONFIRMATION_TOKEN


def manifest_for_paths(paths: list[Path]) -> list[dict[str, str]]:
    return [{"path": str(path), "kind": "file"} for path in paths]


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def duplicate_paths(packet_output_path: Path, packet_id: str, selected_candidate_id: str) -> list[Path]:
    packet_candidates = list(packet_output_path.glob(f"{packet_id}.json"))
    for path in packet_output_path.glob("*.json"):
        if path in packet_candidates:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("selectedFeature", {}).get("id") == selected_candidate_id:
            packet_candidates.append(path)
    return packet_candidates


def ensure_no_duplicate(packet_output_path: Path, packet: dict[str, Any], resolution: str | None = None) -> dict[str, Any]:
    duplicates = duplicate_paths(packet_output_path, packet["packetId"], packet["selectedFeature"]["id"])
    if not duplicates:
        return {"status": "pass", "duplicates": []}
    if resolution not in {"overwrite", "new-packet"}:
        return {
            "status": "fail",
            "duplicates": [str(path) for path in duplicates],
            "message": "Duplicate packet attempt detected; explicit operator resolution is required before any write.",
        }
    if resolution == "overwrite":
        return {"status": "pass", "duplicates": [str(path) for path in duplicates], "resolution": resolution}
    packet["packetId"] = f"{packet['packetId']}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    return {"status": "pass", "duplicates": [str(path) for path in duplicates], "resolution": resolution}


def save_run_state(run_state_path: Path, state: dict[str, Any], allowed_roots: list[Path]) -> dict[str, Any]:
    guard = guard_path(run_state_path, allowed_roots, "runStatePath")
    if guard["status"] != "pass":
        return guard
    text = json.dumps(state, sort_keys=True).lower()
    if any(marker in text for marker in SECRET_MARKERS):
        return {
            "status": "fail",
            "pathGuard": {
                "category": "secret-scan",
                "field": "runState",
                "message": "Run-state cache must not store secrets, credentials, tokens, or broad environment dumps.",
                "recommendation": "Store only stage, packet id, selected candidate id, and explicit non-secret context references.",
            },
        }
    payload = dict(state)
    payload.setdefault("schemaVersion", RUN_STATE_SCHEMA_VERSION)
    payload.setdefault("cacheOnly", True)
    payload.setdefault("notPacketValidity", True)
    payload.setdefault("notTopologyTruth", True)
    atomic_write_json(run_state_path, payload)
    return {"status": "pass", "runStatePath": str(run_state_path)}


def resume_run_state(run_state_path: Path) -> dict[str, Any]:
    data = json.loads(run_state_path.read_text(encoding="utf-8"))
    if data.get("schemaVersion") != RUN_STATE_SCHEMA_VERSION:
        return {"status": "fail", "message": "Unsupported run-state schema; restart with explicit context."}
    stage = data.get("stage")
    if stage not in STAGE_LABELS:
        return {"status": "fail", "message": "Unknown saved stage; restart with explicit context."}
    safe_index = min(STAGE_LABELS.index(stage), STAGE_LABELS.index("preview"))
    return {
        "status": "pass",
        "resumeStage": STAGE_LABELS[safe_index],
        "requiresRevalidationBeforeWrite": True,
        "cacheOnly": data.get("cacheOnly") is True,
        "notTopologyTruth": data.get("notTopologyTruth") is True,
    }


def cancel_result(reason: str) -> dict[str, Any]:
    return {
        "status": "cancelled",
        "acceptedPacketWritten": False,
        "message": f"Cancelled: {reason}. No packet, receipt, run metadata, governance file, release clone file, or top-down runtime file was written.",
    }


def write_accepted_packet(packet: dict[str, Any], packet_output_path: Path) -> dict[str, Any]:
    packet_output_path = packet_output_path.expanduser().resolve()
    packet_path = packet_output_path / f"{packet['packetId']}.json"
    metadata_path = packet_output_path / f"{packet['packetId']}.run-metadata.json"
    receipt_path = packet_output_path / f"{packet['packetId']}.receipt.json"
    plan = guard_write_plan([packet_path, metadata_path, receipt_path], [packet_output_path])
    if plan["status"] != "pass":
        return {"status": "fail", "acceptedPacketWritten": False, "pathGuard": plan}

    validation = validate_packet(packet)
    if validation["packetValid"]["status"] != "pass":
        return {"status": "fail", "acceptedPacketWritten": False, "validation": validation}

    now = utc_now()
    accepted_packet = json.loads(json.dumps(packet))
    accepted_packet["packetStatus"] = "accepted"
    accepted_packet["receiptReference"] = {"receiptPath": str(receipt_path), "runMetadataPath": str(metadata_path)}

    written_paths = [packet_path, metadata_path, receipt_path]
    run_metadata = {
        "schemaVersion": "bul.run-metadata.v1",
        "runId": f"run-{accepted_packet['packetId']}",
        "packetId": accepted_packet["packetId"],
        "createdAt": now,
        "explicitInputsOnly": True,
        "writtenFiles": manifest_for_paths(written_paths),
        "changedFiles": manifest_for_paths(written_paths),
        "environmentCaptured": False,
        "secretsCaptured": False,
    }
    receipt = {
        "schemaVersion": "bul.receipt.v1",
        "packetId": accepted_packet["packetId"],
        "runId": run_metadata["runId"],
        "status": "pending-verification",
        "writtenFiles": manifest_for_paths(written_paths),
        "changedFiles": manifest_for_paths(written_paths),
        "nonEffects": canonical_non_effects(),
    }

    try:
        atomic_write_json(packet_path, accepted_packet)
        atomic_write_json(metadata_path, run_metadata)
        atomic_write_json(receipt_path, receipt)
    except Exception as exc:  # pragma: no cover - defensive rollback guidance
        return {
            "status": "fail",
            "acceptedPacketWritten": False,
            "message": f"Write failed: {exc}",
            "rollbackGuidance": "Remove any temporary files in the packet output directory and rerun after validation passes.",
        }

    verification = verify_receipt(receipt, run_metadata)
    if verification["status"] != "pass":
        return {"status": "fail", "acceptedPacketWritten": False, "verification": verification, "runValid": False}

    receipt["status"] = "verified"
    atomic_write_json(receipt_path, receipt)
    return {
        "status": "pass",
        "acceptedPacketWritten": True,
        "packetPath": str(packet_path),
        "runMetadataPath": str(metadata_path),
        "receiptPath": str(receipt_path),
        "verification": verification,
        "labels": [PACKET_VALID_LABEL, validation["bmadReady"]["label"], "Non-effects verified"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Bottom-Up LENS packet from explicit JSON input.")
    parser.add_argument("--input", required=True, help="Explicit JSON input/draft data")
    parser.add_argument("--packet-output-path", required=True)
    parser.add_argument("--reports-output-path", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", action="store_true", help="Required for headless writes")
    parser.add_argument("--duplicate-resolution", choices=["overwrite", "new-packet"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    packet = compose_packet_from_json(source)
    preview = render_preview(packet, args.packet_output_path, args.reports_output_path)
    if args.dry_run:
        print(json.dumps({"status": "dry-run", "acceptedPacketWritten": False, "preview": preview}, indent=2))
        return 0
    if not confirmation_allows_write(headless=True, confirm_flag=args.confirm):
        print(json.dumps({"status": "blocked", "acceptedPacketWritten": False, "message": "Headless writes require --confirm."}, indent=2))
        return 1
    duplicate = ensure_no_duplicate(Path(args.packet_output_path).expanduser().resolve(), packet, args.duplicate_resolution)
    if duplicate["status"] != "pass":
        print(json.dumps({"status": "blocked", "acceptedPacketWritten": False, "duplicate": duplicate}, indent=2))
        return 1
    result = write_accepted_packet(packet, Path(args.packet_output_path))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
