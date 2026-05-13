# LENS Completion Audit - nextGoal.md

Date: 2026-05-13

Source goal: `nextGoal.md`
Supporting context: `context.md`

Official references checked:

- BMAD Builder documentation: https://bmad-builder-docs.bmad-method.org/llms-full.txt
- BMAD Method documentation: https://docs.bmad-method.org/llms-full.txt

## Result

Status: pass with one external eval-runner blocker documented.

The repository contains a BMAD-native LENS module using the `lens` module code and the `bmad-lens-*` skill surface. This pass focused on the highest-confidence internal consistency fixes requested by `nextGoal.md`: relationship lifecycle/type/gate enforcement, canonical slice artifact contract alignment, eval coverage, and validation proofing. It keeps LENS self-contained and does not create NorthStarET or any application scaffold.

## Requirements Addressed

### Relationship Contract

- Updated `skills/bmad-lens-setup/assets/lens/schemas/lens-entity.schema.json` so relationship lifecycle state `promoted` is valid while preserving the broader entity status enum.
- Added `x_lens_relationship_lifecycle` to the entity schema for explicit relationship-state documentation.
- Updated `skills/bmad-lens-setup/assets/lens/schemas/relationship-types.yaml` to be the canonical relationship contract, including graph projection types used by deterministic tooling:
  - `possibly_conflicts_with`
  - `touches_file`
  - `touches_contract`
  - `promotes_to`
  - `related_to`
- Updated `skills/bmad-lens-setup/assets/lens/templates/relationship.yaml` so relationships carry all canonical gates:
  - discovery
  - challenge
  - promotion
  - bmad
  - implementation
  - salmon
  - validation
- Strengthened `skills/bmad-lens-setup/assets/lens/scripts/validate_lens_assets.py` to enforce relationship types, lifecycle states, and gate completeness from `relationship-types.yaml`.
- Updated `skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py` so adjacency reasons are not projected as noncanonical relationship types.

### Slice Artifact Contract

Canonical decision: `slice.yaml` is the source truth for LENS slices.

The canonical slice source truth now keeps these fields inline:

- `scope.includes`
- `scope.excludes`
- `acceptance_evidence`
- `risks`

Separate `acceptance-evidence.yaml` and `risks.yaml` files are not canonical source truth for LENS slices. `slice.md` may remain a human-readable companion.

Updated:

- `skills/bmad-lens-slice-new/SKILL.md`
- `skills/bmad-lens-setup/assets/lens/references/skill-contracts.md`
- `skills/bmad-lens-setup/assets/lens/references/lens-module-guide.md`
- `README.md`
- `skills/bmad-lens-setup/assets/module-help.csv`
- `_bmad/module-help.csv`
- `skills/bmad-lens-setup/assets/lens/scripts/validate_lens_assets.py`

### Evals And Triggers

- Updated `skills/bmad-lens-setup/assets/lens/evals/lens-evals.yaml`.
- Updated `evals/lens/evals.json`.
- Updated `evals/lens/triggers.json`.
- Added `relationship_contract_validation`.
- Updated `bottom_up_remains_slice` to assert inline `acceptance_evidence` and `risks`.
- Preserved required coverage for:
  - top-down routing to discovery rather than PRD
  - bottom-up slice-first behavior
  - repeated pressure promotion candidate without automatic promotion
  - focused BMAD packet
  - context gate blocking premature PRD
  - workstream impact projection
  - guard-story traceability
  - Salmon upstream impact
  - Doctor invalid topology detection
  - Auspex read-only status
  - project context initialization

### Tests

- Updated `skills/bmad-lens-setup/assets/lens/scripts/tests/test_validate_lens_assets.py`.
- Updated `skills/bmad-lens-setup/assets/lens/scripts/tests/test_lens_artifact_ops.py`.
- Added validator regression coverage for:
  - unknown relationship types
  - relationship lifecycle values missing from the schema
  - missing or unknown relationship gates
  - noncanonical split slice artifacts
  - missing inline `acceptance_evidence` and `risks`
  - generated graph relationship types staying inside the canonical contract

## Validation Commands

Final validation commands passed:

```text
python3 .agents/skills/bmad-module-builder/scripts/validate-module.py skills
status: pass, total_findings: 0

python3 skills/bmad-lens-setup/assets/lens/scripts/validate_lens_assets.py --module-root .
status: pass, findings: []

PATH="$PWD/.venv/bin:$PATH" pytest skills/bmad-lens-setup/assets/lens/scripts/tests -q
9 passed in 0.58s

PATH="$PWD/.venv/bin:$PATH" pytest skills/bmad-lens-setup/scripts/tests -q
3 passed in 0.09s

python3 -m py_compile skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py skills/bmad-lens-setup/assets/lens/scripts/validate_lens_assets.py skills/bmad-lens-setup/scripts/merge-config.py skills/bmad-lens-setup/scripts/merge-help-csv.py skills/bmad-lens-setup/scripts/cleanup-legacy.py
pass

python3 -m json.tool evals/lens/evals.json
valid JSON

python3 -m json.tool evals/lens/triggers.json
valid JSON
```

Artifact smoke commands:

```text
python3 skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py init --project-root .
status: ok, directories: 31

python3 skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py map-rebuild --project-root .
status: ok, nodes: 17, relationships: 40, traceability: 2, warnings: 37

python3 skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py doctor --project-root .
status: ok, warnings: 37
warning types: workstream_impact_gate, duplicate_id, orphan_ref, unresolved_promoted_ref, unresolved_decision

python3 skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py auspex --project-root .
status: ok, active_slices: 2
```

## Eval Runner

The BMAD eval-runner skill exists at `.agents/skills/bmad-eval-runner`.

Discovered invocation:

```text
python3 .agents/skills/bmad-eval-runner/scripts/run_evals.py --help
python3 .agents/skills/bmad-eval-runner/scripts/run_triggers.py --help
```

Attempted artifact eval command:

```text
python3 .agents/skills/bmad-eval-runner/scripts/run_evals.py --skill-path skills/bmad-lens-help --evals-file evals/lens/evals.json --project-root . --output-dir _bmad-output/lens/validation/eval-runs --isolation local --workers 1 --timeout 30 --quiet
```

Result: blocked.

Reasons:

- `which claude` returned exit code 1, so the required Claude CLI is unavailable.
- `docker info` returned permission denied connecting to `unix:///var/run/docker.sock`, so Docker isolation is unavailable.
- The local attempt with an in-repo output directory recursively copied `_bmad-output/lens/validation/eval-runs` into its own staged workspaces and was stopped. The generated eval-run directories were removed after cleanup.

## Assumptions

- `nextGoal.md` is the operative goal.
- `context.md` is supporting design context and confirms the top-down/bottom-up LENS model.
- Relationship contract enforcement should use `relationship-types.yaml` as canonical.
- Slice source truth should stay in `slice.yaml` rather than split across multiple YAML files.

## Blockers

- The artifact eval-runner cannot complete in this environment until either the `claude` CLI is available for local isolation or Docker access is granted for Docker isolation.
