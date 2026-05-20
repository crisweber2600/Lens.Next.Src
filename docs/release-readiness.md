# Bottom-Up LENS Release Readiness

## Module validation route

Run from the module root:

`python skills/bul-create-packet/scripts/validate_module.py --repo-root . --run-tests`

The validator checks marketplace metadata, setup help registration, eval definition JSON, the release checklist, and optionally the pytest suite. Release readiness requires all checks to pass.

## Read-only consumer contract

Future reporting or BMAD handoff consumers may read these fields without mutating packet state:

- packet status
- provenance
- packet validity result
- BMAD readiness result
- identity and selected feature

Consumers must not promote topology, write Landscape or Derived Graph outputs, update `feature.yaml`, publish governance, or create service/domain/program truth paths.

## Constitutional planning traceability

For full-track planning equivalence:

- product brief, research, brainstorm, PRD, and UX artifacts together satisfy the business-plan equivalent.
- `architecture.md` satisfies the tech-plan equivalent.

This module is package-validation ready only after metadata, docs, examples, unit tests, fixture tests, evals, and module validation pass. It does not claim Lens governance, topology promotion, release-clone, or current top-down runtime readiness.
