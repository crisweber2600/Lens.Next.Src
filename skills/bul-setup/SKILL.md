---
name: bul-setup
description: Sets up the Bottom-Up LENS BMad module in a project. Use when the user requests to install, configure, or refresh Bottom-Up LENS module registration.
---

# Bottom-Up LENS Setup

## Purpose

Registers Bottom-Up LENS as a standalone multi-skill BMad module. Module identity, configuration variables, and help entries come from `./assets/module.yaml` and `./assets/module-help.csv`.

## Boundary

This setup skill registers only Bottom-Up LENS configuration and help discovery. It must not create, read, or mutate Lens governance `feature.yaml`, governance publish outputs, branch topology, release clones, Landscape, Derived Graph, Salmon, promotion, adjacency, pressure, roadmap, or service/domain/program truth paths.

## Inputs

Optional setup answers may provide:

- `packet_output_path`
- `reports_output_path`
- `default_packet_schema_version`

Defaults are defined in `./assets/module.yaml`.

## Outputs

- `{project-root}/_bmad/config.yaml` with a `bul` module section.
- `{project-root}/_bmad/config.user.yaml` only for user-scoped answers if later added.
- `{project-root}/_bmad/module-help.csv` entries for Bottom-Up LENS capabilities.
- Configured output directories for packet and report artifacts.

## On Activation

1. Read `./assets/module.yaml` and `./assets/module-help.csv`.
2. If the user asks for setup with defaults, use the module defaults without extra prompting.
3. Otherwise collect only unresolved setup values.
4. Run the merge scripts in `./scripts/` to update BMad config and help registration using anti-zombie replacement.
5. Create configured directories after resolving `{project-root}` from stored config values.
6. Summarize registered capabilities and configured output roots.

## Future Validation Route

Structural package validation is intentionally a placeholder in this scaffold story. Later stories add deterministic validation that verifies setup assets, help entries, marketplace paths, skill folders, and eval suites.
