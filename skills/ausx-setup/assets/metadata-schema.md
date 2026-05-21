# Auspex Metadata Contract

This contract defines the frontmatter Auspex workflows read from authored project artifacts. Authored artifacts live in the work/feature archive or the living landscape. Generated projections are derived views and must not become source truth.

## Entity Types

| Type | Stable ID Prefix | Authored Location | Parent Rule |
| ---- | ---------------- | ----------------- | ----------- |
| `program` | `program:` | `{landscape_root}/<program>/ledger/program.md` | no parent required |
| `domain` | `domain:` | `{landscape_root}/<program>/<domain>/ledger/domain.md` | `belongs_to` should reference a `program:` ID |
| `service` | `service:` | `{landscape_root}/<program>/<domain>/<service>/ledger/service.md` | `belongs_to` should reference a `domain:` ID |
| `feature` | `feature:` | `{work_intake_path}/<work-id>/work.md` or `{feature_archive_path}/<feature-id>/feature.md` | `belongs_to` should reference a `service:`, `domain:`, or `program:` ID when known |
| `projection` | `projection:` | `{reporting_output_path}/governance-map.*` | derived; no authored parent |

## Core Fields

| Field | Required | Applies To | Meaning |
| ----- | -------- | ---------- | ------- |
| `stable_id` | yes | all governed authored entities | Stable identity that survives file moves. Prefix must match `entity_type`. |
| `entity_type` | yes | all governed authored entities | One of `program`, `domain`, `service`, `feature`, or `projection`. |
| `title` | yes | all governed authored entities | Human-readable name. |
| `belongs_to` | conditional | domain, service, feature | Parent stable ID. Use `unknown` only for intake or draft work that is not projection-ready. |
| `status` | yes | authored entities | Delivery or knowledge lifecycle, such as `intake`, `in_progress`, `completed`, `promoted`, `active`, `retired`. |
| `publication_state` | yes | authored entities | Projection participation state: `draft`, `published`, or `retired`. |
| `updated_at` | yes | authored entities | ISO date or timestamp used for freshness checks. |

## Work And Feature Fields

| Field | Required | Meaning |
| ----- | -------- | ------- |
| `work_id` | yes for work archives | Kebab-case work archive folder name. |
| `lifecycle_stage` | yes for work archives | Current Lens/BMad lifecycle stage. |
| `source_feature` | optional | Stable ID or path that this work came from. |
| `related_to` | optional | Stable IDs for related work or features. |
| `extends` | optional | Stable IDs this work extends. |
| `replaces` | optional | Stable IDs this work supersedes. |
| `promotion_status` | optional | `not_started`, `planned`, `promoted`, or `blocked`. |
| `salmon_upstream` | optional | Boolean signal that downstream evidence may affect upstream truth. |
| `links` | optional | Local paths or stable IDs this artifact depends on or references. |

## Publication Semantics

`status` tracks lifecycle. `publication_state` controls whether the artifact participates in published projections.

- `draft`: inspectable during doctor runs but excluded from published projections unless `--include-drafts` is explicit.
- `published`: included in doctor checks, projection rebuilds, reporting snapshots, and promotion decisions.
- `retired`: retained for history and traceability; excluded from current projections unless the user explicitly requests retired entities.

Do not use branches as the source of planning isolation. Planning state belongs in `publication_state`, with all decisions visible in files.

## Blocking Conditions

Auspex doctor, map audit, and projection rebuild treat these as blocking for published projections:

- Missing `stable_id`, `entity_type`, `title`, `status`, `publication_state`, or `updated_at`.
- `stable_id` prefix does not match `entity_type`.
- Duplicate published `stable_id` values.
- `belongs_to` is missing, `unknown`, broken, cyclic, or points to an invalid parent type.
- Broken local Markdown links.
- Published feature completion has no resolvable ledger target when promotion is required.

Draft artifacts may carry incomplete parentage, but doctor reports must surface those gaps as draft advisories.