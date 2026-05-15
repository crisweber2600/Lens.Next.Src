---
name: bmad-nextlens-new
description: Creates one NextLens Feature packet from top-down discovery context. Use when the user asks to create or emit a NextLens feature packet.
---

# NextLens New Packet

## Purpose

Create one deterministic Feature packet from top-down discovery context.

## On Activation

- Treat this skill as the `new` capability of the NextLens module.
- If `{project-root}/_bmad/config.yaml` does not contain an `nxl` section, run `bmad-nextlens-setup` before continuing.
- Normalize arguments with `../bmad-nextlens/scripts/command_surface.py` using action `new`.
- Require `context_source`; optionally accept `docs_path` to override the configured docs root.
- Use the shared implementation under `../bmad-nextlens/scripts/` for context loading, candidate selection, packet composition, confirmation, and emission.

## Action Contract

Required args:

- `context_source`

Optional args:

- `docs_path`

Output:

- One Feature packet JSON artifact in the configured NextLens docs path.