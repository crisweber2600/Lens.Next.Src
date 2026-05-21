---
name: ausx-salmon-impact
description: Reviews upstream Salmon impacts. Use when the user requests 'ausx salmon impact', 'review upstream impact', or 'trace recursive consistency'.
---

# Auspex Salmon Impact

## Overview

This skill reviews Salmon upstream-impact signals: changes discovered downstream that need to swim back through service, domain, and program knowledge. Act as a recursive consistency reviewer. Your output is an impact report that separates advisory refreshes from blocking contradictions before teams promote or publish updated truth.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, `{project-root}/_bmad/config.toml`, and `{project-root}/_bmad/config.user.toml`, checking both root values and the `ausx` or `modules.ausx` section. If config is missing, let the user know `ausx-setup` can configure Auspex at any time. Use these defaults:

- `feature_archive_path`: `{project-root}/docs/features`
- `landscape_root`: `{project-root}/docs`
- `reporting_output_path`: `{project-root}/_bmad-output/auspex`
- `freshness_threshold_hours`: `24`

Support interactive and headless use. In headless mode, inspect explicit paths or configured defaults, write the impact report, and return JSON with `status`, `report_path`, `blocking_count`, and `advisory_count`.

## Salmon Signals

Treat any of these as an upstream-impact signal: `salmon_upstream: true`, `impact: upstream`, `upstream_impact`, `UPSTREAM IMPACT`, an explicit user request, or a feature/ledger note saying a downstream finding changes parent assumptions.

The review follows `belongs_to` and local references from the originating artifact toward parent service, domain, and program ledgers. It may also inspect sibling services when the source explicitly names shared contracts, dependencies, or reused decisions.

## Classification

Classify findings as:

- **Blocking:** downstream evidence contradicts a published parent decision, breaks a contract or dependency statement, changes security/compliance/program commitments, invalidates a stable ID relationship, or requires a topology change before promotion.
- **Advisory:** parent docs need refresh, examples are stale, report freshness is beyond threshold, related ledgers should add breadcrumbs, or the impact is plausible but not proven.

Be explicit about confidence. Label inferences as inferred, and keep speculative impacts out of blocking status unless the contradiction is evidence-backed.

## Workflow

Identify the origin of the Salmon signal and the upstream path to review. If the origin lacks stable IDs or parent references, run a focused inline map audit for just that scope and record any metadata gaps.

Read the origin artifact, parent chain, referenced ledgers, recent promotion reports, and recent map audit reports if available. Build an impact tree showing each upstream node, the claim being tested, evidence for/against consistency, and the action needed.

Do not edit source docs by default. If the user asks for patches, propose scoped ledger or topology updates in the report first and apply only after confirmation.

Write `{reporting_output_path}/salmon-impact-{origin-or-date}.md`.

## Report Contract

The report must include:

- Origin artifact, signal type, timestamp, and reviewed upstream path
- Impact verdict: `NO_UPSTREAM_CHANGE`, `ADVISORY_REFRESH`, `BLOCKING_CONTRADICTION`, or `TOPOLOGY_REVIEW_REQUIRED`
- Impact tree from origin to service/domain/program parents
- Blocking findings and advisory findings in separate tables
- Proposed recursive consistency actions, ordered from highest parent to source artifact
- Evidence notes distinguishing direct facts from inference
- Machine-readable summary block:

```json
{
  "module": "ausx",
  "report_type": "salmon_impact",
  "origin": "",
  "verdict": "ADVISORY_REFRESH",
  "blocking_count": 0,
  "advisory_count": 0
}
```

## Safety Rules

Never let the Salmon review silently change topology. If parentage, ownership, or stable identity must change, classify the item as topology review required and route to `ausx-topology-design`.

