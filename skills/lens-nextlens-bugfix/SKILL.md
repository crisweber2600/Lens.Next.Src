---
name: lens-nextlens-bugfix
description: Canonical NextLens clean-room bugfix conductor with bounded writes and governed closeout.
---

# Lens NextLens Bugfix

## Overview

This command captures one NextLens runtime bug, creates a namespaced bug artifact, prepares a fresh bugfix branch, performs bounded implementation, and enforces closeout evidence before reporting success.

## Required Inputs

Collect all required fields before mutation:

- `what_happened`
- `what_should_have_happened`
- `chat_history`

If any required field is missing, request only missing fields and stop.

## Execution Contract

1. Run `lens-preflight` first through the wrapper gate. Stop on non-zero status.
2. Use the conductor prepare gate to generate deterministic state and branch context:

```bash
python skills/lens-nextlens-bugfix/scripts/nextlens_bugfix_conductor.py prepare \
  --project-root {project-root} \
  --feature-id {feature_id} \
  --what-happened "{what_happened}" \
  --what-should-have-happened "{what_should_have_happened}" \
  --chat-history "{chat_history}"
```

This returns `bug_slug`, `working_branch`, `base_branch`, `starting_head`, and `allowed_write_root`.
3. Build deterministic fix spec:

```bash
python skills/lens-nextlens-bugfix/scripts/nextlens_fix_spec.py \
  --project-root {project-root} \
  --what-happened "{what_happened}" \
  --what-should-have-happened "{what_should_have_happened}" \
  --chat-history "{chat_history}"
```

4. Stop if `delegation_blocked` is true.
5. Create bug artifact in `Open` state:

```bash
python skills/lens-nextlens-bugfix/scripts/bug_reporter_ops.py create-bug \
  --project-root {project-root} \
  --feature-id {feature_id} \
  --slug {bug_slug} \
  --title "{bug_reporter_fields.title}" \
  --what-happened "{what_happened}" \
  --what-should-have-happened "{what_should_have_happened}" \
  --chat-history "{chat_history}" \
  --namespace nextlens
```

6. Prepare branch in `TargetProjects/lens.next.src`:

- Hard stop on dirty working tree.
- Checkout/create `feature/nextlens-bugfix-{bug_slug}`.
- Capture `starting_head` immediately after branch prep.

7. Delegate bounded implementation with these non-negotiables:

- Edit only inside `{allowed_write_root}`.
- Stop with `target_boundary_violation` on any out-of-root path.
- Run focused validation for touched files.
- Create one implementation commit.
- Do not push, create PR, close bug, or report final success.

8. Conductor completion gate:

- Branch must still be `working_branch`.
- Worktree must be clean.
- Final `HEAD` must differ from `starting_head`.
- Changed files since `starting_head` must be non-empty.
- All changed files must stay under `{allowed_write_root}`.
- Push branch.
- Create or reuse PR and capture `PR URL`.

Run close gate after implementation returns:

```bash
python skills/lens-nextlens-bugfix/scripts/nextlens_bugfix_conductor.py close \
  --project-root {project-root} \
  --bug-slug {bug_slug} \
  --working-branch {working_branch} \
  --base-branch {base_branch} \
  --starting-head {starting_head} \
  --allowed-write-root {allowed_write_root} \
  --summary "{concise_change_summary}" \
  --validation-summary "{validation_summary}" \
  --doctor-status {doctor_status} \
  --doctor-evidence "{doctor_output_reference}" \
  --doctor-rationale "{doctor_rationale}"
```

9. Record PR URL and close bug artifact:

```bash
python skills/lens-nextlens-bugfix/scripts/bug_reporter_ops.py record-quickdev-pr \
  --project-root {project-root} \
  --slug {bug_slug} \
  --pr-url "{pr_url}" \
  --namespace nextlens

python skills/lens-nextlens-bugfix/scripts/bug_reporter_ops.py close-quickdev-bug \
  --project-root {project-root} \
  --slug {bug_slug} \
  --summary "{concise_change_summary}" \
  --validation-summary "{validation_summary}" \
  --namespace nextlens \
  --doctor-status {doctor_status} \
  --doctor-evidence "{doctor_output_reference}" \
  --doctor-rationale "{doctor_rationale}"
```

10. Stop if Doctor evidence is missing. Allowed alternatives:

- `doctor_status=not-applicable` with rationale.
- `doctor_status=deferred` with rationale.

## Output Contract

Return only after all are non-empty:

- `bug_artifact_path`
- `bug_slug`
- `working_branch`
- `base_branch`
- `commit_hash`
- `PR URL`
- concise validation summary
- changed-files summary scoped to `TargetProjects/lens.next.src`
- Doctor evidence reference or rationale

## Safety Rules

- Never mutate files outside `TargetProjects/lens.next.src`.
- Never auto-clean a dirty working tree.
- Never report success if any completion gate fails.
