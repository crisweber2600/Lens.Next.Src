---
name: lens-expressplan
description: NextLens ExpressPlan phase. Use when the user requests expressplan, /expressplan, or compact planning for an express-track feature.
---

# Lens ExpressPlan

## Overview

ExpressPlan is the compact planning path for features that do not need separate PrePlan, BusinessPlan, and TechPlan phases. It produces `business-plan.md`, `tech-plan.md`, `sprint-plan.md`, and `expressplan-adversarial-review.md`, then hands off to FinalizePlan.

## On Activation

1. Resolve `{feature_id}` and confirm `feature.yaml.track` is `express` or the user explicitly wants the express track.
2. Read `work.md`, `memory.md`, `links.md`, related feature archives, and parent ledgers.
3. Use `bmad-agent-analyst`, `bmad-prd` or `bmad-product-brief` patterns to produce `business-plan.md`.
4. Use `bmad-agent-architect` or `bmad-create-architecture` patterns to produce `tech-plan.md`.
5. Use `bmad-sprint-planning` patterns to produce `sprint-plan.md` with candidate story boundaries and dependencies.
6. Run `bmad-review-adversarial-general` against the whole express packet and write `expressplan-adversarial-review.md`.
7. Validate and advance:

```bash
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} validate-phase --feature-id {feature_id} --phase expressplan
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} advance-phase --feature-id {feature_id} --phase expressplan
```

## Artifact Rules

- Keep business, technical, and sprint decisions separate even though the track is compact.
- Use `publication_state` in artifacts and the feature record; do not create branch-only planning state.
- Capture Salmon signals when express planning discovers upstream impact.

## Next Action

After completion, route express-track features to `/finalizePlan`.