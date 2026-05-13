Implement the remaining hardening work for the BMAD-native LENS module. Do not build any product or app. Do not create NorthStarET. This repo is only for the LENS module.

Use repository-local patterns first. Then use the official references below for module packaging and BMAD workflow alignment:

- BMAD Builder docs: https://bmad-builder-docs.bmad-method.org/llms-full.txt
- BMAD Method docs: https://docs.bmad-method.org/llms-full.txt

## Design contract you must preserve

LENS = Large-system Exploration, Navigation, Slicing, and Validation.

Core principles:
- The slice is the central unit.
- Support both:
  1. top-down discovery: idea -> discovery epoch -> capture -> extraction -> context sufficiency -> outcomes -> journeys -> selected slice -> impact -> focused BMAD packet -> BMAD workflows -> validation -> Salmon correction
  2. bottom-up growth: slice -> artifact -> adjacency -> repeated pressure -> optional promotion
- Keep Work Archive, Living Landscape, and Derived Map separate.
- Derived Map is generated, rebuildable, and never source truth.
- Salmon propagates downstream discoveries upstream.
- Doctor audits topology.
- Auspex publishes read-only status.
- LENS feeds BMAD; it does not replace BMAD.
- No backward-compatibility aliases are required.
- No growth without pressure.

## What is already present

The repo already has:
- a multi-skill BMAD module shape
- `skills/bmad-lens-setup/`
- `assets/module.yaml`
- `assets/module-help.csv`
- `.claude-plugin/marketplace.json`
- `_bmad/module-help.csv`
- `_bmad-output/project-context.md`
- the full `bmad-lens-*` skill surface, including Salmon, Doctor, and Auspex

Do not re-scaffold the module from scratch. Harden and complete it.

## Gaps to fix

1. Derived Map / Doctor / Auspex behavior is too shallow.
   Current script:
   - writes empty relationships
   - writes empty relationship/traceability indexes
   - writes minimal freshness only
   - doctor checks only duplicates/missing trees
   - auspex reports only counts and basic slices/signals

   Implement real projection behavior in:
   - `skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py`

   Required behavior:
   - parse entity IDs, kinds, relationship refs, `from/type/to`, parent refs, BMAD artifact refs, and validation refs from archive + landscape files
   - materialize non-empty `relationship-index.yaml`
   - materialize `traceability-index.yaml`
   - materialize `freshness-index.yaml` with stale/needs-review signals
   - detect orphan refs, missing ledgers, duplicate IDs, unresolved promoted refs, stale ledgers, and untraced stories in Doctor
   - produce richer Auspex status: active outcomes, journeys, slices, decisions, risks, blockers, BMAD progress, validation evidence, Salmon signals

2. Normalize the validation folder contract.
   Make the primary validation output path:
   - `_bmad-output/lens/validation`

   Keep archival history under:
   - `_bmad-output/lens/archive/validation-results`

   Update all references consistently in:
   - `skills/bmad-lens-setup/assets/module.yaml`
   - `_bmad/config.yaml`
   - `skills/bmad-lens-setup/assets/lens/schemas/directory-map.yaml`
   - `skills/bmad-lens-setup/assets/lens/references/lens-module-guide.md`
   - `README.md`
   - `skills/bmad-lens-setup/assets/lens/scripts/validate_lens_assets.py`
   - any impacted SKILL.md files or templates

3. Enrich top-down templates and add missing source templates.
   Update:
   - `skills/bmad-lens-setup/assets/lens/templates/slice.yaml`
   - `skills/bmad-lens-setup/assets/lens/templates/impact-map.yaml`
   - `skills/bmad-lens-setup/assets/lens/templates/bmad-packet.md`

   Add missing core templates:
   - `skills/bmad-lens-setup/assets/lens/templates/journey.yaml`
   - `skills/bmad-lens-setup/assets/lens/templates/journey.md`
   - `skills/bmad-lens-setup/assets/lens/templates/journey-map.mmd`

   Top-down slice support must include fields such as:
   - `journey`
   - `outcome`
   - `why_first`
   - `starts_with`
   - `ends_with`
   - `vertical_path`
   - `required_capabilities`
   - explicit scope includes/excludes
   - acceptance evidence

   Bottom-up slices must still remain valid without system/outcome/journey/capability.

