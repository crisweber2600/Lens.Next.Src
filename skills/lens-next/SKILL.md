---
name: lens-next
description: NextLens clean-room lifecycle router. Use when the user requests next, /next, or asks what lifecycle command should run now.
---

# Lens Next

## Overview

This skill routes a local NextLens feature to its next lifecycle command. It reads `docs/features/<feature-id>/feature.yaml`, uses the local `lens-lifecycle` engine, and either reports blockers or loads the recommended local phase skill. It does not route through release-module commands or external governance state.

## On Activation

1. Resolve `{feature_id}` from explicit user input, `docs/features/<feature-id>/feature.yaml`, or the active work archive named by the user. If missing, ask once for the feature ID.
2. Run:

```bash
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} suggest-next --feature-id {feature_id}
```

3. If status is `blocked`, show the predecessor and missing artifact details, then stop.
4. If status is `complete`, route to `lens-doctor`, `lens-projection-rebuild`, `lens-ledger-promotion`, `lens-salmon-impact`, or `lens-reporting-snapshot` based on the user's goal.
5. If status is `unblocked`, load the local skill for `recommendation`:
   - `preplan` -> `skills/lens-preplan/SKILL.md`
   - `businessplan` -> `skills/lens-businessplan/SKILL.md`
   - `techplan` -> `skills/lens-techplan/SKILL.md`
   - `expressplan` -> `skills/lens-expressplan/SKILL.md`
   - `finalizeplan` -> `skills/lens-finalizeplan/SKILL.md`
   - `dev` -> `skills/lens-dev/SKILL.md`

## Safety Rules

- Do not infer feature identity from branch name.
- Do not create planning branches.
- Do not invoke release-module lifecycle commands.
- Do not advance phase state from this router; phase skills own advancement after validation.