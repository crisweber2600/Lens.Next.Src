---
name: bmad-nextlens
description: Shared internal runtime bundle for NextLens workflow skills. Not intended for direct user invocation.
---

# NextLens Shared Runtime

This directory packages the shared Python runtime used by:

- `bmad-nextlens-new`
- `bmad-nextlens-doctor`
- `bmad-nextlens-validate`
- `bmad-nextlens-salmon`

It exists so installed module checkouts can resolve the shared implementation under `./scripts/`.

Do not invoke this skill directly. Use the user-facing workflow skills instead.

## Lifecycle Split

- `/bmad-nextlens-new`: discovery/context intake → candidate selection → Feature packet emission → BMAD handoff artifacts → initial evidence bundle.
- `/bmad-nextlens-doctor`: non-mutating validation of Feature packets, BMAD handoff refs, and downstream artifacts.
- `/bmad-nextlens-salmon`: routes correction findings through impact mapping and deduplication.
- `/bmad-nextlens-validate`: post-BMAD artifacts/stories/evidence → validation result → Salmon when required → Landscape proposal by default or apply when explicitly requested → evidence bundle update.

The Living Landscape is authoritative. Derived Graph output is always a non-authoritative projection, and Feature work must not auto-promote into Capability, Domain, or System hierarchy.
