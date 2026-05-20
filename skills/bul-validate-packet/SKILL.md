---
name: bul-validate-packet
description: Validates Bottom-Up LENS packet structure and BMAD readiness without mutating source artifacts. Use when the user asks to validate a bottom-up feature packet.
---

# Validate Bottom-Up LENS Packet

## Purpose

Reads an existing Bottom-Up LENS packet or packet draft and reports packet validity separately from BMAD readiness.

## Boundary

Validation is read-only for packet sources. It must not emit or repair packets, mutate source files, write governance artifacts, update Lens lifecycle state, publish to governance, alter release clones, mutate Landscape or Derived Graph state, route Salmon, or promote topology.

## Inputs

- `packet_source`: path to a packet JSON or draft artifact.
- Optional `reports_output_path` for future validation reports.

## Outputs

Future stories will return structured validation results and optional report artifacts under `reports_output_path`. This scaffold only defines the contract.

## On Activation

1. Load module configuration from Bottom-Up LENS setup.
2. Normalize the packet source path.
3. Run deterministic validation scripts once they are implemented.
4. Report `packet_valid` and `bmad_ready` separately.
5. Preserve packet and source fixture bytes unchanged.

## Future Validation Route

Later stories add handwritten Python validation for schema version, required fields, source mode, no topology promotion, no forbidden paths, and BMAD readiness reasons.
