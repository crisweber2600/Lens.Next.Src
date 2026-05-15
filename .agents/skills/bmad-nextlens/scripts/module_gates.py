"""Create Module and Validate Module gates for NextLens packaging."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Callable, Mapping, Sequence

try:
    import yaml
except ModuleNotFoundError as exc:  # pragma: no cover
    yaml = None
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None


MODULE_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
MODULE_SKILL_PATH = ".agents/skills/bmad-nextlens/SKILL.md"

CAPABILITIES = (
    {
        "command": "nextlens-new",
        "name": "NextLens New Packet",
        "description": "Create one Feature packet from top-down discovery context",
        "entry_point": "commands/new.ts",
        "keywords": "nextlens new,top-down bridge,feature packet,deterministic selection",
    },
    {
        "command": "nextlens-doctor",
        "name": "NextLens Doctor",
        "description": "Run non-mutating validation checks on packet or landscape",
        "entry_point": "commands/doctor.ts",
        "keywords": "nextlens doctor,validate packet,check landscape,doctor validation",
    },
    {
        "command": "nextlens-salmon",
        "name": "NextLens Salmon",
        "description": "Route correction signals through deduplication and impact classification",
        "entry_point": "commands/salmon.ts",
        "keywords": "nextlens salmon,route correction,deduplicate events,correction routing",
    },
)


@dataclass(frozen=True)
class ModuleGateFinding:
    check_id: str
    status: str
    message: str
    remediation: str


@dataclass(frozen=True)
class ModuleGateResult:
    status: str
    approved_for_distribution: bool
    findings: tuple[ModuleGateFinding, ...] = ()
    generated_at: str | None = None
    generated_files: tuple[dict[str, str], ...] = ()
    report_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "approved_for_distribution": self.approved_for_distribution,
            "generated_at": self.generated_at,
            "generated_files": list(self.generated_files),
            "report_path": str(self.report_path) if self.report_path else None,
            "findings": [finding.__dict__ for finding in self.findings],
        }


def create_module_package(repo_root: str | Path, *, now_factory: Callable[[], datetime] | None = None) -> ModuleGateResult:
    root = Path(repo_root)
    generated_at = _utc_timestamp(now_factory)
    files = {
        root / ".agents" / "skills" / "bmad-nextlens" / "assets" / "module.yaml": _module_yaml_text(),
        root / ".agents" / "skills" / "bmad-nextlens" / "assets" / "module-help.csv": _module_help_text(),
        root / ".claude-plugin" / "marketplace.json": _marketplace_json_text(),
    }
    findings = list(_skill_reference_findings(root))
    if findings:
        return ModuleGateResult(status="fail", approved_for_distribution=False, findings=tuple(findings), generated_at=generated_at)

    generated_files: list[dict[str, str]] = []
    for path, text in files.items():
        _atomic_write_text(path, text)
        generated_files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "checksum": _sha256_text(text),
                "generated_at": generated_at,
            }
        )

    report_path = root / ".claude-plugin" / "module-gates.json"
    report = {
        "gate": "create-module",
        "status": "pass",
        "generated_at": generated_at,
        "generated_files": generated_files,
    }
    _atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return ModuleGateResult(
        status="pass",
        approved_for_distribution=True,
        generated_at=generated_at,
        generated_files=tuple(generated_files),
        report_path=report_path,
    )


def validate_module_package(repo_root: str | Path) -> ModuleGateResult:
    root = Path(repo_root)
    findings: list[ModuleGateFinding] = []
    module_yaml = _load_yaml(root / ".agents" / "skills" / "bmad-nextlens" / "assets" / "module.yaml", findings)
    module_help = _load_module_help(root / ".agents" / "skills" / "bmad-nextlens" / "assets" / "module-help.csv", findings)
    marketplace = _load_json(root / ".claude-plugin" / "marketplace.json", findings)

    if module_yaml:
        _validate_module_yaml(module_yaml, findings)
    if module_help:
        _validate_module_help(module_help, findings)
    if marketplace:
        _validate_marketplace(root, marketplace, findings)
    if module_yaml and module_help and marketplace:
        _validate_cross_manifest_consistency(module_yaml, module_help, marketplace, findings)

    status = "pass" if not findings else "fail"
    report_path = root / ".claude-plugin" / "module-validation.json"
    report = {
        "gate": "validate-module",
        "status": status,
        "approved_for_distribution": not findings,
        "findings": [finding.__dict__ for finding in findings],
    }
    _atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return ModuleGateResult(
        status=status,
        approved_for_distribution=not findings,
        findings=tuple(findings),
        report_path=report_path,
    )


def _module_yaml_text() -> str:
    payload = {
        "module_id": "nextlens-src",
        "module_name": "NextLens Top-Down Bridge",
        "module_version": "1.0.0",
        "description": "Deterministic top-down feature packet bridge with doctor validation and salmon correction routing.",
        "author": "NextLens Team",
        "license": "MIT",
        "code": "nxl",
        "name": "NextLens Top-Down Bridge",
        "default_selected": False,
        "module_greeting": "NextLens is ready. Use the module action surface to create a feature packet, run doctor validation, or route salmon findings.",
        "capabilities": [
            {
                "command": capability["command"],
                "description": capability["description"],
                "entry_point": MODULE_SKILL_PATH,
                "skill_type": "command",
            }
            for capability in CAPABILITIES
        ],
        "configuration": [
            {
                "name": "NEXTLENS_DOCS_PATH",
                "type": "string",
                "required": True,
                "source": "feature.yaml",
                "description": "Feature docs path resolved from feature.yaml.",
            },
            {
                "name": "NEXTLENS_LANDSCAPE_STORE",
                "type": "string",
                "required": False,
                "default": "{docs_path}/landscape",
                "description": "Landscape state directory for reconstructed top-down context.",
            },
            {
                "name": "NEXTLENS_IDEMPOTENCY_TTL_HOURS",
                "type": "number",
                "required": False,
                "default": 24,
                "description": "Retention window for active idempotency tokens.",
            },
        ],
        "dependencies": ["feature-yaml-resolver", "bmad-constitution-resolver"],
    }
    return _yaml_dump(payload)


def _module_help_text() -> str:
    lines = ["command,category,description,entry_point,trigger_keywords"]
    for capability in CAPABILITIES:
        row = [
            capability["command"],
            "command",
            capability["description"],
            capability["entry_point"],
            capability["keywords"],
        ]
        lines.append(_csv_line(row))
    return "\n".join(lines) + "\n"


def _marketplace_json_text() -> str:
    payload = {
        "name": "NextLens Top-Down Bridge",
        "version": "1.0.0",
        "description": "Deterministic v1 top-down Feature packet bridge with validation and correction routing",
        "author": "NextLens Team",
        "repository": "https://github.com/crisweber2600/NextLens",
        "plugins": [
            {
                "id": capability["command"],
                "name": capability["name"],
                "description": capability["description"],
                "skills": [MODULE_SKILL_PATH],
            }
            for capability in CAPABILITIES
        ],
        "keywords": [
            "nextlens",
            "top-down",
            "feature-packet",
            "bmad-module",
            "doctor-validation",
            "salmon-routing",
        ],
        "license": "MIT",
    }
    return json.dumps(payload, indent=2) + "\n"


def _validate_module_yaml(payload: Mapping[str, Any], findings: list[ModuleGateFinding]) -> None:
    required = ("module_id", "module_name", "module_version", "description", "author", "license", "capabilities")
    for field_name in required:
        if field_name not in payload:
            findings.append(_finding("module-yaml-missing-field", f"module.yaml missing {field_name}.", "Regenerate module.yaml with create-module."))
    version = str(payload.get("module_version") or "")
    if not MODULE_VERSION_PATTERN.match(version):
        findings.append(_finding("module-yaml-semver", "module_version must use major.minor.patch semantic versioning.", "Set module_version to a value such as 1.0.0."))


def _validate_module_help(rows: Sequence[Mapping[str, str]], findings: list[ModuleGateFinding]) -> None:
    commands = [row.get("command", "") for row in rows]
    expected = [capability["command"] for capability in CAPABILITIES]
    if commands != expected:
        findings.append(_finding("module-help-command-set", "module-help.csv commands do not match current capabilities.", "Regenerate module-help.csv with create-module."))
    for row in rows:
        if set(row) != {"command", "category", "description", "entry_point", "trigger_keywords"}:
            findings.append(_finding("module-help-header", "module-help.csv has unexpected columns.", "Use the command,category,description,entry_point,trigger_keywords header."))


def _validate_marketplace(root: Path, payload: Mapping[str, Any], findings: list[ModuleGateFinding]) -> None:
    for field_name in ("name", "version", "description", "author", "repository", "plugins", "keywords", "license"):
        if field_name not in payload:
            findings.append(_finding("marketplace-missing-field", f"marketplace.json missing {field_name}.", "Regenerate marketplace.json with create-module."))
    version = str(payload.get("version") or "")
    if not MODULE_VERSION_PATTERN.match(version):
        findings.append(_finding("marketplace-semver", "marketplace version must use major.minor.patch semantic versioning.", "Set marketplace version to a value such as 1.0.0."))
    for plugin in _mapping_sequence(payload.get("plugins")):
        for skill in _string_sequence(plugin.get("skills")):
            if Path(skill).is_absolute() or ".." in Path(skill).parts:
                findings.append(_finding("marketplace-skill-path", f"Skill path {skill} must be repository-relative.", "Use a relative path inside the repository."))
            elif not (root / skill).is_file():
                findings.append(_finding("marketplace-skill-missing", f"Referenced skill file does not exist: {skill}.", "Create the skill file or update marketplace.json to point at an existing skill."))


def _validate_cross_manifest_consistency(
    module_yaml: Mapping[str, Any],
    module_help: Sequence[Mapping[str, str]],
    marketplace: Mapping[str, Any],
    findings: list[ModuleGateFinding],
) -> None:
    yaml_commands = {str(item.get("command")) for item in _mapping_sequence(module_yaml.get("capabilities"))}
    help_commands = {row.get("command", "") for row in module_help}
    marketplace_commands = {str(item.get("id")) for item in _mapping_sequence(marketplace.get("plugins"))}
    if yaml_commands != help_commands or yaml_commands != marketplace_commands:
        findings.append(_finding("manifest-command-consistency", "module.yaml, module-help.csv, and marketplace.json command sets differ.", "Regenerate all module surfaces with create-module."))


def _skill_reference_findings(root: Path) -> tuple[ModuleGateFinding, ...]:
    if (root / MODULE_SKILL_PATH).is_file():
        return ()
    return (_finding("skill-reference-missing", f"Required skill file does not exist: {MODULE_SKILL_PATH}.", "Create the skill file before running create-module."),)


def _load_yaml(path: Path, findings: list[ModuleGateFinding]) -> Mapping[str, Any]:
    try:
        yaml_module = _require_yaml()
        value = yaml_module.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        findings.append(_finding("module-yaml-parse", f"Cannot parse module.yaml: {exc}", "Fix YAML syntax or regenerate module.yaml."))
        return {}
    return value if isinstance(value, Mapping) else {}


def _load_module_help(path: Path, findings: list[ModuleGateFinding]) -> list[Mapping[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except Exception as exc:
        findings.append(_finding("module-help-parse", f"Cannot parse module-help.csv: {exc}", "Fix CSV syntax or regenerate module-help.csv."))
        return []


def _load_json(path: Path, findings: list[ModuleGateFinding]) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        findings.append(_finding("marketplace-parse", f"Cannot parse marketplace.json: {exc}", "Fix JSON syntax or regenerate marketplace.json."))
        return {}
    return value if isinstance(value, Mapping) else {}


def _finding(check_id: str, message: str, remediation: str) -> ModuleGateFinding:
    return ModuleGateFinding(check_id=check_id, status="fail", message=message, remediation=remediation)


def _yaml_dump(payload: Mapping[str, Any]) -> str:
    yaml_module = _require_yaml()
    return yaml_module.safe_dump(dict(payload), sort_keys=False)


def _csv_line(values: Sequence[str]) -> str:
    import io

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="")
    writer.writerow(values)
    return output.getvalue()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f"{path.stem}-", suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(str(temp_path), str(path))
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _require_yaml():
    if yaml is None:
        raise RuntimeError("PyYAML is required for module gates.") from _YAML_IMPORT_ERROR
    return yaml


def _utc_timestamp(now_factory: Callable[[], datetime] | None) -> str:
    now = now_factory() if now_factory else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _mapping_sequence(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_sequence(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run NextLens Create Module and Validate Module gates.")
    parser.add_argument("gate", choices=("cm", "vm", "create-module", "validate-module"))
    parser.add_argument("--repo-root", default=Path.cwd())
    args = parser.parse_args(argv)
    if args.gate in {"cm", "create-module"}:
        result = create_module_package(args.repo_root)
    else:
        result = validate_module_package(args.repo_root)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.status == "pass" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))