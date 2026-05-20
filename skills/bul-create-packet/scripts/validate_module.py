#!/usr/bin/env python3
"""Bottom-Up LENS package/module validation."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REQUIRED_MARKETPLACE_FIELDS = ["name", "owner", "license", "homepage", "repository", "keywords", "plugins"]
REQUIRED_PLUGIN_FIELDS = ["name", "source", "displayName", "description", "version", "author", "skills", "module"]
REQUIRED_SKILLS = ["bul-setup", "bul-create-packet", "bul-validate-packet", "bul-verify-receipt"]
FORBIDDEN_METADATA_PHRASES = [
    "governance installation",
    "publish to governance",
    "create lens branches",
    "branch topology",
    "constitution runtime",
    "salmon routing",
    "top-down bridge",
    "doctor-validation",
]


def _error(code: str, field: str, message: str, recommendation: str) -> dict[str, str]:
    return {"code": code, "field": field, "message": message, "recommendation": recommendation}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def validate_marketplace(repo_root: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.exists():
        return [_error("missingMarketplace", ".claude-plugin/marketplace.json", "Marketplace metadata is missing.", "Create marketplace.json before release.")]
    data = load_json(marketplace_path)
    for field in REQUIRED_MARKETPLACE_FIELDS:
        if field not in data or data[field] in (None, "", [], {}):
            errors.append(_error("missingMarketplaceField", field, f"Marketplace field {field} is required.", "Fill all package metadata before release."))
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        errors.append(_error("invalidPluginList", "plugins", "Exactly one Bottom-Up LENS plugin must be registered.", "Register the standalone bul plugin only."))
        return errors
    plugin = plugins[0]
    for field in REQUIRED_PLUGIN_FIELDS:
        if field not in plugin or plugin[field] in (None, "", [], {}):
            errors.append(_error("missingPluginField", f"plugins[0].{field}", f"Plugin field {field} is required.", "Complete plugin metadata before release."))
    if plugin.get("name") != "bul":
        errors.append(_error("invalidModuleCode", "plugins[0].name", "Module code must be bul.", "Set plugin name to bul."))
    if plugin.get("displayName") != "Bottom-Up LENS":
        errors.append(_error("invalidModuleName", "plugins[0].displayName", "Module name must be Bottom-Up LENS.", "Set displayName to Bottom-Up LENS."))
    if plugin.get("version") != "1.0.0":
        errors.append(_error("invalidVersion", "plugins[0].version", "Initial version must be 1.0.0.", "Set the initial version to 1.0.0."))
    skills = plugin.get("skills", [])
    for skill in REQUIRED_SKILLS:
        if f"skills/{skill}" not in skills:
            errors.append(_error("missingSkill", "plugins[0].skills", f"{skill} must be listed.", "List all Bottom-Up LENS skills in marketplace metadata."))
    text = marketplace_path.read_text(encoding="utf-8").lower()
    for phrase in FORBIDDEN_METADATA_PHRASES:
        if phrase in text:
            errors.append(_error("forbiddenMetadataClaim", ".claude-plugin/marketplace.json", f"Forbidden metadata phrase found: {phrase}.", "Describe Bottom-Up LENS as standalone packet creation and verification only."))
    if not (repo_root / "LICENSE").is_file():
        errors.append(_error("missingLicense", "LICENSE", "License file is required.", "Add or restore the MIT LICENSE file."))
    return errors


def validate_help(repo_root: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    help_path = repo_root / "skills" / "bul-setup" / "assets" / "module-help.csv"
    if not help_path.exists():
        return [_error("missingHelp", str(help_path), "Module help CSV is missing.", "Restore module-help.csv.")]
    rows = list(csv.DictReader(help_path.open(newline="", encoding="utf-8")))
    actions = {row.get("action") for row in rows}
    for action in {"configure", "create-packet", "validate-packet", "verify-receipt"}:
        if action not in actions:
            errors.append(_error("missingHelpAction", "module-help.csv", f"Help action {action} is missing.", "Expose configure, create, validate, and verify actions."))
    return errors


def validate_evals(repo_root: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for relative in ["evals/bul-create-packet/evals.json", "evals/bul-create-packet/triggers.json", "evals/bul-validate-packet/evals.json", "evals/bul-verify-receipt/evals.json"]:
        path = repo_root / relative
        if not path.exists():
            errors.append(_error("missingEval", relative, "Eval artifact is missing.", "Add executable eval definitions before release."))
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(_error("invalidEvalJson", relative, f"Eval JSON is invalid: {exc}", "Fix eval syntax before release."))
    return errors


def run_pytest(repo_root: Path) -> dict[str, Any]:
    command = [sys.executable, "-m", "pytest", "tests", "-q"]
    completed = subprocess.run(command, cwd=repo_root, text=True, capture_output=True)
    return {"command": " ".join(command), "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def _resolve_json_path(data: dict[str, Any], path: str) -> list[Any]:
    current: list[Any] = [data]
    for part in path.split("."):
        wildcard = part.endswith("[*]")
        key = part[:-3] if wildcard else part
        next_values: list[Any] = []
        for value in current:
            if isinstance(value, dict) and key in value:
                child = value[key]
                if wildcard and isinstance(child, list):
                    next_values.extend(child)
                else:
                    next_values.append(child)
        current = next_values
    return current


def _assert_eval(output: dict[str, Any], assertion: dict[str, Any]) -> bool:
    values = _resolve_json_path(output, str(assertion.get("path", "")))
    if "equals" in assertion:
        return any(value == assertion["equals"] for value in values)
    if "contains" in assertion:
        expected = assertion["contains"]
        for value in values:
            if isinstance(value, list) and expected in value:
                return True
            if isinstance(value, str) and str(expected) in value:
                return True
            if value == expected:
                return True
    return False


def _run_eval_case(repo_root: Path, suite_path: Path, eval_case: dict[str, Any], tmp_root: Path) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    command = str(eval_case.get("command") or "")
    if not command:
        return [_error("missingEvalCommand", str(suite_path), "Eval case command is missing.", "Add an executable command for every eval case.")]

    replacements = {"{tmp}": str(tmp_root), "{input}": "", "{receipt}": "", "{runMetadata}": ""}
    for key, token in (("input", "{input}"), ("receipt", "{receipt}"), ("runMetadata", "{runMetadata}")):
        if key in eval_case:
            replacements[token] = str((suite_path.parent / str(eval_case[key])).resolve())
    for token, value in replacements.items():
        command = command.replace(token, value)

    completed = subprocess.run(command, cwd=repo_root, text=True, capture_output=True, shell=True)
    stdout = completed.stdout.strip()
    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return [
            _error(
                "evalOutputNotJson",
                str(suite_path),
                f"Eval '{eval_case.get('name')}' did not emit JSON: {exc}.",
                "Make eval commands emit machine-readable JSON before release.",
            )
        ]

    allowed_nonzero_statuses = {"fail", "blocked", "dry-run"}
    expected_success = not any(
        str(assertion.get("path", "")).endswith("status") and assertion.get("equals") in allowed_nonzero_statuses
        for assertion in eval_case.get("assertions", [])
    )
    if expected_success and completed.returncode != 0:
        errors.append(_error("evalCommandFailed", str(suite_path), f"Eval '{eval_case.get('name')}' exited {completed.returncode}.", completed.stderr.strip() or "Fix the eval command."))

    for assertion in eval_case.get("assertions", []):
        if not _assert_eval(output, assertion):
            errors.append(
                _error(
                    "evalAssertionFailed",
                    str(suite_path),
                    f"Eval '{eval_case.get('name')}' assertion failed: {assertion}.",
                    "Update the fixture, command, or implementation so eval assertions prove behavior.",
                )
            )
    return errors


def run_artifact_evals(repo_root: Path) -> dict[str, Any]:
    eval_paths = [
        repo_root / "evals" / "bul-create-packet" / "evals.json",
        repo_root / "evals" / "bul-validate-packet" / "evals.json",
        repo_root / "evals" / "bul-verify-receipt" / "evals.json",
    ]
    errors: list[dict[str, str]] = []
    executed = 0
    with tempfile.TemporaryDirectory(prefix="bul-evals-") as tmp:
        tmp_root = Path(tmp)
        for suite_path in eval_paths:
            suite = load_json(suite_path)
            cases = suite.get("evals")
            if not isinstance(cases, list) or not cases:
                errors.append(_error("missingEvalCases", str(suite_path), "Eval suite has no cases.", "Add executable eval cases before release."))
                continue
            for eval_case in cases:
                executed += 1
                errors.extend(_run_eval_case(repo_root, suite_path, eval_case, tmp_root / str(executed)))
    return {"status": "pass" if not errors else "fail", "executed": executed, "errors": errors}


def validate_module(repo_root: Path, run_tests: bool = False, run_evals: bool = False) -> dict[str, Any]:
    errors = validate_marketplace(repo_root) + validate_help(repo_root) + validate_evals(repo_root)
    tests: dict[str, Any] | None = None
    evals: dict[str, Any] | None = None
    if run_tests:
        tests = run_pytest(repo_root)
        if tests["returncode"] != 0:
            errors.append(_error("testsFailed", "tests", "Unit or fixture tests failed.", "Fix tests before release."))
    if run_evals:
        evals = run_artifact_evals(repo_root)
        errors.extend(evals["errors"])
    return {
        "schemaVersion": "bul.module-validation.v1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "releaseChecklist": [
            "Marketplace metadata complete",
            "README and command docs complete",
            "Golden examples synchronized with validator/readiness/verifier",
            "Artifact and trigger evals parse and assert boundaries",
            "Unit and fixture tests pass",
            "Read-only consumer and traceability contracts pass",
        ],
        "tests": tests,
        "evals": evals,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Bottom-Up LENS module release readiness.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--run-evals", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_module(Path(args.repo_root).resolve(), run_tests=args.run_tests, run_evals=args.run_evals)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
