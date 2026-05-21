---
name: ausx-topology-design
description: Designs Auspex topology decisions. Use when the user requests 'ausx topology design', 'design service topology', or 'update topology decision'.
---

# Auspex Topology Design

## Overview

This skill creates or updates service, domain, and program topology decisions for LENS/BMAD projects using the Auspex Two-Tree model. Act as a topology architect: turn project context into durable parentage, stable IDs, and ledger placement decisions while preserving the distinction between authored truth and generated projections.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, `{project-root}/_bmad/config.toml`, and `{project-root}/_bmad/config.user.toml`, checking both root values and the `ausx` or `modules.ausx` section. If config is missing, let the user know `ausx-setup` can configure Auspex at any time. Use these defaults:

- `feature_archive_path`: `{project-root}/docs/features`
- `landscape_root`: `{project-root}/docs`
- `reporting_output_path`: `{project-root}/_bmad-output/auspex`
- `freshness_threshold_hours`: `24`

Support interactive and headless use. In headless mode, create a decision report from available context and mark unresolved choices explicitly instead of asking follow-up questions.

## Topology Contract

Topology decisions define how programs, domains, services, and major shared capabilities relate. They do not rewrite feature history. They may create or update living ledger scaffolds only when the user explicitly approves or when headless arguments explicitly request scaffolding.

Prefer stable IDs that survive file moves. Use `belongs_to` for parent references. Use generated projections only as derived views; if a projection conflicts with authored ledgers or feature archives, trust the authored source and record the projection problem.

## Workflow

Start by identifying the design intent: new topology, topology update, conflict resolution, or ledger path normalization. Read the relevant project context, existing ledger structure, feature archives, prior topology decisions, map audit reports, and Salmon impact reports. If key context is missing, capture assumptions in the decision report instead of inventing certainty.

Develop a topology proposal covering:

- Program/domain/service hierarchy and rationale
- Stable ID assignments or migrations
- Ledger path conventions, including shallower landscape paths when appropriate
- Parent references and ownership boundaries
- Source features or decisions that justify each entity
- Impact on projection rebuilds, reporting snapshots, and pending promotions

For interactive runs, present the proposed topology before modifying source docs. For headless runs, write the report and do not modify ledger files unless an explicit apply/scaffold argument is present.

Write topology decision reports to `{reporting_output_path}/topology-decision-{date}.md` unless the user names a different target. If applying approved ledger scaffolds, write only under `landscape_root`.

## Decision Report Contract

The report must include:

- Scope, sources read, timestamp, and assumptions
- Decision status: `PROPOSED`, `APPROVED`, `APPLIED`, or `BLOCKED`
- Current topology summary and proposed topology summary
- Stable ID table with entity type, title, parent, path, and source
- Blocking inconsistencies and advisory cleanup
- Migration or scaffold plan, including files to create/update
- Projection rebuild guidance
- Machine-readable summary block:

```json
{
  "module": "ausx",
  "report_type": "topology_decision",
  "status": "PROPOSED",
  "entities": [],
  "blocking_count": 0,
  "advisory_count": 0
}
```

## Safety Rules

Do not collapse program/domain/service boundaries just to fit an existing folder layout. If a folder path and a stable parent reference disagree, surface the conflict and explain which authored evidence supports each side.

