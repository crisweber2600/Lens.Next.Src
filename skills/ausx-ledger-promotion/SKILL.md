---
name: ausx-ledger-promotion
description: Promotes feature knowledge into ledgers. Use when the user requests 'ausx ledger promotion', 'promote feature to ledger', or 'update living ledgers'.
---

# Auspex Ledger Promotion

## Overview

This skill promotes completed LENS/BMAD feature knowledge into living service, domain, or program ledgers without erasing the permanent feature archive. Act as a knowledge steward: preserve provenance, surface conflicts before edits, and produce a promotion report that explains what moved, what stayed, and what still blocks promotion.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, `{project-root}/_bmad/config.toml`, and `{project-root}/_bmad/config.user.toml`, checking both root values and the `ausx` or `modules.ausx` section. If config is missing, let the user know `ausx-setup` can configure Auspex at any time. Use these defaults:

- `feature_archive_path`: `{project-root}/docs/features`
- `landscape_root`: `{project-root}/docs`
- `reporting_output_path`: `{project-root}/_bmad-output/auspex`
- `freshness_threshold_hours`: `24`

Support interactive and headless use. In headless mode, produce a promotion plan and report only unless the user explicitly passed an apply instruction such as `--apply`.

## Promotion Contract

The feature archive remains the immutable record of delivery history. The living ledger is the current operational truth for service/domain/program knowledge. Promotion copies or synthesizes durable knowledge from completed features into the right ledger while preserving `source_feature` references and stable IDs.

Promotion candidates usually have `status: completed`, `status: done`, an accepted story closeout, or a completion note in `{feature_archive_path}/<feature-id>/`. Skip drafts, in-progress work, and already-promoted records unless the user explicitly asks for a re-promotion review.

## Classification

Classify findings as:

- **Blocking:** feature has no stable ID, no resolvable ledger target, conflicting parent reference, duplicate entity identity, contradiction with a newer ledger entry, unclear source of truth, or missing user approval for write-back.
- **Advisory:** ledger target is clear but metadata is incomplete, promotion is overdue, source breadcrumbs are weak, or the ledger update is non-controversial but would benefit from cleanup.

When a completed feature has clear durable knowledge but no matching ledger, recommend a new ledger path using the Two-Tree topology instead of writing to an arbitrary location.

## Workflow

Start by identifying the feature scope: one feature folder, all completed unpromoted features, or a specific service/domain/program ledger. If there is no recent map audit, recommend running `ausx-map-audit` first; continue only when the user accepts the risk or the scope is narrow enough to verify inline.

Read the feature archive and target ledger before proposing edits. Compare stable IDs, parent references, current ledger content, and source feature breadcrumbs. Build a promotion plan that separates direct ledger updates, new ledger entries, deferred items, and blocked items.

For interactive runs, show the promotion plan before editing source files. For headless runs without `--apply`, do not edit source files. When applying changes, keep edits tightly scoped to ledger files under `landscape_root`; never rewrite feature archives except to add a user-approved promotion marker.

Write `{reporting_output_path}/ledger-promotion-{feature-id-or-scope}-{date}.md`.

## Report Contract

The report must include:

- Scope, selected feature archives, target ledger paths, and timestamp
- Promotion verdict: `APPLIED`, `PLANNED`, `PARTIAL`, or `BLOCKED`
- Ledger updates applied or proposed, with stable IDs and source features
- Blocking findings and advisory findings in separate tables
- Deferred items with owner/action recommendations
- Source files read and files modified, if any
- Machine-readable summary block:

```json
{
  "module": "ausx",
  "report_type": "ledger_promotion",
  "scope": "",
  "applied": false,
  "blocking_count": 0,
  "advisory_count": 0,
  "files_modified": []
}
```

## Safety Rules

Do not flatten feature history into the ledger. Preserve traceability by adding `source_feature` or equivalent provenance on every promoted entry. If a ledger update would change published topology, stop and route the user to `ausx-topology-design` or `ausx-salmon-impact` as appropriate.

