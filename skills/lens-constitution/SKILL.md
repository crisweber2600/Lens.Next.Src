---
name: lens-constitution
description: NextLens clean-room constitution resolver. Use when the user requests constitution, governance rules, governance checks, or wants to validate a local feature archive against workspace constitutions.
---

# Lens Constitution

## Overview

Lens Constitution is the clean-room constitution resolver for NextLens. It reads constitutions from the local constitution tree, derives scope from local feature archives under `docs/features/<feature-id>/`, and returns the effective ruleset for the current domain, service, and optional repo scope. It does not invoke `lens.core`, and only writes constitution state when running the explicit `bootstrap` recovery operation.

## Source Model

- Local lifecycle authority: `docs/features/<feature-id>/feature.yaml`
- Local topology context: authored ledgers under `docs/`
- Local constitution root: `.lens/.constitution/`

## Scope Resolution

When a local feature archive is available, derive constitution scope in this order:

1. Explicit `domain`, `service`, and `repo` inputs.
2. Feature fields already recorded in `feature.yaml`.
3. The local stable-id graph rooted in `feature.yaml.belongs_to` and the parent ledger chain under `docs/`.

Constitution root resolution should prefer an explicit `--constitution-root`, then feature-level constitution-root fields when present, then the workspace default `.lens/.constitution/`.

## Deterministic Operations

```bash
python skills/lens-constitution/scripts/constitution_ops.py resolve --project-root {project-root} --feature-id {feature_id}
python skills/lens-constitution/scripts/constitution_ops.py progressive-display --project-root {project-root} --feature-id {feature_id}
python skills/lens-constitution/scripts/constitution_ops.py check-compliance --project-root {project-root} --feature-id {feature_id}
python skills/lens-constitution/scripts/constitution_ops.py bootstrap --project-root {project-root}
```

## Capabilities

- `resolve`: merge org, domain, service, and optional repo constitutions for the requested scope.
- `progressive-display`: show the current hard gates, reviewers, required artifacts, and track permissions for the local phase.
- `check-compliance`: validate local artifacts against the resolved constitution using local feature docs as the default artifact path.
- `bootstrap`: create a minimal `org/constitution.md` when the constitution tree is missing so blocked flows can recover.

## Local Phase Mapping

NextLens local phases map to constitution phases as follows:

- `preplan`, `businessplan`, `techplan`, `expressplan`, `finalizeplan` -> `planning`
- `dev` -> `dev`
- `dev-complete` -> `complete`

## Safety Rules

- Do not treat constitutions as local lifecycle authority.
- Do not write to the constitution root except when explicitly running `bootstrap` for constitution recovery.
- Do not infer feature scope from branch names or open editors.
- Stop on org constitution parse errors or missing org constitutions.

## Output Contract

Return JSON that includes:

- resolved constitution root
- resolved scope and levels loaded
- merged structured constitution fields
- per-level details and combined prose
- warnings for parse issues, unknown tracks, and empty track intersections
- compliance findings when the check-compliance operation is used