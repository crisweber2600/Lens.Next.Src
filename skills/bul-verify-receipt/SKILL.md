---
name: bul-verify-receipt
description: Verifies Bottom-Up LENS receipt and run metadata claims without mutating source artifacts. Use when the user asks to verify packet receipt or non-effects claims.
---

# Verify Bottom-Up LENS Receipt

## Purpose

Checks whether a Bottom-Up LENS receipt and run metadata truthfully describe the files written and the side effects not emitted.

## Boundary

Receipt verification is read-only for receipts, run metadata, packet artifacts, and observed changed-file manifests. It must not repair receipts, update packets, write governance artifacts, alter Lens lifecycle state, mutate Landscape or Derived Graph state, route Salmon, promote topology, or write outside configured report roots.

## Inputs

- `receipt_source`: receipt JSON path.
- `run_metadata_source`: run metadata path.
- Optional changed-file manifest path.

## Outputs

Future stories will return structured verification results and optional report artifacts under `reports_output_path`. This scaffold only defines the contract.

## On Activation

1. Load module configuration from Bottom-Up LENS setup.
2. Normalize receipt and metadata paths.
3. Run deterministic verification scripts once they are implemented.
4. Fail closed on missing metadata, forbidden writes, or claims that conflict with observed changes.
5. Preserve input artifacts unchanged.

## Future Validation Route

Later stories add Python verification of changed files, forbidden surfaces, claimed writes, schema version, timestamps, and non-effects booleans.
