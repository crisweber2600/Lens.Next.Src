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

Verification returns structured JSON with `status`, `runValid`, checked-file summaries, `hardBlockers`, and the labels `Non-effects verified` or `Receipt mismatch detected`. Optional reports may be written only under configured `reports_output_path`.

## On Activation

1. Load module configuration from Bottom-Up LENS setup.
2. Normalize receipt and metadata paths.
3. Run `./scripts/verify_receipt.py`.
4. Fail closed on missing metadata, forbidden writes, or claims that conflict with observed changes.
5. Preserve input artifacts unchanged.

## Verification Route

The verifier compares `writtenFiles`, `changedFiles`, and `nonEffects` claims against run metadata and denied path categories. False claims, missing metadata, governance/topology/runtime/release path changes, and report paths outside `reports_output_path` are hard failures.
