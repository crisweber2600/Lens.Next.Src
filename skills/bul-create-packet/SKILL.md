---
name: bul-create-packet
description: Creates one safe Bottom-Up LENS feature packet from local context after preview and explicit confirmation. Use when the user asks to create a bottom-up feature packet or says "Start from one feature".
---

# Create Bottom-Up LENS Packet

## Purpose

Guides packet creation from local bottom-up context to one bounded feature packet. The router keeps prompt flow concise and delegates deterministic packet composition, validation, path guarding, atomic writes, receipt verification, duplicate handling, and safe resume behavior to scripts under `./scripts/`.

## Boundary

`bul-create-packet` is a standalone BMad workflow. It does not use Lens lifecycle commands, Lens governance `feature.yaml`, governance publish, Lens branch topology, Lens constitution runtime, release clones, current NextLens top-down runtime, Landscape, Derived Graph, Salmon, promotion, adjacency, pressure, roadmap, or service/domain/program truth paths.

## Inputs

- Raw local feature context or a source file path supplied explicitly.
- Configured `packet_output_path` and `reports_output_path`; do not infer them from branch, open editor, or cwd.
- Interactive confirmation token `CREATE PACKET` or headless `--confirm` before any accepted packet write.

## Outputs

- One packet JSON under configured `packet_output_path`.
- One receipt and run metadata under configured output roots.
- Optional reports under configured `reports_output_path`.

Dry-run, revise, cancel, duplicate, blocker, and interrupted/resumed paths must not claim an accepted packet result.

## Stage Order

The workflow routes through these exact stages:

1. `context-intake`
2. `candidate-selection`
3. `local-sufficiency`
4. `scope-boundary`
5. `preview`
6. `confirmation`
7. `write`
8. `receipt`

## On Activation

1. Ensure Bottom-Up LENS setup has registered module configuration.
2. Display explicit/module context, configured `packet_output_path`, configured `reports_output_path`, and runtime write scope before any write-capable step.
3. Stop and ask for explicit input when context resolution would rely on branch name, open editor, or cwd/current working directory.
4. Load `./prompts/create-guided.md` for interactive mode or `./prompts/create-headless.md` for headless mode.
5. Use `./scripts/create_packet.py`, `./scripts/path_guard.py`, `../bul-validate-packet/scripts/validate_packet.py`, and `../bul-verify-receipt/scripts/verify_receipt.py` for deterministic gates.
6. Stop instead of writing if sufficiency, scope, validation, path guard, confirmation, duplicate resolution, write, or receipt verification fails.

## Non-Effects Contract

Candidate identification, preview, dry-run, revise, cancel, validation, and blocker paths do not emit an accepted packet. Accepted packet writing requires explicit confirmation and must remain confined to configured output roots. Receipt verification must pass before success is claimed.
