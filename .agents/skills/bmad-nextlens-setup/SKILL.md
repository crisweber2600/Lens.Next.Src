---
name: bmad-nextlens-setup
description: Sets up the NextLens Top-Down Bridge module in a project. Use when the user requests to install, configure, or refresh NextLens module registration.
---

# NextLens Setup

## Overview

Installs or refreshes the NextLens Top-Down Bridge as a multi-skill BMad module. Module identity, configuration variables, and registered capabilities come from `./assets/module.yaml` and `./assets/module-help.csv`.

Setup writes or refreshes three project files:

- `{project-root}/_bmad/config.yaml` for shared project settings and the `nxl` module section
- `{project-root}/_bmad/config.user.yaml` for user-only settings when collected
- `{project-root}/_bmad/module-help.csv` for the NextLens setup, new, doctor, and salmon help entries

Both merge scripts use anti-zombie replacement so stale NextLens rows and config values do not remain after reconfiguration.

## On Activation

1. Read `./assets/module.yaml` for module metadata and defaults.
2. Check whether `{project-root}/_bmad/config.yaml` already contains an `nxl` section. If it does, treat this as an update.
3. If the user supplied inline setup values or asked to accept defaults, map them to the module keys and skip extra prompting.
4. Otherwise, collect the module configuration values in one concise prompt.

## Configuration

Default module values:

- `nextlens_docs_path`: `{project-root}/docs`
- `nextlens_landscape_store`: `{project-root}/docs/landscape`
- `nextlens_idempotency_ttl_hours`: `24`

Keep `{project-root}` as a literal token in stored config values. Resolve it to an actual path only when creating directories on disk.

## Write Files

Write a temporary JSON answers file shaped like this:

```json
{
  "module": {
    "nextlens_docs_path": "{project-root}/docs",
    "nextlens_landscape_store": "{project-root}/docs/landscape",
    "nextlens_idempotency_ttl_hours": 24
  }
}
```

Then run from this skill directory:

```bash
python ./scripts/merge-config.py --config-path "{project-root}/_bmad/config.yaml" --user-config-path "{project-root}/_bmad/config.user.yaml" --module-yaml ./assets/module.yaml --answers "{answers-file}" --legacy-dir "{project-root}/_bmad"
python ./scripts/merge-help-csv.py --target "{project-root}/_bmad/module-help.csv" --source ./assets/module-help.csv --legacy-dir "{project-root}/_bmad" --module-code nxl
```

After the scripts succeed, create directories from `directories` in `module.yaml`, resolving placeholders from the stored config values.

## Confirm

Summarize the written config section, user settings if any, help entries registered, and any legacy files removed. Then display the `module_greeting` from `./assets/module.yaml`.