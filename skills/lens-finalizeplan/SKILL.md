---
name: lens-finalizeplan
description: NextLens FinalizePlan phase. Use when the user requests finalizePlan, finalizeplan, final planning review, epics, stories, or dev readiness.
---

# Lens FinalizePlan

## Overview

FinalizePlan turns accepted planning inputs into a dev-ready local bundle: `finalizeplan-review.md`, `epics.md`, `stories.md`, `implementation-readiness.md`, `sprint-status.yaml`, and story files under `stories/`. It accepts either full-track TechPlan inputs or express-track ExpressPlan inputs.

## On Activation

1. Resolve `{feature_id}` and run `suggest-next`; stop unless `finalizeplan` is unblocked or active.
2. Read the feature record and determine the track:
   - `full`: use `prd.md`, `ux-design.md`, `architecture.md`, and prior review artifacts.
   - `express`: use `business-plan.md`, `tech-plan.md`, `sprint-plan.md`, and `expressplan-adversarial-review.md`.
3. Run `bmad-review-adversarial-general` across the approved input packet; write `finalizeplan-review.md`.
4. Reconcile accepted review findings into the feature archive before generating the bundle.
5. Use local BMAD skills in this order:
   - `bmad-create-epics-and-stories` -> `epics.md`, `stories.md`
   - `bmad-check-implementation-readiness` -> `implementation-readiness.md`
   - `bmad-sprint-planning` -> `sprint-status.yaml`
   - `bmad-create-story` -> `stories/*.md`
6. Validate and advance:

```bash
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} validate-phase --feature-id {feature_id} --phase finalizeplan
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} advance-phase --feature-id {feature_id} --phase finalizeplan
```

## Artifact Rules

- Every story file must include frontmatter with `feature`, `story_id`, `doc_type: story`, `status`, `title`, `depends_on`, and `updated_at`.
- `sprint-status.yaml` must reference every generated story file.
- Target repository paths must be recorded in `feature.yaml.target_repos` before `/dev` starts.

## Next Action

After completion, route to `/dev`.