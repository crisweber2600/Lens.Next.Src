# Bottom-Up LENS Commands

## `bul-setup`

Registers Bottom-Up LENS configuration and help entries.

Default roots:

- `packet_output_path`: `{project-root}/docs/bottom-up-lens`
- `reports_output_path`: `{project-root}/_bmad-output/bottom-up-lens`
- `default_packet_schema_version`: `bul.feature-packet.v1`

Setup writes only BMad setup-owned config/help files in a consuming project.

## `bul-create-packet`

Use this for: "Start from one feature".

Stages: `context-intake`, `candidate-selection`, `local-sufficiency`, `scope-boundary`, `preview`, `confirmation`, `write`, `receipt`.

Interactive writes require the exact token `CREATE PACKET`. Headless writes require `--confirm`. Dry-run, revise, cancel, duplicate, blocker, and failed-verification exits write no accepted packet result.

## `bul-validate-packet`

Validates a packet or draft without mutating it. Output separates:

- `Feature packet is valid` / `Feature packet is not ready yet`
- `Ready for BMAD: ready` / `Ready for BMAD: not yet`

Optional reports are allowed only under `reports_output_path`.

## `bul-verify-receipt`

Verifies receipt and run metadata claims without mutating inputs. Output labels:

- `Non-effects verified`
- `Receipt mismatch detected`

Optional reports are allowed only under `reports_output_path`.

## Standalone boundary

Bottom-Up LENS does not publish governance, create Lens branches, enforce Lens constitution runtime, write release clones, depend on current NextLens top-down runtime modules, write Landscape/Derived Graph/Salmon/promotion/adjacency/pressure/roadmap outputs, or update service/domain/program truth paths.
