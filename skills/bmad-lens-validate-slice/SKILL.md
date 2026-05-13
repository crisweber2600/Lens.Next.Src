---
name: bmad-lens-validate-slice
description: Validate whether implementation evidence satisfies the active slice goal, scope, exclusions, and acceptance evidence.
---

# Validate Slice

## Overview

Produces a validation result for the slice and identifies stale assumptions, missing evidence, or Salmon needs.


## Conventions

- Bare paths such as `templates/slice.yaml` resolve from this skill's installed directory.
- Shared LENS references live at `../bmad-lens-setup/assets/lens/`.
- Project artifacts use `_bmad-output/lens/` unless module config overrides the output folder.
- IDs are identity. Paths are addresses and must not be used as identity.
- Archive records history, Landscape records current truth, and Graph records derived projections.
- AI hypotheses are not facts. Mark status, confidence, provenance, and open questions explicitly.
- No growth without pressure: never promote a slice into a capability, domain, program, or system without repeated evidence and human review.

## On Activation

1. Load available config from `{project-root}/_bmad/config.yaml` and `{project-root}/_bmad/config.user.yaml`, including the `lens` section when present.
2. If config is missing, continue with defaults and mention that `bmad-lens-setup` can register the module.
3. Read `../bmad-lens-setup/assets/lens/references/lens-module-guide.md` for the LENS model.
4. Read `../bmad-lens-setup/assets/lens/references/skill-contracts.md` and follow the section for this skill.
5. Prefer existing project artifacts in `_bmad-output/lens/` over recreating them.
6. Do not overwrite unrelated user changes. When updating ledgers, supersede or append unless the user asks for a direct replacement.

## Procedure

1. Compare implementation evidence to slice acceptance evidence.
2. Check explicit exclusions were not silently added.
3. Mark pass, fail, partial, blocked, or needs-review.
4. Record evidence and recommended corrections.

## Required Output Discipline

- Write artifacts only under the configured LENS output folders unless the user gives another path.
- Preserve source references and confidence on every major entity.
- For bottom-up slices, do not require system, domain, service, capability, program, initiative, or roadmap fields.
- For top-down work, do not recommend BMAD PRD creation until `bmad-lens-context-check` says PRD readiness is ready or explicitly accepted by the user.
- When a BMAD workflow is the correct next step, recommend the BMAD skill by name and explain what LENS packet or evidence should feed it.

## Produces

slice validation result.
