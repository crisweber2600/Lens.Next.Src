#!/usr/bin/env python3
"""Verify Bottom-Up LENS receipt and run metadata non-effects claims."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

CREATE_SCRIPTS = Path(__file__).resolve().parents[1].parent / "bul-create-packet" / "scripts"
if str(CREATE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CREATE_SCRIPTS))
from path_guard import denied_category_for, guard_path  # noqa: E402

RECEIPT_SCHEMA_VERSION = "bul.receipt.v1"
RUN_METADATA_SCHEMA_VERSION = "bul.run-metadata.v1"
PASS_LABEL = "Non-effects verified"
FAIL_LABEL = "Receipt mismatch detected"


def _error(code: str, field: str, message: str, recommendation: str, evidence: Any | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "code": code,
        "field": field,
        "message": message,
        "recommendation": recommendation,
    }
    if evidence is not None:
        result["evidence"] = evidence
    return result


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _paths_from_manifest(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and isinstance(item.get("path"), str):
            result.append(item["path"])
    return result


def _normalize_paths(paths: list[str]) -> set[str]:
    return {str(Path(path)) for path in paths}


def verify_receipt(receipt: dict[str, Any], run_metadata: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []

    if receipt.get("schemaVersion") != RECEIPT_SCHEMA_VERSION:
        errors.append(_error("invalidReceiptSchema", "receipt.schemaVersion", "Receipt schema version is unsupported.", "Use bul.receipt.v1."))
    if run_metadata.get("schemaVersion") != RUN_METADATA_SCHEMA_VERSION:
        errors.append(_error("invalidRunMetadataSchema", "runMetadata.schemaVersion", "Run metadata schema version is unsupported.", "Use bul.run-metadata.v1."))

    receipt_written = _paths_from_manifest(receipt.get("writtenFiles"))
    receipt_changed = _paths_from_manifest(receipt.get("changedFiles"))
    metadata_written = _paths_from_manifest(run_metadata.get("writtenFiles"))
    metadata_changed = _paths_from_manifest(run_metadata.get("changedFiles"))

    if not metadata_changed and not metadata_written:
        errors.append(
            _error(
                "missingChangedFileManifest",
                "runMetadata.changedFiles",
                "Run metadata must include changedFiles or writtenFiles evidence.",
                "Capture changed-file manifests from the write workflow before claiming non-effects.",
            )
        )

    if _normalize_paths(receipt_written) != _normalize_paths(metadata_written):
        errors.append(
            _error(
                "writtenFilesMismatch",
                "writtenFiles",
                "Receipt writtenFiles do not match run metadata writtenFiles.",
                "Generate receipt claims from observed run metadata instead of prose promises.",
                {"receipt": receipt_written, "runMetadata": metadata_written},
            )
        )
    if receipt_changed and _normalize_paths(receipt_changed) != _normalize_paths(metadata_changed):
        errors.append(
            _error(
                "changedFilesMismatch",
                "changedFiles",
                "Receipt changedFiles do not match run metadata changedFiles.",
                "Generate receipt changedFiles from observed manifests.",
                {"receipt": receipt_changed, "runMetadata": metadata_changed},
            )
        )

    changed_evidence = sorted(set(metadata_changed or metadata_written))
    for changed in changed_evidence:
        category = denied_category_for(Path(changed).expanduser())
        if category:
            errors.append(
                _error(
                    "forbiddenChangedFile",
                    "runMetadata.changedFiles",
                    f"Changed file violates denied category: {category}.",
                    "Stop the run, mark it invalid, and remove any forbidden write from the create workflow.",
                    {"category": category, "path": changed},
                )
            )

    non_effects = receipt.get("nonEffects")
    if not isinstance(non_effects, dict):
        errors.append(_error("missingNonEffects", "receipt.nonEffects", "Receipt nonEffects claims are required.", "Include explicit false/no-effect claims for forbidden categories."))
    else:
        false_graph_claim = non_effects.get("derivedGraphWritten") is False or non_effects.get("graphWritten") is False
        graph_changes = [path for path in changed_evidence if denied_category_for(Path(path).expanduser()) == "graph"]
        if false_graph_claim and graph_changes:
            errors.append(
                _error(
                    "falseReceiptClaim",
                    "receipt.nonEffects.derivedGraphWritten",
                    "Receipt claims no graph update but changed files include graph paths.",
                    "Report Receipt mismatch detected and mark this run invalid.",
                    {"category": "graph", "changedFiles": graph_changes},
                )
            )

    status = "pass" if not errors else "fail"
    return {
        "schemaVersion": "bul.receipt-verification.v1",
        "status": status,
        "runValid": status == "pass",
        "label": PASS_LABEL if status == "pass" else FAIL_LABEL,
        "checkedFiles": {
            "writtenFiles": metadata_written,
            "changedFiles": metadata_changed,
            "count": len(changed_evidence),
        },
        "errors": errors,
        "hardBlockers": errors,
    }


def write_report_atomic(result: dict[str, Any], report_path: Path, reports_output_path: Path) -> Path:
    guard = guard_path(report_path, [reports_output_path], "reportPath")
    if guard["status"] != "pass":
        raise ValueError(guard["pathGuard"]["message"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(report_path.parent), delete=False) as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
        tmp_path = Path(handle.name)
    tmp_path.replace(report_path)
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Bottom-Up LENS receipt and run metadata without mutating inputs.")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--run-metadata", required=True)
    parser.add_argument("--report")
    parser.add_argument("--reports-output-path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt_path = Path(args.receipt).expanduser().resolve()
    metadata_path = Path(args.run_metadata).expanduser().resolve()
    result = verify_receipt(load_json(receipt_path), load_json(metadata_path))
    result["receiptSource"] = str(receipt_path)
    result["runMetadataSource"] = str(metadata_path)
    if args.report:
        if not args.reports_output_path:
            raise SystemExit("--reports-output-path is required when --report is supplied")
        result["reportPath"] = str(write_report_atomic(result, Path(args.report).expanduser().resolve(), Path(args.reports_output_path).expanduser().resolve()))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
