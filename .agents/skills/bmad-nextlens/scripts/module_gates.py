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
SETUP_SKILL = "bmad-nextlens-setup"
SETUP_ASSETS_DIR = Path(".agents") / "skills" / SETUP_SKILL / "assets"
CONFIG_DISCOVERY_MODULE_YAML = Path("skills") / "module.yaml"
EXPECTED_MARKETPLACE_PLUGIN_COUNT = 1
SHARED_RUNTIME_SKILLS = (
    {
        "skill_dir": ".agents/skills/bmad-nextlens",
        "skill_path": ".agents/skills/bmad-nextlens/SKILL.md",
    },
)

CAPABILITIES = (
    {
        "command": "nextlens-setup",
        "action": "configure",
        "skill": "bmad-nextlens-setup",
        "skill_dir": ".agents/skills/bmad-nextlens-setup",
        "skill_path": ".agents/skills/bmad-nextlens-setup/SKILL.md",
        "display_name": "Setup NextLens",
        "menu_code": "SN",
        "name": "NextLens Setup",
        "description": "Register or refresh the NextLens BMad module in this project.",
        "args": "{-H: headless mode}|{setup|configure}",
        "phase": "anytime",
        "after": "",
        "before": "bmad-nextlens-new:new",
        "required": "true",
        "output_location": "{project-root}/_bmad",
        "outputs": "config.yaml and module-help.csv",
    },
    {
        "command": "nextlens-new",
        "action": "new",
        "skill": "bmad-nextlens-new",
        "skill_dir": ".agents/skills/bmad-nextlens-new",
        "skill_path": ".agents/skills/bmad-nextlens-new/SKILL.md",
        "display_name": "Create Feature Packet",
        "menu_code": "NF",
        "name": "Create Feature Packet",
        "description": "Break discovery context into candidate Feature slices before creating one packet.",
        "args": "{context_source: discovery context path}|{docs_path: optional docs root}",
        "phase": "anytime",
        "after": "bmad-nextlens-setup:configure",
        "before": "bmad-nextlens-doctor:doctor",
        "required": "false",
        "output_location": "nextlens_docs_path",
        "outputs": "feature packet JSON",
    },
    {
        "command": "nextlens-doctor",
        "action": "doctor",
        "skill": "bmad-nextlens-doctor",
        "skill_dir": ".agents/skills/bmad-nextlens-doctor",
        "skill_path": ".agents/skills/bmad-nextlens-doctor/SKILL.md",
        "display_name": "Run Doctor Checks",
        "menu_code": "ND",
        "name": "NextLens Doctor",
        "description": "Run non-mutating validation checks on a Feature packet or landscape.",
        "args": "{packet_source: packet path}|{docs_path: optional docs root}",
        "phase": "anytime",
        "after": "bmad-nextlens-new:new",
        "before": "bmad-nextlens-salmon:salmon",
        "required": "false",
        "output_location": "nextlens_docs_path",
        "outputs": "doctor validation report",
    },
    {
        "command": "nextlens-salmon",
        "action": "salmon",
        "skill": "bmad-nextlens-salmon",
        "skill_dir": ".agents/skills/bmad-nextlens-salmon",
        "skill_path": ".agents/skills/bmad-nextlens-salmon/SKILL.md",
        "display_name": "Route Salmon Findings",
        "menu_code": "NS",
        "name": "NextLens Salmon",
        "description": "Route correction findings through deduplication and impact classification.",
        "args": "{findings_source: findings path}|{docs_path: optional docs root}",
        "phase": "anytime",
        "after": "bmad-nextlens-doctor:doctor",
        "before": "",
        "required": "false",
        "output_location": "nextlens_landscape_store",
        "outputs": "salmon routing report",
    },
)

