# LENS BMAD Module

LENS is a BMAD-native module for large-system exploration, navigation, slicing, and validation. It makes the slice the central operational unit, supports top-down discovery and bottom-up slice growth, and keeps Work Archive history separate from the current Living Landscape and rebuildable Derived Map projections.

LENS is not a standalone application, not a PRD generator, not a replacement for BMAD, and not a domain/service/feature-first organizer. It feeds BMAD with focused packets and validates whether built slices still match the intended slice, journey, and outcome.

## Official References

- BMAD Builder documentation: https://bmad-builder-docs.bmad-method.org/llms-full.txt
- BMAD Method documentation: https://docs.bmad-method.org//llms-full.txt

## Module Shape

This repository follows the BMAD Builder multi-skill module pattern:

- `skills/bmad-lens-setup/` registers module config and help entries.
- `skills/bmad-lens-*` contains workflow skills for discovery, slicing, mapping, BMAD bridge, validation, Salmon, Doctor, and Auspex.
- `.claude-plugin/marketplace.json` lists all installable skills.
- `_bmad-output/project-context.md` records traceability rules for agents working in this project.

## Source Truth

- Work Archive: `_bmad-output/lens/archive/` records what happened.
- Living Landscape: `_bmad-output/lens/landscape/` records current curated truth.
- Derived Map: `_bmad-output/lens/graph/` is generated and must not be hand-edited.

Slices are reality. Landscape is interpretation. Graph is projection.

## Starting Points

Use `bmad-lens-help` when unsure.

Use `bmad-lens-discover` for a large ambiguous system idea. The top-down path is capture, extraction, context sufficiency, challenged assumptions, outcomes, journeys, slice selection, impact analysis, focused BMAD packet, BMAD execution, validation, and Salmon correction when implementation reveals reality.

Use `bmad-lens-slice-new` for one useful bottom-up thing. A bottom-up slice can remain complete without a system, domain, service, capability, program, initiative, or roadmap.

Use `bmad-lens-prepare-bmad` only after the active slice is focused enough to feed BMAD. Use `bmad-lens-guard-story`, `bmad-lens-validate-slice`, `bmad-lens-salmon`, `bmad-lens-doctor`, and `bmad-lens-auspex` during implementation and review.

## No Growth Without Pressure

A slice never promotes automatically. Promotion requires repeated evidence such as artifact reuse, repeated workflow, repeated dependency, repeated risk, repeated ownership concern, repeated cross-slice coordination, repeated journey, or repeated implementation friction. Promotion candidates are explicit and human-reviewed.

## Installation

Run `bmad-lens-setup` from an environment where this module's skills are available. The setup skill writes module config to `_bmad/config.yaml`, user config to `_bmad/config.user.yaml`, and help entries to `_bmad/module-help.csv`.

## Validation

Run the BMAD Builder module validator:

```bash
python3 .agents/skills/bmad-module-builder/scripts/validate-module.py skills
```

Run LENS asset validation:

```bash
python3 skills/bmad-lens-setup/assets/lens/scripts/validate_lens_assets.py --module-root .
```

Module-level BMAD eval-runner inputs live in `evals/lens/evals.json` and `evals/lens/triggers.json`.

The module is self-contained and does not require any original PDF or uploaded chat files. NorthStar-like education examples are fixtures only; this repository does not scaffold a NorthStarET application.
