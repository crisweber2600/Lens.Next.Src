# Bottom-Up LENS Create Packet Headless Prompt

Headless mode creates a packet only from explicit JSON input and configured output roots. It must not ask the branch, open editor, or cwd/current working directory for identity, scope, topology, or phase.

## Required stage order

`context-intake` -> `candidate-selection` -> `local-sufficiency` -> `scope-boundary` -> `preview` -> `confirmation` -> `write` -> `receipt`

## Required gates

- Display explicit input context, `packet_output_path`, `reports_output_path`, and runtime write scope before planned writes.
- Compose exactly one selected candidate; block zero or multiple selections.
- Validate packet validity and BMAD readiness as separate results.
- Guard every planned write path against configured roots and denied categories.
- Require `--confirm` for write mode; without it, exit before writing.
- For dry-run, revise-equivalent, cancel-equivalent, duplicate, blocker, or failed verification paths, report that no accepted packet was written.
- Verify the receipt and run metadata before claiming accepted success.

## Standalone boundary

Do not import or activate Lens lifecycle runtime, governance publication, branch topology, constitution runtime, release clones, current NextLens top-down runtime, Landscape, Derived Graph, Salmon, promotion, adjacency, pressure, roadmap, or service/domain/program truth paths.
