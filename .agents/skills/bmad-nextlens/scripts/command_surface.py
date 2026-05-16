"""Normalize the NextLens BMAD module action surface.

The planning stories describe textual commands such as `nextlens new --context ...`.
NextLens itself is being built as a BMAD module, not a standalone CLI application,
so this helper keeps the story examples executable in tests while normalizing the
module's real action surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from shlex import split as shlex_split
from typing import Mapping, Sequence


ACTION_DEFINITIONS = {
    "new": {
        "required_keys": ("context_source",),
        "flag": "--context",
    },
    "doctor": {
        "required_keys": ("packet_source",),
        "flag": "--packet",
    },
    "salmon": {
        "required_keys": ("findings_source",),
        "flag": "--findings",
    },
    "validate": {
        "required_keys": ("packet_source", "implementation_evidence_source"),
        "flag": "--packet and --implementation-evidence",
    },
}

ACTION_OPTION_ALIASES = {
    "new": {
        "context": "context_source",
        "context_source": "context_source",
        "context-source": "context_source",
    },
    "doctor": {
        "packet": "packet_source",
        "packet_source": "packet_source",
        "packet-source": "packet_source",
    },
    "salmon": {
        "findings": "findings_source",
        "findings_source": "findings_source",
        "findings-source": "findings_source",
    },
    "validate": {
        "packet": "packet_source",
        "packet_source": "packet_source",
        "packet-source": "packet_source",
        "bmad_artifacts": "bmad_artifacts_source",
        "bmad-artifacts": "bmad_artifacts_source",
        "bmad_artifact_bundle": "bmad_artifacts_source",
        "bmad-artifact-bundle": "bmad_artifacts_source",
        "implementation_evidence": "implementation_evidence_source",
        "implementation-evidence": "implementation_evidence_source",
        "implementation_evidence_source": "implementation_evidence_source",
        "implementation-evidence-source": "implementation_evidence_source",
        "landscape_update_source": "landscape_update_source",
        "landscape-update-source": "landscape_update_source",
        "landscape_updates": "landscape_update_source",
        "landscape-updates": "landscape_update_source",
        "landscape_update_mode": "landscape_update_mode",
        "landscape-update-mode": "landscape_update_mode",
    },
}

COMMON_OPTION_ALIASES = {
    "docs_path": "docs_path",
    "docs-path": "docs_path",
}

HELP_ALIASES = {"help", "-h", "--help"}
SETUP_ALIASES = {"setup", "configure"}


@dataclass(frozen=True)
class ParsedAction:
    action: str
    context_source: str | None = None
    packet_source: str | None = None
    findings_source: str | None = None
    bmad_artifacts_source: str | None = None
    implementation_evidence_source: str | None = None
    landscape_update_source: str | None = None
    landscape_update_mode: str | None = None
    overrides: dict[str, str] = field(default_factory=dict)

    @property
    def mode(self) -> str:
        return self.action


class CommandSurfaceError(ValueError):
    def __init__(self, message: str):
        super().__init__(message)
        self.help_text = build_help_text()


def build_help_text() -> str:
    lines = [
        "NextLens BMAD module actions:",
        "  setup | configure",
        "  new --context <path> [--docs-path <path>]",
        "  doctor --packet <path> [--docs-path <path>]",
        "  salmon --findings <path> [--docs-path <path>]",
        "  validate --packet <path> --implementation-evidence <path> [--bmad-artifacts <path>] [--docs-path <path>] [--landscape-update-source <path>] [--landscape-update-mode propose|apply]",
        "  help | --help",
        "",
        "Validate runs governed post-BMAD validation for implementation evidence; it is not Doctor.",
        "Landscape updates are proposal-only by default; apply mode must be requested explicitly.",
        "",
        "Story-compatible textual examples:",
        "  nextlens setup",
        "  nextlens new --context path/to/context.yaml",
        "  nextlens doctor --packet path/to/packet.json",
        "  nextlens salmon --findings path/to/findings.jsonl",
        "  nextlens validate --packet path/to/packet.json --implementation-evidence path/to/evidence.json --bmad-artifacts path/to/bmad-bundle.json",
        "  nextlens help",
    ]
    return "\n".join(lines)


def _normalize_mapping_keys(action: str, options: Mapping[str, object]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    action_aliases = ACTION_OPTION_ALIASES.get(action, {})

    for raw_key, raw_value in options.items():
        key = str(raw_key).strip().replace(" ", "_").lower()
        value = str(raw_value).strip()

        if not value:
            raise CommandSurfaceError(f"Argument '{raw_key}' requires a non-empty value.")

        if key in COMMON_OPTION_ALIASES:
            mapped_key = COMMON_OPTION_ALIASES[key]
        elif key in action_aliases:
            mapped_key = action_aliases[key]
        else:
            raise CommandSurfaceError(
                f"Unknown argument '{raw_key}' for action '{action}'.\n{build_help_text()}"
            )

        if mapped_key in normalized:
            raise CommandSurfaceError(
                f"Argument '{raw_key}' was provided more than once for action '{action}'."
            )
        normalized[mapped_key] = value

    return normalized


def parse_module_action(action: str, options: Mapping[str, object] | None = None) -> ParsedAction:
    normalized_action = str(action or "").strip().lower()
    if normalized_action in HELP_ALIASES:
        return ParsedAction(action="help")
    if normalized_action in SETUP_ALIASES:
        return ParsedAction(action="setup")

    if normalized_action not in ACTION_DEFINITIONS:
        raise CommandSurfaceError(
            f"Unknown NextLens action '{action}'.\n{build_help_text()}"
        )

    normalized_options = _normalize_mapping_keys(normalized_action, options or {})
    required_keys = ACTION_DEFINITIONS[normalized_action]["required_keys"]
    missing_keys = [key for key in required_keys if key not in normalized_options]
    if missing_keys:
        missing = ", ".join(f"'{key}'" for key in missing_keys)
        raise CommandSurfaceError(
            f"Missing required argument {missing} for action '{normalized_action}'. "
            f"Use {ACTION_DEFINITIONS[normalized_action]['flag']} to provide it.\n{build_help_text()}"
        )

    return ParsedAction(
        action=normalized_action,
        context_source=normalized_options.get("context_source"),
        packet_source=normalized_options.get("packet_source"),
        findings_source=normalized_options.get("findings_source"),
        bmad_artifacts_source=normalized_options.get("bmad_artifacts_source"),
        implementation_evidence_source=normalized_options.get("implementation_evidence_source"),
        landscape_update_source=normalized_options.get("landscape_update_source"),
        landscape_update_mode=normalized_options.get("landscape_update_mode"),
        overrides={
            key: value
            for key, value in normalized_options.items()
            if key in COMMON_OPTION_ALIASES.values()
        },
    )


def parse_story_command(command: str | Sequence[str]) -> ParsedAction:
    if isinstance(command, str):
        tokens = shlex_split(command)
    else:
        tokens = [str(token) for token in command]

    if not tokens:
        raise CommandSurfaceError(f"No command was provided.\n{build_help_text()}")

    if tokens[0].lower() == "nextlens":
        tokens = tokens[1:]

    if not tokens:
        raise CommandSurfaceError(f"No action was provided.\n{build_help_text()}")

    action = tokens[0].lower()
    if action in HELP_ALIASES:
        return ParsedAction(action="help")
    if action in SETUP_ALIASES:
        return ParsedAction(action="setup")

    if action not in ACTION_DEFINITIONS:
        raise CommandSurfaceError(
            f"Unknown NextLens action '{action}'.\n{build_help_text()}"
        )

    parsed_options: dict[str, str] = {}
    option_tokens = tokens[1:]
    index = 0
    while index < len(option_tokens):
        token = option_tokens[index]
        if token in HELP_ALIASES:
            return ParsedAction(action="help")
        if not token.startswith("--"):
            raise CommandSurfaceError(
                f"Unexpected positional token '{token}' for action '{action}'.\n{build_help_text()}"
            )
        if index + 1 >= len(option_tokens):
            raise CommandSurfaceError(
                f"Option '{token}' requires a value.\n{build_help_text()}"
            )
        parsed_options[token[2:]] = option_tokens[index + 1]
        index += 2

    return parse_module_action(action, parsed_options)