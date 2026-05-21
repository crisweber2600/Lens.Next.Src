---
name: lens-dev
description: NextLens Dev phase. Use when the user requests dev, /dev, story implementation, or sprint execution for a finalized feature.
---

# Lens Dev

## Overview

Dev executes finalized story work against configured target repositories while keeping lifecycle state in the local feature archive. It consumes `sprint-status.yaml` and `stories/*.md`, delegates story implementation to local BMAD dev skills, records `dev-session.yaml`, and leaves topology/reporting closeout to Lens doctor, projection, promotion, Salmon, and reporting workflows.

## On Activation

1. Resolve `{feature_id}` and run `suggest-next`; stop unless `dev` is unblocked or active.
2. Resolve constitution before implementation:

```bash
python skills/lens-constitution/scripts/constitution_ops.py resolve --project-root {project-root} --feature-id {feature_id}
python skills/lens-constitution/scripts/constitution_ops.py progressive-display --project-root {project-root} --feature-id {feature_id}
python skills/lens-constitution/scripts/constitution_ops.py check-compliance --project-root {project-root} --feature-id {feature_id} --phase dev
```

3. Stop immediately if constitution resolution fails, if the resolved gate mode is hard and the track is not permitted, or if the resolved constitution identifies a hard-gate requirement the planned implementation would violate. Surface the applicable hard-gate rules and carry the combined constitution prose into every downstream story implementation delegation.
4. Validate dev entry:

```bash
python skills/lens-lifecycle/scripts/lifecycle_ops.py --project-root {project-root} validate-phase --feature-id {feature_id} --phase dev
```

5. Read `feature.yaml.target_repos`; if absent, stop and ask for the target repo path instead of guessing from the workspace.
6. Verify the selected target repo exists and is not the feature archive, `skills/`, generated reports, or any release-module folder.
7. Parse `sprint-status.yaml` and story files. Build the ready queue from stories not marked complete, blocked, or failed in `dev-session.yaml`.
8. For each ready story:
   - Mark the story `in-progress` in `dev-session.yaml`.
   - Use `bmad-dev-story` for story-scoped implementation, or `bmad-quick-dev` only when the story explicitly says quick-dev is acceptable.
   - Run the narrowest available validation for changed target-repo files.
   - Update story status and checkpoint results in `dev-session.yaml`.
9. When all required stories are done, run `bmad-code-review` over the target repo changes and record `dev-adversarial-review.md` in the feature archive.
10. Advance the local feature record with `advance-phase --phase dev` after dev validation passes.

## Write Boundaries

- Planning and lifecycle state writes stay under `docs/features/{feature_id}/`.
- Implementation writes go only to configured target repos.
- Generated reports stay under configured reporting output paths.
- Do not write to release-module folders or external governance mirrors.

## Closeout

After Dev completes, route to `lens-doctor`, `lens-projection-rebuild`, `lens-ledger-promotion`, `lens-salmon-impact` when signaled, and `lens-reporting-snapshot`.