---
name: bmad-nextlens
description: Shared internal runtime bundle for NextLens workflow skills. Not intended for direct user invocation.
---

# NextLens Shared Runtime

This directory packages the shared Python runtime used by:

- `bmad-nextlens-new`
- `bmad-nextlens-doctor`
- `bmad-nextlens-salmon`

It exists so installed module checkouts can resolve the shared implementation under `./scripts/`.

Do not invoke this skill directly. Use the user-facing workflow skills instead.