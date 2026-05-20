# Bottom-Up LENS

Start from one feature. Bottom-Up LENS is a standalone BMad module for safely creating one bounded feature packet from explicit local context. It packages setup, packet creation, packet validation, and receipt verification as separate BMad skills.

## Module Boundary

This module is not Lens governance behavior. It does not require or write Lens `feature.yaml`, governance publish artifacts, control-repo branch topology, Lens constitution state, release clones, Landscape, Derived Graph, Salmon, promotion, adjacency, pressure, roadmap, or service/domain/program truth paths.

Runtime packet creation may write only packet JSON, run metadata JSON, receipt JSON, and optional reports under configured `packet_output_path` and `reports_output_path` roots after explicit confirmation. Validation and receipt verification are read-only unless `--report` writes under `reports_output_path`.

## Initial Skill Set

- `bul-setup`: registers module configuration and help discovery.
- `bul-create-packet`: guided/headless workflow for packet creation.
- `bul-validate-packet`: read-only packet validation and BMAD readiness checks.
- `bul-verify-receipt`: read-only receipt and run metadata verification.

## Commands

See `docs/commands.md` for command details.

### Setup

`bul-setup` registers defaults:

- `packet_output_path`: `{project-root}/docs/bottom-up-lens`
- `reports_output_path`: `{project-root}/_bmad-output/bottom-up-lens`
- `default_packet_schema_version`: `bul.feature-packet.v1`

### Create

`bul-create-packet` uses these exact stages: `context-intake`, `candidate-selection`, `local-sufficiency`, `scope-boundary`, `preview`, `confirmation`, `write`, and `receipt`.

Interactive writes require the exact token `CREATE PACKET`. Headless writes require `--confirm`. Dry-run, revise, cancel, duplicate, blocker, and failed-verification exits do not write an accepted packet result.

### Validate

`bul-validate-packet` validates packet shape with handwritten Python rules and reports packet validity separately from BMAD readiness.

Status labels are plain text:

- `Feature packet is valid`
- `Feature packet is not ready yet`
- `Ready for BMAD: not yet`
- `Ready for BMAD: ready`

### Verify

`bul-verify-receipt` compares receipt claims with run metadata and changed-file evidence. Success uses `Non-effects verified`; false or missing evidence uses `Receipt mismatch detected` or a fail-closed structured error.

## Distribution Skeleton

The repository contains the BMad custom module surfaces expected by BMad Builder guidance:

- `.claude-plugin/marketplace.json`
- `skills/bul-setup/assets/module.yaml`
- `skills/bul-setup/assets/module-help.csv`
- `skills/bul-*/SKILL.md`
- `evals/bul-*` placeholder suites

## Examples and Evals

Golden examples live under `evals/bul-validate-packet/files/`, `evals/bul-verify-receipt/files/`, and `evals/bul-create-packet/files/`. They show valid packets, invalid multi-candidate packets, missing explicit out-of-scope, valid-not-BMAD-ready packets, forbidden write fixtures, and false receipt cases.

Artifact and trigger eval definitions live under `evals/`. Positive triggers target Bottom-Up LENS packet creation, validation, and verification. Negative triggers cover Lens lifecycle requests and must not activate this standalone module.

## Release Readiness

Run `python skills/bul-create-packet/scripts/validate_module.py --repo-root . --run-tests` from this module root before release. The release checklist requires metadata, docs, examples, unit tests, fixture tests, evals, and module validation to pass.
