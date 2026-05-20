---
name: bul-validate-packet
description: Validates Bottom-Up LENS packet structure and BMAD readiness without mutating source artifacts. Use when the user asks to validate a bottom-up feature packet.
---

# Validate Bottom-Up LENS Packet

## Purpose

Reads an existing Bottom-Up LENS packet or packet draft and reports packet validity separately from BMAD readiness using handwritten Python standard-library-first rules.

## Boundary

Validation is read-only for packet sources. It must not emit or repair packets, mutate source files, write governance artifacts, update Lens lifecycle state, publish to governance, alter release clones, mutate Landscape or Derived Graph state, route Salmon, or promote topology.

## Inputs

- `packet_source`: path to a packet JSON or draft artifact.
- Optional `reports_output_path` for future validation reports.

## Outputs

Validation returns JSON with `packetValid`, `bmadReady`, `hardBlockers`, and `advisories`. Optional reports may be written only under configured `reports_output_path`.

## On Activation

1. Load module configuration from Bottom-Up LENS setup.
2. Normalize the packet source path.
3. Run `./scripts/validate_packet.py`.
4. Report `packetValid` and `bmadReady` separately.
5. Preserve packet and source fixture bytes unchanged.

## Validation Route

MVP validation uses handwritten Python rules in `./scripts/validation_contract.py`; no `jsonschema` dependency is required or allowed for this MVP. A future `jsonschema` interoperability layer may be considered only after handwritten validation passes the fixture suite.

Rule categories include schema version, source mode, identity, selected feature, scope, constraints, assumptions, provenance, receipt reference, topology, and non-effects requirements.

Human-readable labels are exact:

- `Feature packet is valid`
- `Feature packet is not ready yet`
- `Ready for BMAD: not yet`
- `Ready for BMAD: ready`
