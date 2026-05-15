---
name: bmad-nextlens-doctor
description: Runs non-mutating NextLens doctor validation checks on a Feature packet or landscape state.
---

# NextLens Doctor

## Purpose

Validate an emitted Feature packet or reconstructed landscape state without mutating project artifacts.

## On Activation

- Treat this skill as the `doctor` capability of the NextLens module.
- If `{project-root}/_bmad/config.yaml` does not contain an `nxl` section, run `bmad-nextlens-setup` before continuing.
- Normalize arguments with `../bmad-nextlens/scripts/command_surface.py` using action `doctor`.
- Require `packet_source`; optionally accept `docs_path` to override the configured docs root.
- Use the shared implementation under `../bmad-nextlens/scripts/doctor_checks.py` and related support modules.

## Action Contract

Required args:

- `packet_source`

Optional args:

- `docs_path`

Output:

- A doctor validation report describing packet or landscape findings.