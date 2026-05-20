# Bottom-Up LENS Create Packet Guided Prompt

Use this prompt when the operator says "Start from one feature" or asks to create a Bottom-Up LENS packet interactively.

## Required stage order

1. `context-intake`
2. `candidate-selection`
3. `local-sufficiency`
4. `scope-boundary`
5. `preview`
6. `confirmation`
7. `write`
8. `receipt`

## Context display gate

At `context-intake`, display:

- explicit context source supplied by the operator
- module context and configured output roots
- `packet_output_path`
- `reports_output_path`
- runtime write scope: packet JSON, run metadata JSON, receipt JSON, and optional reports only under configured roots

Block if identity, scope, feature choice, or output roots would rely on branch name, open editor, or cwd/current working directory inference.

## Candidate and sufficiency gates

At `candidate-selection`, present unranked candidates and require exactly one selection. Deferred candidates remain unranked notes only.

At `local-sufficiency` and `scope-boundary`, require actor/user, problem, useful local outcome, acceptance criteria, constraints, assumptions, included scope, explicit out-of-scope, provenance, and anti-inference handoff instructions.

## Preview and confirmation

At `preview`, render selected feature, included scope, explicit out-of-scope, assumptions, acceptance criteria, constraints, provenance, intended write target, packet validity, BMAD readiness, and non-effects checklist. Support dry-run, revise, and cancel with no accepted packet write.

At `confirmation`, require the exact token `CREATE PACKET`. Pressing Enter or any other token must not write.

## Standalone boundary

Never invoke Lens governance, Lens topology, current NextLens top-down runtime, Landscape, Graph, Salmon, promotion, adjacency, pressure, roadmap, release clone, service/domain/program truth, or `feature.yaml` behavior.
