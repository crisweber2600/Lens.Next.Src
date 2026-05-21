---
name: ausx-reporting-snapshot
description: Creates read-only stakeholder snapshots. Use when the user requests 'ausx reporting snapshot', 'create Auspex snapshot', or 'stakeholder status report'.
---

# Auspex Reporting Snapshot

## Overview

This skill produces read-only stakeholder visibility artifacts from Auspex feature archives, living ledgers, map audits, promotion reports, Salmon reports, and topology decisions. Act as a reporting analyst: summarize status without modifying source truth, and shape the output for both human review and future Auspex UI ingestion.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, `{project-root}/_bmad/config.toml`, and `{project-root}/_bmad/config.user.toml`, checking both root values and the `ausx` or `modules.ausx` section. If config is missing, let the user know `ausx-setup` can configure Auspex at any time. Use these defaults:

- `feature_archive_path`: `{project-root}/docs/features`
- `landscape_root`: `{project-root}/docs`
- `reporting_output_path`: `{project-root}/_bmad-output/auspex`
- `freshness_threshold_hours`: `24`

Support interactive and headless use. In headless mode, create Markdown and JSON snapshots from configured paths and return JSON with `status`, `markdown_path`, `json_path`, `blocking_count`, and `advisory_count`.

## Read-Only Contract

This workflow never writes to feature archives, ledgers, topology decisions, or prior reports. Its only outputs are snapshot artifacts under `reporting_output_path` or a user-specified reporting directory.

Snapshots are not source truth. They are time-bound views for stakeholders and future Auspex UI ingestion.

## Inputs

Use the latest relevant artifacts unless the user pins specific paths:

- Feature archives under `feature_archive_path`
- Living ledgers under `landscape_root`
- Recent `map-audit-*`, `ledger-promotion-*`, `salmon-impact-*`, and `topology-decision-*` reports under `reporting_output_path`
- Existing snapshot JSON only for trend comparison, never as current truth

If audit or impact reports are older than `freshness_threshold_hours`, mark freshness as advisory. If blocking findings exist in the latest audit or Salmon report, carry them forward as blocking snapshot risks.

## Workflow

Identify the audience and reporting horizon. Default to an executive stakeholder snapshot with sections for overall health, completed features, unpromoted knowledge, topology risks, upstream-impact risks, freshness, and next actions.

Read current source artifacts directly before summarizing. Use prior reports to avoid redoing all classification work, but do not rely on a stale report when source files have changed or the user provides a newer scope.

Write:

- `{reporting_output_path}/snapshot-{date}.md`
- `{reporting_output_path}/snapshot-{date}.json`

The Markdown should be concise and reviewable. The JSON should be stable enough for a future Auspex UI to ingest.

## Snapshot Contract

The Markdown report must include:

- Timestamp, scope, audience, and source paths
- Overall status: `GREEN`, `YELLOW`, or `RED`
- Blocking inconsistencies separated from advisory findings
- Completed features and unpromoted feature knowledge
- Ledger health and topology health
- Salmon upstream-impact status
- Freshness summary
- Recommended next actions, each tied to a source artifact

The JSON artifact must include:

```json
{
  "module": "ausx",
  "report_type": "reporting_snapshot",
  "created_at": "",
  "scope": "",
  "overall_status": "YELLOW",
  "blocking": [],
  "advisory": [],
  "features": [],
  "ledgers": [],
  "salmon_impacts": [],
  "freshness": {}
}
```

## Safety Rules

Never hide blocking inconsistencies in an executive summary. Summaries can be concise, but they must preserve the distinction between advisory cleanup and decisions that should block publication, promotion, or projection rebuilds.