BMAD_HELP_HEADER = (
    "module",
    "skill",
    "display-name",
    "menu-code",
    "description",
    "action",
    "args",
    "phase",
    "after",
    "before",
    "required",
    "output-location",
    "outputs",
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
    module_yaml_text = _module_yaml_text()
    files = {
        root / SETUP_ASSETS_DIR / "module.yaml": module_yaml_text,
        root / CONFIG_DISCOVERY_MODULE_YAML: module_yaml_text,
        root / SETUP_ASSETS_DIR / "module-help.csv": _module_help_text(),
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
    module_yaml = _load_yaml(root / SETUP_ASSETS_DIR / "module.yaml", findings)
    config_discovery_module_yaml = _load_yaml(root / CONFIG_DISCOVERY_MODULE_YAML, findings)
    module_help = _load_module_help(root / SETUP_ASSETS_DIR / "module-help.csv", findings)
    marketplace = _load_json(root / ".claude-plugin" / "marketplace.json", findings)

    if module_yaml:
        _validate_module_yaml(module_yaml, findings)
    if config_discovery_module_yaml and module_yaml and config_discovery_module_yaml != module_yaml:
        findings.append(_finding("config-discovery-module-yaml", "skills/module.yaml must mirror the setup skill module.yaml.", "Regenerate module surfaces with create-module."))
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
        "code": "nxl",
        "name": "NextLens Top-Down Bridge",
        "module_version": "1.0.0",
        "description": "Deterministic top-down feature packet bridge with doctor validation and salmon correction routing.",
        "default_selected": False,
        "module_greeting": "NextLens is ready. Run setup once, then use the New, Doctor, and Salmon skills as separate parts of the top-down bridge.",
        "capabilities": [
            {
                "command": capability["command"],
                "action": capability["action"],
                "skill": capability["skill"],
                "description": capability["description"],
                "entry_point": capability["skill_path"],
                "skill_type": "workflow",
            }
            for capability in CAPABILITIES
        ],
        "nextlens_docs_path": {
            "prompt": "Where should NextLens read and write Feature packet documentation?",
            "default": "{project-root}/docs",
        },
        "nextlens_landscape_store": {
            "prompt": "Where should NextLens keep reconstructed landscape state?",
            "default": "{project-root}/docs/landscape",
        },
        "nextlens_idempotency_ttl_hours": {
            "prompt": "How many hours should active idempotency tokens be retained?",
            "default": 24,
            "type": "number",
        },
        "directories": ["{nextlens_docs_path}", "{nextlens_landscape_store}"],
        "post-install-notes": "Use NextLens setup, new, doctor, and salmon actions from BMAD help after setup completes.",
    }
    return _yaml_dump(payload)


def _module_help_text() -> str:
    lines = [_csv_line(BMAD_HELP_HEADER)]
    for capability in CAPABILITIES:
        row = [
            "NextLens Top-Down Bridge",
            capability["skill"],
            capability["display_name"],
            capability["menu_code"],
            capability["description"],
            capability["action"],
            capability["args"],
            capability["phase"],
            capability["after"],
            capability["before"],
            capability["required"],
            capability["output_location"],
            capability["outputs"],
        ]
        lines.append(_csv_line(row))
    return "\n".join(lines) + "\n"


def _marketplace_json_text() -> str:
    payload = {
        "name": "NextLens Top-Down Bridge",
        "owner": {"name": "NextLens Team"},
        "license": "MIT",
        "homepage": "https://github.com/crisweber2600/NextLens",
        "repository": "https://github.com/crisweber2600/NextLens",
        "keywords": [
            "nextlens",
            "top-down",
            "feature-packet",
            "bmad-module",
            "doctor-validation",
            "salmon-routing",
        ],
        "plugins": [
            {
                "name": "nxl",
                "source": "./",
                "description": "Deterministic top-down feature packet bridge with doctor validation and salmon correction routing.",
                "version": "1.0.0",
                "author": {"name": "NextLens Team"},
                "skills": _marketplace_plugin_skills(),
            }
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def _marketplace_plugin_skills() -> list[str]:
    setup_skill_dir = ".agents/skills/bmad-nextlens-setup"
    skills = [setup_skill_dir]
    for shared_skill in SHARED_RUNTIME_SKILLS:
        skill_dir = str(shared_skill["skill_dir"]).strip()
        if skill_dir and skill_dir not in skills:
            skills.append(skill_dir)
    for capability in CAPABILITIES:
        skill_dir = str(capability.get("skill_dir", "")).strip()
        if skill_dir and skill_dir not in skills:
            skills.append(skill_dir)
    return skills


def _validate_module_yaml(payload: Mapping[str, Any], findings: list[ModuleGateFinding]) -> None:
    required = ("code", "name", "module_version", "description", "capabilities")
    for field_name in required:
        if field_name not in payload:
            findings.append(_finding("module-yaml-missing-field", f"module.yaml missing {field_name}.", "Regenerate module.yaml with create-module."))
    version = str(payload.get("module_version") or "")
    if not MODULE_VERSION_PATTERN.match(version):
        findings.append(_finding("module-yaml-semver", "module_version must use major.minor.patch semantic versioning.", "Set module_version to a value such as 1.0.0."))
    actions = [str(item.get("action")) for item in _mapping_sequence(payload.get("capabilities"))]
    expected_actions = [capability["action"] for capability in CAPABILITIES]
    if actions != expected_actions:
        findings.append(_finding("module-yaml-action-set", "module.yaml actions do not match current capabilities.", "Regenerate module.yaml with create-module."))
    skills = [str(item.get("skill")) for item in _mapping_sequence(payload.get("capabilities"))]
    expected_skills = [capability["skill"] for capability in CAPABILITIES]
    if skills != expected_skills:
        findings.append(_finding("module-yaml-skill-set", "module.yaml skills do not match the split NextLens skill set.", "Regenerate module.yaml with create-module."))
    entry_points = [str(item.get("entry_point")) for item in _mapping_sequence(payload.get("capabilities"))]
    expected_entry_points = [capability["skill_path"] for capability in CAPABILITIES]
    if entry_points != expected_entry_points:
        findings.append(_finding("module-yaml-entry-points", "module.yaml entry points do not match the split NextLens skill files.", "Regenerate module.yaml with create-module."))
    for variable in ("nextlens_docs_path", "nextlens_landscape_store", "nextlens_idempotency_ttl_hours"):
        if variable not in payload:
            findings.append(_finding("module-yaml-missing-config", f"module.yaml missing {variable} configuration.", "Regenerate module.yaml with create-module."))


def _validate_module_help(rows: Sequence[Mapping[str, str]], findings: list[ModuleGateFinding]) -> None:
    actions = [row.get("action", "") for row in rows]
    expected = [capability["action"] for capability in CAPABILITIES]
    if actions != expected:
        findings.append(_finding("module-help-action-set", "module-help.csv actions do not match current capabilities.", "Regenerate module-help.csv with create-module."))
    for row in rows:
        if tuple(row.keys()) != BMAD_HELP_HEADER:
            findings.append(_finding("module-help-header", "module-help.csv has unexpected columns.", "Use the BMad module-help.csv header."))


def _validate_marketplace(root: Path, payload: Mapping[str, Any], findings: list[ModuleGateFinding]) -> None:
    for field_name in ("name", "owner", "license", "homepage", "repository", "keywords", "plugins"):
        if field_name not in payload:
            findings.append(_finding("marketplace-missing-field", f"marketplace.json missing {field_name}.", "Regenerate marketplace.json with create-module."))
    owner = payload.get("owner")
    if not isinstance(owner, Mapping) or not str(owner.get("name") or "").strip():
        findings.append(_finding("marketplace-owner", "marketplace.json owner must include a non-empty name.", "Set owner.name in marketplace.json."))
    plugins = _mapping_sequence(payload.get("plugins"))
    if len(plugins) != EXPECTED_MARKETPLACE_PLUGIN_COUNT:
        findings.append(_finding("marketplace-plugin-count", "marketplace.json must expose one installable plugin for the multi-skill NextLens module.", "Regenerate marketplace.json with create-module."))
    for plugin in plugins:
        for field_name in ("name", "source", "description", "version", "author", "skills"):
            if field_name not in plugin:
                findings.append(_finding(f"marketplace-plugin-missing-{field_name}", f"marketplace plugin missing {field_name}.", "Regenerate marketplace.json with create-module."))
        version = str(plugin.get("version") or "")
        if not MODULE_VERSION_PATTERN.match(version):
            findings.append(_finding("marketplace-semver", "marketplace plugin version must use major.minor.patch semantic versioning.", "Set plugin version to a value such as 1.0.0."))
        author = plugin.get("author")
        if not isinstance(author, Mapping) or not str(author.get("name") or "").strip():
            findings.append(_finding("marketplace-author", "marketplace plugin author must include a non-empty name.", "Set plugin author.name in marketplace.json."))
        source = str(plugin.get("source") or "")
        if source != "./":
            findings.append(_finding("marketplace-source", "marketplace plugin source must point at the repository root.", "Set plugin source to './'."))
        for skill in _string_sequence(plugin.get("skills")):
            skill_path = Path(skill)
            resolved_skill_dir = root / skill_path
            if skill_path.is_absolute() or ".." in skill_path.parts:
                findings.append(_finding("marketplace-skill-path", f"Skill path {skill} must be repository-relative.", "Use a relative path inside the repository."))
            elif not resolved_skill_dir.is_dir():
                findings.append(_finding("marketplace-skill-missing", f"Referenced skill directory does not exist: {skill}.", "Create the skill directory or update marketplace.json to point at an existing skill directory."))
            elif not (resolved_skill_dir / "SKILL.md").is_file():
                findings.append(_finding("marketplace-skill-missing", f"Referenced skill directory does not contain SKILL.md: {skill}.", "Create the skill file or update marketplace.json to point at an existing skill directory."))


def _validate_cross_manifest_consistency(
    module_yaml: Mapping[str, Any],
    module_help: Sequence[Mapping[str, str]],
    marketplace: Mapping[str, Any],
    findings: list[ModuleGateFinding],
) -> None:
    yaml_commands = {str(item.get("command")) for item in _mapping_sequence(module_yaml.get("capabilities"))}
    expected_commands = {capability["command"] for capability in CAPABILITIES}
    yaml_actions = {str(item.get("action")) for item in _mapping_sequence(module_yaml.get("capabilities"))}
    help_actions = {row.get("action", "") for row in module_help}
    expected_actions = {capability["action"] for capability in CAPABILITIES}
    yaml_skills = {str(item.get("skill")) for item in _mapping_sequence(module_yaml.get("capabilities"))}
    help_skills = {row.get("skill", "") for row in module_help}
    marketplace_plugins = _mapping_sequence(marketplace.get("plugins"))
    marketplace_skill_dirs = {
        skill
        for plugin in marketplace_plugins
        for skill in _string_sequence(plugin.get("skills"))
    }
    expected_skills = {capability["skill"] for capability in CAPABILITIES}
    expected_skill_dirs = {capability["skill_dir"] for capability in CAPABILITIES}
    expected_skill_dirs.update(shared_skill["skill_dir"] for shared_skill in SHARED_RUNTIME_SKILLS)
    marketplace_plugin_names = {str(plugin.get("name")) for plugin in marketplace_plugins}
    if (
        yaml_commands != expected_commands
        or yaml_actions != expected_actions
        or help_actions != expected_actions
        or yaml_skills != expected_skills
        or help_skills != expected_skills
        or marketplace_skill_dirs != expected_skill_dirs
        or marketplace_plugin_names != {"nxl"}
    ):
        findings.append(_finding("manifest-command-consistency", "module.yaml, module-help.csv, and marketplace.json capability sets differ.", "Regenerate all module surfaces with create-module."))


def _skill_reference_findings(root: Path) -> tuple[ModuleGateFinding, ...]:
    findings = []
    for shared_skill in SHARED_RUNTIME_SKILLS:
        skill_path = shared_skill["skill_path"]
        if not (root / skill_path).is_file():
            findings.append(_finding("skill-reference-missing", f"Required shared skill file does not exist: {skill_path}.", "Create the shared runtime skill file before running create-module."))
    for capability in CAPABILITIES:
        skill_path = capability["skill_path"]
        if not (root / skill_path).is_file():
            findings.append(_finding("skill-reference-missing", f"Required skill file does not exist: {skill_path}.", "Create the split skill file before running create-module."))
    return tuple(findings)


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
