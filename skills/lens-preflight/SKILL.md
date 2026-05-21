---
name: lens-preflight
description: Checks Lens and Lens context readiness. Use when the user requests 'lens preflight' or 'check Lens readiness'.
---

# Lens Preflight

## Overview

This skill checks whether Lens can safely read project knowledge, write reports, and consume optional Lens context. Act as a module readiness reviewer: separate standalone Lens readiness from Lens-owned lifecycle authority, then report blockers before downstream doctor, audit, projection, promotion, topology, or snapshot workflows run.

## Conventions

- Bare paths (e.g. `scripts/lens_preflight.py`) resolve from the skill root.
- `{skill-root}` resolves to this skill's installed directory.
- `{project-root}`-prefixed paths resolve from the project working directory.
- `{skill-name}` resolves to the skill directory's basename.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, `{project-root}/_bmad/config.toml`, and `{project-root}/_bmad/config.user.toml`, checking root values and the `lens` or `modules.lens` section. Use these defaults when config is missing:

- `work_intake_path`: `{project-root}/docs/features`
- `feature_archive_path`: `{project-root}/docs/features`
- `landscape_root`: `{project-root}/docs`
- `reporting_output_path`: `{project-root}/_bmad-output/lens`
- `lens_mode`: `auto`
- `lens_context_path`: `{project-root}/.lens/personal/context.yaml`

## Preflight Contract

Run the deterministic checker when local execution is available:

```bash
python {project-root}/skills/lens-preflight/scripts/lens_preflight.py {project-root} --work-intake-path {work_intake_path} --feature-archive-path {feature_archive_path} --landscape-root {landscape_root} --reporting-output-path {reporting_output_path}
```

If `lens_mode` is `required`, include `--lens-enabled` plus configured Lens paths. If script execution is unavailable, perform the same checks directly: validate configured Lens paths, metadata schema presence, reporting output scope, Lens lifecycle contract discovery, Lens feature context discovery, and governance repo availability when Lens mode is required.

## Clean-Room Lens Boundary

Lens preflight is supplemental. It detects and reports Lens context, but it does not run Lens repo sync, advance lifecycle phases, resolve constitutions, or write governance repo state. When a Lens wrapper has already run Lens preflight, treat that wrapper output as authoritative and include the Lens result as local readiness evidence.

## Output Contract

Return or write JSON with `module`, `report_type: preflight`, `status`, `paths`, `lens`, `blocking`, `advisory`, `blocking_count`, and `advisory_count`. `status` is `blocked` when a finding would make later Lens outputs misleading or unsafe.

## Routing

- Missing Lens config or paths: run `lens-setup` or correct config.
- Missing metadata schema: restore the Lens setup assets.
- Lens governance unavailable in required mode: run Lens preflight or provide the governance repo path.
- Clean preflight: continue to `lens-doctor`, `lens-map-audit`, or the requested Lens workflow.

## Safety Rules

Preflight is read-only. It may inspect project files and report paths, but it must not create output directories, repair config, run Lens commands, or write governance state.