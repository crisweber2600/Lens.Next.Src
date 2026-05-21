---
name: lens-techplan
description: NextLens TechPlan phase. Use when the user requests techplan, /techplan, architecture, or technical design planning for a feature.
---

# Lens TechPlan

## Overview

TechPlan creates the local technical architecture packet for full-track features: `architecture.md` and `techplan-adversarial-review.md`. It treats PRD/UX as local source context and keeps durable truth in the Two-Tree model.

## On Activation

1. Resolve `{feature_id}` and run `suggest-next`; stop unless `techplan` is unblocked or already active.
2. Read `prd.md`, `ux-design.md`, PrePlan artifacts, feature memory, and parent ledgers.
3. Stop if no PRD-equivalent artifact can be found in the feature archive.
4. Resolve constitution before delegation:

```bash
python skills/lens-constitution/scripts/constitution_ops.py resolve --project-root {project-root} --feature-id {feature_id}
python skills/lens-constitution/scripts/constitution_ops.py progressive-display --project-root {project-root} --feature-id {feature_id}
```

5. Stop immediately if constitution resolution fails, if the resolved gate mode is hard and the track is not permitted, or if the resolved constitution identifies a hard-gate requirement the planned TechPlan artifacts would violate. Surface the applicable hard-gate rules and carry the combined constitution prose into every downstream planning delegation.
6. Use `bmad-create-architecture` to produce `architecture.md`.
7. Run `bmad-review-adversarial-general` against architecture, PRD/UX context, related ledgers, and Salmon risks; write `techplan-adversarial-review.md`.
8. Validate and advance:

```bash
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} validate-phase --feature-id {feature_id} --phase techplan
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} advance-phase --feature-id {feature_id} --phase techplan
```

## Artifact Rules

- Architecture must name target repositories, integration boundaries, data contracts, rollout risks, and test strategy where applicable.
- If architecture changes parent service/domain assumptions, set or preserve a Salmon signal in the feature record.

## Next Action

After completion, route full-track features to `/finalizePlan`.