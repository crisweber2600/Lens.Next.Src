---
name: bul-create-packet
description: Creates one safe Bottom-Up LENS feature packet from local context after preview and explicit confirmation. Use when the user asks to create a bottom-up feature packet.
---

# Create Bottom-Up LENS Packet

## Purpose

Guides packet creation from local bottom-up context to one bounded feature packet. The workflow is scaffolded here; packet composition, validation, path guard, atomic write, receipt generation, and run metadata are implemented by later stories.

## Boundary

`bul-create-packet` is a standalone BMad workflow. It does not use Lens lifecycle commands, Lens governance `feature.yaml`, governance publish, Lens branch topology, Lens constitution runtime, release clones, current NextLens top-down runtime, Landscape, Derived Graph, Salmon, promotion, adjacency, pressure, roadmap, or service/domain/program truth paths.

## Inputs

- Raw local feature context or a source file path.
- Optional output root overrides from module config.
- Explicit confirmation before any accepted packet write.

## Outputs

Future stories will produce:

- One packet JSON under configured `packet_output_path`.
- One receipt and run metadata under configured output roots.
- Optional reports under configured `reports_output_path`.

This scaffold story produces no packet behavior beyond routing and boundary text.

## On Activation

1. Ensure Bottom-Up LENS setup has registered module configuration.
2. Display configured `packet_output_path` and `reports_output_path` before any write-capable step.
3. Load the relevant prompt from `./prompts/` when create behavior is implemented.
4. Use deterministic scripts for validation and writes when those scripts are added.
5. Stop instead of writing if confirmation, sufficiency, path guard, or validation is missing.

## Non-Effects Contract

Candidate identification, preview, and validation do not emit a packet. Accepted packet writing requires explicit confirmation and must remain confined to configured output roots.
