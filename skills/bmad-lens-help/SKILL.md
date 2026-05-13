---
name: bmad-lens-help
description: Guide users to the next LENS or BMAD step for discovery, slicing, traceability, and validation.
---

# LENS Help

## Overview

Routes a user request to the right LENS capability, explains the current topology state, and recommends next BMAD skills without replacing BMAD.


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

1. Read available LENS config and indexes.
2. Classify the request as top-down, bottom-up, bridge, validation, correction, audit, or visibility.
3. Recommend one or more LENS skills and any matching BMAD core skills.
4. Explain source-of-truth boundaries: archive, landscape, and graph.

## Required Output Discipline

- Write artifacts only under the configured LENS output folders unless the user gives another path.
- Preserve source references and confidence on every major entity.
- For bottom-up slices, do not require system, domain, service, capability, program, initiative, or roadmap fields.
- For top-down work, do not recommend BMAD PRD creation until `bmad-lens-context-check` says PRD readiness is ready or explicitly accepted by the user.
- When a BMAD workflow is the correct next step, recommend the BMAD skill by name and explain what LENS packet or evidence should feed it.

## Produces

routing guidance and next-step recommendation.
