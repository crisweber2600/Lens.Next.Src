---
name: ausx-lens-doctor
description: Checks Auspex topology health. Use when the user requests 'ausx lens doctor' or 'run lens doctor'.
---

# Auspex Lens Doctor

## Overview

This skill runs lightweight Auspex health checks against authored work archives, feature archives, and living ledgers. Act as a topology triage reviewer: separate projection-blocking defects from draft advisories and route the user to the next workflow that can fix or explain the finding.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, `{project-root}/_bmad/config.toml`, and `{project-root}/_bmad/config.user.toml`, checking root values and the `ausx` or `modules.ausx` section. Use these defaults:

- `work_intake_path`: `{project-root}/docs/features`
- `feature_archive_path`: `{project-root}/docs/features`
- `landscape_root`: `{project-root}/docs`
- `reporting_output_path`: `{project-root}/_bmad-output/auspex`
- `freshness_threshold_hours`: `24`

Use the shared metadata contract at `{project-root}/skills/ausx-setup/assets/metadata-schema.md`. If local execution is available, run:

```bash
python {project-root}/skills/ausx-projection-rebuild/scripts/ausx_projection.py doctor {project-root} --work-intake-path {work_intake_path} --feature-archive-path {feature_archive_path} --landscape-root {landscape_root}
```

If the script cannot run, perform the same checks directly from the metadata contract.

## Doctor Lens

Blocking findings prevent published projection rebuilds: duplicate published stable IDs, missing required metadata, invalid stable ID prefixes, broken `belongs_to`, parent type mismatches, parent cycles, broken local links, and completed published features with no resolvable ledger target.

Advisory findings include draft parent gaps, completed-but-unpromoted knowledge with a valid parent, Salmon signals that need recursive review, stale timestamps, and metadata cleanup that does not make projections unsafe.

## Output Contract

Produce a compact doctor report with scope, source paths, blocking findings, advisory findings, projection rebuild readiness, and next workflow routing. Return or include JSON with `module`, `report_type: lens_doctor`, `status`, `entity_count`, `blocking_count`, `advisory_count`, `projection_rebuild_ready`, and `findings`.

## Routing

- Metadata or parentage blockers: fix source docs or run `ausx-topology-design`.
- Completed unpromoted knowledge: run `ausx-ledger-promotion` after blockers are resolved.
- Salmon signals: run `ausx-salmon-impact`.
- Clean doctor status: run `ausx-projection-rebuild`, then `ausx-reporting-snapshot`.

## Safety Rules

Lens doctor is read-only. Never edit archives, ledgers, projections, or config files during a doctor run. If an obvious fix exists, describe it with exact source paths and route to the owning workflow.