4. Add committed fixtures for both canonical modes.
   Add these exact fixture roots:
   - `skills/bmad-lens-setup/assets/lens/fixtures/top-down/evidence-visible-to-teacher/`
   - `skills/bmad-lens-setup/assets/lens/fixtures/bottom-up/download-model-images/`

   Minimum fixture files:
   - top-down:
     - `slice.yaml`
     - `journey.yaml`
     - `impact-map.yaml`
   - bottom-up:
     - `slice.yaml`
     - `adjacency.yaml`
     - `promotion-gate.yaml`

   Fixture semantics:
   - top-down example = “teacher can view a student evidence artifact with source metadata”
   - bottom-up example = “download model listing images locally”

5. Add direct script tests.
   Add:
   - `skills/bmad-lens-setup/assets/lens/scripts/tests/test_lens_artifact_ops.py`
   - `skills/bmad-lens-setup/assets/lens/scripts/tests/test_validate_lens_assets.py`

   Follow repo-local BMAD Builder test style where practical.

6. Strengthen docs.
   Update:
   - `README.md`
   - `skills/bmad-lens-setup/assets/lens/references/lens-module-guide.md`

   Docs must include:
   - BMAD custom-module installation examples
   - setup + validation commands
   - top-down and bottom-up usage examples
   - exact fixture paths
   - one Mermaid relationship diagram
   - one Mermaid implementation timeline

## Acceptance criteria

The work is complete only if all of the following are true:

- BMAD Builder module structure remains valid.
- `module-help.csv`, marketplace skill paths, and registered help entries stay consistent.
- Validation paths are internally consistent and use `_bmad-output/lens/validation` as the primary validation layer.
- `lens_artifact_ops.py map-rebuild` produces real relationship, traceability, freshness, and warning outputs from fixture/source files.
- `doctor` detects more than duplicate IDs and missing trees.
- `auspex` produces richer read-only status than node counts alone.
- Top-down and bottom-up fixtures are committed and usable.
- Template set includes journey templates in addition to slice/impact/BMAD packet templates.
- README and module guide explain installation, operation, and validation clearly.
- No app/product scaffolding is added.
- No NorthStarET code or directories are created.

## Validation commands to run

Run and report results for:

1. BMAD Builder structural validation
python3 .agents/skills/bmad-module-builder/scripts/validate-module.py skills

2. LENS asset validation
python3 skills/bmad-lens-setup/assets/lens/scripts/validate_lens_assets.py --module-root .

3. LENS script tests
pytest skills/bmad-lens-setup/assets/lens/scripts/tests -q

4. LENS artifact smoke tests using the repo root
python3 skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py init --project-root .
python3 skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py map-rebuild --project-root .
python3 skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py doctor --project-root .
python3 skills/bmad-lens-setup/assets/lens/scripts/lens_artifact_ops.py auspex --project-root .

## Non-goals

- Do not create a standalone app.
- Do not create NorthStarET.
- Do not add legacy domain/service/feature aliases unless a repo-local dependency requires them.
- Do not replace BMAD core workflows.
- Do not overbuild autonomous agents if skills/templates/scripts are enough.

## Assumptions

- You have repo write permission.
- Network access may be available for the BMAD docs URLs above.
- Python 3 is available.
- If pytest is not already configured, add only the minimum test scaffolding needed.

## Final reporting format

Return a concise implementation report with:
1. summary of what changed
2. changed files grouped by task
3. validation commands executed and results
4. remaining risks or follow-up ideas

Do not dump large code blocks in the final report. Focus on files changed, why, and proof of correctness.
