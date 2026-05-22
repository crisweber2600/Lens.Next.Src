---
description: NextLens clean-room bugfix intake surface.
mode: agent
---

# /nextlens-bugfix

FIRST, run the preflight gate from the workspace root:

```bash
python skills/lens-nextlens-bugfix/scripts/light_preflight.py --caller nextlens-bugfix
```

If that command exits non-zero, stop and surface the failure. Do not proceed.

ONLY AFTER a successful prompt-start sync, load and follow:

`skills/lens-nextlens-bugfix/SKILL.md`

When asked for user input, use `vscode_askQuestions` if available.
If `vscode_askQuestions` is not available, render the numbered menu and STOP.
