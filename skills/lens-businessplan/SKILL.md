---
name: lens-businessplan
description: NextLens BusinessPlan phase. Use when the user requests businessplan, /businessplan, PRD, or UX design planning for a feature.
---

# Lens BusinessPlan

## Overview

BusinessPlan turns reviewed PrePlan context into local `prd.md`, `ux-design.md`, and `businessplan-adversarial-review.md`. It uses local BMAD planning skills and local feature archives only.

## On Activation

1. Resolve `{feature_id}` and run `suggest-next`; stop unless `businessplan` is unblocked or already active.
2. Read the feature record and PrePlan artifacts from `docs/features/{feature_id}/`.
3. Load related living ledgers and related feature archives referenced by `belongs_to`, `related_to`, `extends`, `depends_on`, or `links`.
4. Resolve constitution before delegation:

```bash
python skills/lens-constitution/scripts/constitution_ops.py resolve --project-root {project-root} --feature-id {feature_id}
python skills/lens-constitution/scripts/constitution_ops.py progressive-display --project-root {project-root} --feature-id {feature_id}
```

5. Stop immediately if constitution resolution fails, if the resolved gate mode is hard and the track is not permitted, or if the resolved constitution identifies a hard-gate requirement the planned BusinessPlan artifacts would violate. Surface the applicable hard-gate rules and carry the combined constitution prose into every downstream planning delegation.
6. Use `bmad-prd` or `bmad-create-prd` to produce `prd.md`.
7. Use `bmad-create-ux-design` when UX behavior, flows, screens, or stakeholder journeys are in scope; otherwise record an explicit UX non-applicability note in `ux-design.md`.
8. Run `bmad-review-adversarial-general` against PRD, UX, PrePlan context, and topology assumptions; write `businessplan-adversarial-review.md`.
9. Validate and advance:

```bash
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} validate-phase --feature-id {feature_id} --phase businessplan
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} advance-phase --feature-id {feature_id} --phase businessplan
```

## Artifact Rules

- PRD and UX artifacts stay in the feature archive.
- Use `publication_state` rather than planning branches to distinguish draft and accepted state.
- Do not copy artifacts to an external governance mirror.

## Next Action

After completion, route full-track features to `/techplan`.