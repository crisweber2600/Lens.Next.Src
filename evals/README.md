# Bottom-Up LENS Evals

These eval definitions are JSON artifacts that can be consumed by a BMad eval runner or checked by unit tests.

## Artifact evals

- `bul-create-packet/evals.json` asserts create dry-run, fail-closed missing confirmation, and confirmed packet/metadata/receipt writes.
- `bul-validate-packet/evals.json` asserts packet validity, BMAD readiness separation, and invalid candidate failures.
- `bul-verify-receipt/evals.json` asserts valid non-effects verification and false receipt failures.

## Trigger evals

`bul-create-packet/triggers.json` includes positive Bottom-Up LENS prompts and negative Lens lifecycle prompts. Negative prompts include feature initialization, governance publish, constitution resolution, branch topology work, and current top-down runtime requests.

All evals must avoid governance repos, release clones, current top-down runtime modules, and Lens lifecycle runtime dependencies.
