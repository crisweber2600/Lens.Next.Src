# LENS Completion Audit

Objective: read `lens-goal.md` and execute it by creating a BMAD-native LENS module using the BMAD Builder and BMAD Method references.

Official references used and preserved in module docs:

- BMAD Builder documentation: https://bmad-builder-docs.bmad-method.org/llms-full.txt
- BMAD Method documentation: https://docs.bmad-method.org//llms-full.txt

## Deliverable Checklist

| Requirement | Evidence | Status |
| --- | --- | --- |
| Inspect repository and local BMAD conventions before editing. | Existing `_bmad/config.yaml`, `_bmad/module-help.csv`, BMad Builder setup skill, scaffold script, validator script, and eval format reference were inspected. | Pass |
| Use BMAD Builder conventions for module packaging. | `skills/bmad-lens-setup/assets/module.yaml`, `skills/bmad-lens-setup/assets/module-help.csv`, setup merge scripts, and BMAD Builder validator pass. | Pass |
| Use BMAD Method conventions for lifecycle and artifact locations. | `skills/bmad-lens-setup/assets/lens/references/bmad-integration.md`, `_bmad-output/project-context.md`, and phase values in module help map to BMAD phases. | Pass |
| Create a BMAD-native LENS module, not a standalone app. | Module source is under `skills/bmad-lens-*`; no app/package runtime was scaffolded. | Pass |
| Use `bmad-lens-*` names. | 32 skill folders exist under `skills/`, all named `bmad-lens-*`. | Pass |
| Include setup and help registration. | `skills/bmad-lens-setup/` exists; `_bmad/module-help.csv` contains 32 `LENS` entries. | Pass |
| Include marketplace/plugin manifest. | `.claude-plugin/marketplace.json` lists all 32 LENS skill folders. | Pass |
| Implement Work Archive, Living Landscape, Derived Map model. | `lens-module-guide.md`, `directory-map.yaml`, templates, and initialized `_bmad-output/lens/archive`, `landscape`, and `graph` trees. | Pass |
| Make slice the central unit. | `lens-module-guide.md`, `slice.yaml`, slice skills, examples, and evals emphasize slices as central. | Pass |
| Support top-down discovery. | `bmad-lens-discover`, capture/synthesize/context/map/journey/slice skills, top-down example, and eval case. | Pass |
| Support bottom-up growth. | `bmad-lens-slice-new`, adjacency/repetition/promotion skills, bottom-up example, and eval case. | Pass |
| Enforce no growth without pressure. | Guide, skill contracts, promotion gate template, promotion skill, pressure eval, and repeated-pressure rules. | Pass |
| Include evidence-driven optional promotion. | `promotion-gate.yaml`, `bmad-lens-suggest-promotion`, relationship gates, and eval coverage. | Pass |
| Include knowledge states and confidence levels. | `schemas/knowledge-states.yaml` and JSON entity schema. | Pass |
| Include all required core entities. | `schemas/lens-entity.schema.json` contains all listed entity kinds. | Pass |
| Use stable IDs rather than paths as identity. | Skill conventions, guide, project context, and templates state ID/path rule. | Pass |
| Include relationship lifecycle, types, and gates. | `schemas/relationship-types.yaml`, `relationship.yaml`, and guide. | Pass |
| Include discovery epoch behavior. | `discovery-epoch.yaml`, `bmad-lens-discover`, and context sufficiency instructions. | Pass |
| Include context sufficiency gate that can block PRD. | `bmad-lens-context-check`, `context-sufficiency.md`, guide, and eval case. | Pass |
| Include LENS layers 0-11. | `lens-module-guide.md` documents BMAD core, capture, extraction, intent, journey, slice, landscape, graph, BMAD bridge, implementation guard, Salmon, and Auspex layers. | Pass |
| Include slice model. | `templates/slice.yaml`, slice skills, top-down and bottom-up examples. | Pass |
| Include promotion model. | Guide, `promotion-gate.yaml`, detect repetition, suggest promotion, promote landscape. | Pass |
| Include impact/workstream analysis. | `bmad-lens-analyze-impact` and `impact-map.yaml`. | Pass |
| Include focused BMAD packet behavior. | `bmad-lens-prepare-bmad`, `bmad-packet.md`, focused packet example. | Pass |
| Generate/update project context guidance. | `_bmad-output/project-context.md` contains traceability, scope, architecture, change, and source truth rules. | Pass |
| Include implementation guard behavior. | `bmad-lens-guard-story` and `story-guard.yaml`. | Pass |
| Include Salmon behavior. | `bmad-lens-salmon`, `salmon-signal.yaml`, guide, and eval case. | Pass |
| Include Doctor behavior. | `bmad-lens-doctor`, `doctor-report.md`, `lens_artifact_ops.py doctor`, generated `graph/doctor-report.md`. | Pass |
| Include Auspex behavior. | `bmad-lens-auspex`, `auspex-status.yaml`, `lens_artifact_ops.py auspex`, generated Auspex status files. | Pass |
| Include illustrative examples. | `examples/top-down-education-example.yaml`, `examples/bottom-up-model-images-example.yaml`, and `examples/focused-bmad-packet-example.md`. | Pass |
| Include eval coverage. | `skills/bmad-lens-setup/assets/lens/evals/lens-evals.yaml`, `evals/lens/evals.json`, and `evals/lens/triggers.json` cover the 8 required cases. | Pass |
| Avoid NorthStarET application scaffolding. | No `NorthStarET` directory or app package exists; education example is fixture-only. | Pass |
| Register or make registerable with BMAD help. | Setup skill assets are present, and `_bmad/module-help.csv` has 32 LENS rows. | Pass |
| Keep module self-contained without PDF/chat dependency. | README and guide state no original PDF or uploaded chat files are required; module assets contain all needed templates/examples/contracts. | Pass |

## Validation Commands

| Command | Result |
| --- | --- |
| `python3 .agents/skills/bmad-module-builder/scripts/validate-module.py skills` | Pass |
| `python3 skills/bmad-lens-setup/assets/lens/scripts/validate_lens_assets.py --module-root .` | Pass |
| `python3 skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py init --project-root .` | Pass |
| `python3 skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py map-rebuild --project-root .` | Pass |
| `python3 skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py doctor --project-root .` | Pass |
| `python3 skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py auspex --project-root .` | Pass |
| `python3 -m json.tool .claude-plugin/marketplace.json` | Pass |
| `python3 -m json.tool skills/bmad-lens-setup/assets/lens/schemas/lens-entity.schema.json` | Pass |
| `python3 -m json.tool evals/lens/evals.json` | Pass |
| `python3 -m json.tool evals/lens/triggers.json` | Pass |
| YAML parse check for all `*.yaml` files | Pass |
| CSV parse check for all `*.csv` files | Pass |
| `python3 -m py_compile` for LENS and setup scripts | Pass |

## Residual Notes

The BMAD eval definitions were added and validated for format, but the live eval runner was not executed because that requires an external model runner environment. Static module, schema, registration, script, and format validation passed.
