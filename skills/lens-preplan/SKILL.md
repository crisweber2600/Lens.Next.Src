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
3. Resolve constitution before delegation:

```bash
python skills/lens-constitution/scripts/constitution_ops.py resolve --project-root {project-root} --feature-id {feature_id}
python skills/lens-constitution/scripts/constitution_ops.py progressive-display --project-root {project-root} --feature-id {feature_id}
```

4. If constitution resolution fails with `constitution_root_not_found` or `org_constitution_missing`, enter recovery mode instead of hard stop:
- Explain that constitution bootstrap is required and show the missing path.
- Offer numbered options and use `vscode_askQuestions` when available:
	1. Create a starter constitution and continue.
	2. Show suggested constitution structure/examples, then choose whether to create.
	3. Stop and let the user provide a custom constitution root.
- For option 1, run:

```bash
python skills/lens-constitution/scripts/constitution_ops.py bootstrap --project-root {project-root}
```

- Re-run `resolve` and `progressive-display`, then continue PrePlan when successful.
- If `vscode_askQuestions` is unavailable, render the numbered menu and stop.
5. Hard stop only when constitution resolution fails for non-recoverable reasons (for example parse errors), when the resolved gate mode is hard and the track is not permitted, or when the resolved constitution identifies a hard-gate requirement the planned PrePlan artifacts would violate. Surface the applicable hard-gate rules and carry the combined constitution prose into every downstream planning delegation.
6. Run a scope sufficiency gate before any artifact generation. Treat the request as underscoped if any required planning signal is missing or ambiguous:
- problem statement and gap to close
- target user or operator persona
- desired outcome and success signal
- boundaries or non-goals
7. If the request is underscoped, switch to interactive mode and collect clarifications before continuing:
- Ask direct, numbered questions and wait for user answers.
- Use `vscode_askQuestions` when available.
- If `vscode_askQuestions` is unavailable, render the numbered menu and stop.
- Do not generate, validate, or advance PrePlan artifacts until required answers are captured.
8. Persist accepted clarifications into `memory.md` and reflect them in `brainstorm.md` assumptions before downstream delegation.
9. Use `bmad-agent-analyst` for problem framing when the feature lacks product clarity.
10. Use `bmad-brainstorming` or the user-selected local ideation route to produce `brainstorm.md`.
11. Use the narrowest research skill for `research.md`: `bmad-domain-research`, `bmad-market-research`, or `bmad-technical-research`.
12. Use `bmad-product-brief` to produce `product-brief.md`.
13. Run an adversarial planning review with `bmad-review-adversarial-general` and record `preplan-adversarial-review.md`.
14. Validate artifacts:

```bash
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} validate-phase --feature-id {feature_id} --phase preplan
```

15. If validation passes, advance the local feature record:

```bash
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} advance-phase --feature-id {feature_id} --phase preplan
```

## Artifact Rules

- Write all phase artifacts under `docs/features/{feature_id}/`.
- Set artifact frontmatter `publication_state: draft` until reviewed and accepted.
- Preserve `stable_id`, `belongs_to`, `related_to`, Salmon signals, and source breadcrumbs.

## Next Action

After completion, route full-track features to `/businessplan`.