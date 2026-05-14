---
name: bmad-nextlens
description: Creates a NextLens feature packet, runs doctor validation, or routes salmon corrections through the NextLens BMAD module surface.
---

# BMad NextLens

## Purpose

Provide the BMAD module entry surface for NextLens top-down packet work. This skill accepts four actions: `new`, `doctor`, `salmon`, and `help`.

## On Activation

- Treat this skill as a BMAD module surface, not a standalone CLI application.
- Normalize the requested action and arguments with `./scripts/command_surface.py` before deeper workflow logic runs.
- `help` returns the supported action list and compatibility examples.
- `new` requires `context_source` and optionally accepts `docs_path`.
- `doctor` requires `packet_source` and optionally accepts `docs_path`.
- `salmon` requires `findings_source` and optionally accepts `docs_path`.

## Action Contracts

### `new`

Create one Feature packet from top-down discovery context.

Required args:
- `context_source`

Optional args:
- `docs_path`

### `doctor`

Run non-mutating validation checks on an emitted packet or on derived landscape state.

Required args:
- `packet_source`

Optional args:
- `docs_path`

### `salmon`

Route correction findings through deduplication and impact classification.

Required args:
- `findings_source`

Optional args:
- `docs_path`

### `help`

Return the supported actions and the story-compatible textual examples:

- `nextlens new --context path/to/context.yaml`
- `nextlens doctor --packet path/to/packet.json`
- `nextlens salmon --findings path/to/findings.jsonl`
- `nextlens help`