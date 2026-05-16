---
name: bmad-nextlens-salmon
description: Routes NextLens correction findings through deduplication and impact classification.
---

# NextLens Salmon

## Purpose

Route correction findings through NextLens impact classification, deduplication, and correction mapping so upstream packet or landscape changes can be corrected deliberately.

## On Activation

- Treat this skill as the `salmon` capability of the NextLens module.
- If `{project-root}/_bmad/config.yaml` does not contain an `nxl` section, run `bmad-nextlens-setup` before continuing.
- Normalize arguments with `../bmad-nextlens/scripts/command_surface.py` using action `salmon`.
- Require `findings_source`; optionally accept `docs_path` to override the configured docs root.
- Use the shared implementation under `../bmad-nextlens/scripts/salmon_routing.py`, `salmon_deduplication.py`, and related support modules.
- Consume validation or Doctor findings that indicate upstream truth changed, map impact to the appropriate correction route, and emit Salmon signals for governed follow-up.

## Action Contract

Required args:

- `findings_source`

Optional args:

- `docs_path`

Output:

- A salmon routing report with deduplication and impact classification results.

Salmon routes corrections; it does not auto-promote Feature work into Capability, Domain, or System hierarchy and does not make Derived Graph authoritative.
