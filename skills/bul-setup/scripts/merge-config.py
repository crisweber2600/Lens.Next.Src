#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Merge Bottom-Up LENS module configuration into shared BMad config files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - environment dependency guard
    print("Error: pyyaml is required", file=sys.stderr)
    sys.exit(2)

CORE_USER_KEYS = {"user_name", "communication_language"}
CORE_KEYS = CORE_USER_KEYS | {"document_output_language", "output_folder"}
METADATA_KEYS = {"code", "name", "description", "module_version", "default_selected", "module_greeting"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge Bottom-Up LENS config into _bmad/config.yaml.")
    parser.add_argument("--config-path", required=True)
    parser.add_argument("--user-config-path", required=True)
    parser.add_argument("--module-yaml", required=True)
    parser.add_argument("--answers", required=True)
    parser.add_argument("--legacy-dir")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def load_yaml(path: str) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with file_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_json(path: str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def variable_keys(module_yaml: dict[str, Any]) -> set[str]:
    return {key for key, value in module_yaml.items() if isinstance(value, dict) and key not in METADATA_KEYS}


def load_legacy_values(legacy_dir: str | None, module_code: str, module_yaml: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    if not legacy_dir:
        return {}, {}, []

    legacy_root = Path(legacy_dir)
    legacy_core: dict[str, Any] = {}
    legacy_module: dict[str, Any] = {}
    files_found: list[str] = []
    module_keys = variable_keys(module_yaml)

    for path in (legacy_root / "core" / "config.yaml", legacy_root / module_code / "config.yaml"):
        if not path.exists():
            continue
        data = load_yaml(str(path))
        files_found.append(str(path))
        for key, value in data.items():
            if key in CORE_KEYS and key not in legacy_core:
                legacy_core[key] = value
            elif key in module_keys:
                legacy_module[key] = value

    return legacy_core, legacy_module, files_found


def apply_legacy_defaults(answers: dict[str, Any], legacy_core: dict[str, Any], legacy_module: dict[str, Any]) -> dict[str, Any]:
    merged = dict(answers)
    if legacy_core:
        core = dict(legacy_core)
        core.update(merged.get("core", {}))
        merged["core"] = core
    if legacy_module:
        module = dict(legacy_module)
        module.update(merged.get("module", {}))
        merged["module"] = module
    return merged


def module_metadata(module_yaml: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if "name" in module_yaml:
        metadata["name"] = module_yaml["name"]
    if "description" in module_yaml:
        metadata["description"] = module_yaml["description"]
    if "module_version" in module_yaml:
        metadata["version"] = module_yaml["module_version"]
    if "default_selected" in module_yaml:
        metadata["default_selected"] = module_yaml["default_selected"]
    return metadata


def defaults_from_module_yaml(module_yaml: dict[str, Any]) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for key, value in module_yaml.items():
        if isinstance(value, dict) and "default" in value:
            defaults[key] = value["default"]
    return defaults


def apply_result_templates(module_yaml: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    transformed: dict[str, Any] = {}
    for key, value in values.items():
        definition = module_yaml.get(key)
        if isinstance(definition, dict) and "result" in definition and "{project-root}" not in str(value):
            transformed[key] = str(definition["result"]).replace("{value}", str(value))
        else:
            transformed[key] = value
    return transformed


def merge_config(existing: dict[str, Any], module_yaml: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    module_code = module_yaml.get("code")
    if not module_code:
        raise ValueError("module.yaml must define code")

    config = dict(existing)
    if isinstance(config.get("core"), dict):
        config.update(config.pop("core"))

    for key in CORE_USER_KEYS:
        config.pop(key, None)

    core_answers = answers.get("core", {})
    config.update({key: value for key, value in core_answers.items() if key not in CORE_USER_KEYS})

    config.pop(module_code, None)
    module_section = module_metadata(module_yaml)
    module_values = defaults_from_module_yaml(module_yaml)
    module_values.update(answers.get("module", {}))
    module_section.update(apply_result_templates(module_yaml, module_values))
    config[module_code] = module_section
    return config


def extract_user_settings(module_yaml: dict[str, Any], answers: dict[str, Any]) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    for key in CORE_USER_KEYS:
        if key in answers.get("core", {}):
            settings[key] = answers["core"][key]

    for key, definition in module_yaml.items():
        if isinstance(definition, dict) and definition.get("user_setting") is True and key in answers.get("module", {}):
            settings[key] = answers["module"][key]
    return settings


def cleanup_legacy_configs(legacy_dir: str | None, module_code: str) -> list[str]:
    if not legacy_dir:
        return []
    deleted: list[str] = []
    for subdir in (module_code, "core"):
        path = Path(legacy_dir) / subdir / "config.yaml"
        if path.exists():
            path.unlink()
            deleted.append(str(path))
    return deleted


def write_yaml(path: str, data: dict[str, Any]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def main() -> int:
    args = parse_args()
    module_yaml = load_yaml(args.module_yaml)
    answers = load_json(args.answers)
    module_code = module_yaml.get("code", "")

    legacy_core, legacy_module, legacy_found = load_legacy_values(args.legacy_dir, module_code, module_yaml)
    answers = apply_legacy_defaults(answers, legacy_core, legacy_module)

    updated_config = merge_config(load_yaml(args.config_path), module_yaml, answers)
    write_yaml(args.config_path, updated_config)

    user_settings = extract_user_settings(module_yaml, answers)
    user_config = load_yaml(args.user_config_path)
    user_config.update(user_settings)
    if user_settings:
        write_yaml(args.user_config_path, user_config)

    legacy_deleted = cleanup_legacy_configs(args.legacy_dir, module_code)
    print(json.dumps({
        "status": "success",
        "config_path": str(Path(args.config_path).resolve()),
        "user_config_path": str(Path(args.user_config_path).resolve()),
        "module_code": module_code,
        "module_keys": list(updated_config.get(module_code, {}).keys()),
        "user_keys": list(user_settings.keys()),
        "legacy_configs_found": legacy_found,
        "legacy_configs_deleted": legacy_deleted,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI safety
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
