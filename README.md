# Bottom-Up LENS

Bottom-Up LENS is a standalone BMad module for safely creating one bounded feature packet from local bottom-up context. It packages setup, packet creation, packet validation, and receipt verification as separate BMad skills.

## Module Boundary

This module is not Lens governance behavior. It does not require or write Lens `feature.yaml`, governance publish artifacts, control-repo branch topology, Lens constitution state, release clones, Landscape, Derived Graph, Salmon, promotion, adjacency, pressure, roadmap, or service/domain/program truth paths.

Runtime packet creation may write only under configured `packet_output_path` and `reports_output_path` roots after explicit confirmation. Validation and receipt verification are read-only unless a later story explicitly adds report emission under `reports_output_path`.

## Initial Skill Set

- `bul-setup`: registers module configuration and help discovery.
- `bul-create-packet`: guided/headless workflow placeholder for packet creation.
- `bul-validate-packet`: read-only packet validation placeholder.
- `bul-verify-receipt`: read-only receipt verification placeholder.

## Distribution Skeleton

The repository contains the BMad custom module surfaces expected by BMad Builder guidance:

- `.claude-plugin/marketplace.json`
- `skills/bul-setup/assets/module.yaml`
- `skills/bul-setup/assets/module-help.csv`
- `skills/bul-*/SKILL.md`
- `evals/bul-*` placeholder suites

Implementation is intentionally scaffold-only in the first story. Packet validation, path guards, receipts, atomic writes, and eval content are implemented by later stories.
