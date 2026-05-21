---
name: lens-preplan
description: NextLens PrePlan phase. Use when the user requests preplan, /preplan, brainstorm, research, or product brief work for a feature.
---

# Lens PrePlan

## Overview

PrePlan creates the first local planning packet for a feature archive: `brainstorm.md`, `research.md`, `product-brief.md`, and `preplan-adversarial-review.md`. It is a conductor over local BMAD skills and local feature artifacts. It does not write external governance mirrors or create planning branches.

## On Activation

1. Resolve `{feature_id}` and run `suggest-next`; stop if the feature is not on the `preplan` path.
2. Load `docs/features/{feature_id}/feature.yaml`, `work.md`, `memory.md`, `links.md`, and any living ledger parent referenced by `belongs_to`.
3. Use `bmad-agent-analyst` for problem framing when the feature lacks product clarity.
4. Use `bmad-brainstorming` or the user-selected local ideation route to produce `brainstorm.md`.
5. Use the narrowest research skill for `research.md`: `bmad-domain-research`, `bmad-market-research`, or `bmad-technical-research`.
6. Use `bmad-product-brief` to produce `product-brief.md`.
7. Run an adversarial planning review with `bmad-review-adversarial-general` and record `preplan-adversarial-review.md`.
8. Validate artifacts:

```bash
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} validate-phase --feature-id {feature_id} --phase preplan
```

9. If validation passes, advance the local feature record:

```bash
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} advance-phase --feature-id {feature_id} --phase preplan
```

## Artifact Rules

- Write all phase artifacts under `docs/features/{feature_id}/`.
- Set artifact frontmatter `publication_state: draft` until reviewed and accepted.
- Preserve `stable_id`, `belongs_to`, `related_to`, Salmon signals, and source breadcrumbs.

## Next Action

After completion, route full-track features to `/businessplan`.