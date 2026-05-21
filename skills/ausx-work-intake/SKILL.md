---
name: ausx-work-intake
description: Starts durable Auspex work units. Use when the user requests 'ausx work intake', 'start work', or 'create related feature'.
---

# Auspex Work Intake

## Overview

This skill creates a durable unit of work by turning an idea, change request, or related feature into an inspectable Auspex feature/work archive. Act as a work-intake steward: preserve the user's raw intent as concise file memory, connect related work without copying noise, and hand the unit to the Lens/BMad lifecycle with a clear next workflow.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, `{project-root}/_bmad/config.toml`, and `{project-root}/_bmad/config.user.toml`, checking both root values and the `ausx` or `modules.ausx` section. If config is missing, let the user know `ausx-setup` can configure Auspex at any time. Use these defaults:

- `work_intake_path`: `{project-root}/docs/features`
- `feature_archive_path`: `{project-root}/docs/features`
- `landscape_root`: `{project-root}/docs`
- `reporting_output_path`: `{project-root}/_bmad-output/auspex`
- `freshness_threshold_hours`: `24`

Support interactive and headless use. In headless mode, infer the work ID, relationship, and lifecycle handoff from the provided request and existing artifacts; write the archive; and return compact JSON with `status`, `work_id`, `work_path`, `handoff_path`, `next_skill`, and `open_questions`.

## Work Unit Contract

A unit of work is the permanent historical record for one feature, change, investigation, or related follow-up. Create or update it under `{work_intake_path}/<work-id>/`. The work archive is authored truth for delivery history; living service/domain/program ledgers remain current operational truth and are only changed later by `ausx-ledger-promotion`.

Use the shared Auspex metadata contract at `{project-root}/skills/ausx-setup/assets/metadata-schema.md` and the work template at `{project-root}/skills/ausx-setup/assets/templates/work.md` when available. `status` tracks lifecycle; `publication_state` controls whether the artifact participates in published projections.

Each work archive contains:

- `work.md` - frontmatter, goal, scope, success criteria, status, lifecycle handoff, and completion evidence.
- `memory.md` - durable thread memory: decisions, source signals, user constraints, related-work context, open loops, and discarded options worth preserving.
- `journey.md` - end-to-end user journey and lifecycle trace for this unit.
- `handoff.md` - the next Lens/BMad workflow, inputs it needs, and the exact context to carry forward.
- `links.md` - stable IDs, related work, source artifacts, ledger targets, story files, reports, and promotion status.

Keep memory concise, inspectable, and diffable. Do not rely on hidden chat history for anything a future worker needs.

## Workflow

Start by identifying whether the request creates new work, resumes existing work, or creates related work. Generate a stable kebab-case `work_id`; use `feature:<work-id>` as `stable_id` unless that ID already exists, in which case surface the collision and choose a non-conflicting variant.

For related work, scan nearby work archives under `work_intake_path` and `feature_archive_path` for `work.md`, `feature.md`, `memory.md`, and `links.md`. Load only likely matches unless the user explicitly asks for a broad inventory. Record relationships using `related_to`, `extends`, `replaces`, `source_feature`, and `belongs_to` when known. Carry forward only durable decisions and constraints that matter to the new work; do not bulk-copy prior memory.

Create the archive if absent. If it already exists, read `work.md`, `memory.md`, and `links.md`, append a dated update section, and preserve previous content unless the user explicitly asks for a rewrite.

Write `work.md` with frontmatter that includes `stable_id`, `entity_type: feature`, `title`, `status: intake`, `publication_state: draft`, `work_id`, `created_at` or `updated_at`, relationship fields when present, and `lifecycle_stage`. The body must capture the goal, non-goals, success criteria, current understanding, risks or open questions, and completion evidence placeholders.

Write `memory.md` as the work's durable notebook. Capture the user's raw intent, decisions with reasons, assumptions, open loops, source artifacts, and related-work learnings. Treat this as the explicit file memory inspired by long-running agent threads: useful knowledge survives compaction because it is serialized into project artifacts.

Write `journey.md` with the end-to-end path from intake to completion. Include the current work unit's path through discovery, PRD/architecture if needed, epics/stories, sprint status, story creation, development, review, completion, audit, ledger promotion, Salmon impact if triggered, and reporting snapshot.

Write `handoff.md` with the next recommended Lens/BMad workflow:

- Product clarity missing: `bmad-product-brief` or `bmad-prd`.
- UX/design-led work: WDS project brief, trigger mapping, UX design, design delivery, or product evolution as appropriate.
- Technical decision needed: `bmad-create-architecture`.
- Implementation planning needed: `bmad-create-epics-and-stories`, then `bmad-sprint-planning`.
- Sprint already contains the story: `bmad-create-story`, then `bmad-dev-story`.
- Small implementation-ready change: `bmad-quick-dev`, while still preserving the work archive link.

Write `links.md` with all known artifact paths and relationship metadata. If the work is ready for implementation, include a story-template note instructing `bmad-create-story` to cite this work archive under the story's Auspex work-unit section.

## Completion Routing

When a Lens/BMad story, design delivery, or quick-dev change completes, update the work archive with story path, review status, changed files, validation evidence, and completion notes. Then route governance in this order:

1. `ausx-map-audit` to verify IDs, parentage, links, and projection readiness.
2. `ausx-ledger-promotion` to move durable completed knowledge into living ledgers.
3. `ausx-salmon-impact` when the work has `salmon_upstream`, `impact: upstream`, or evidence that parent assumptions changed.
4. `ausx-reporting-snapshot` for stakeholder visibility.

## Output Contract

End every run with the work path, files created or updated, relationship summary, selected next workflow, and open questions. Include a fenced JSON summary:

```json
{
  "module": "ausx",
  "report_type": "work_intake",
  "work_id": "",
  "work_path": "",
  "next_skill": "",
  "related_work": [],
  "open_questions": []
}
```

## Safety Rules

Never edit living ledgers, generated projections, sprint status, story files, or implementation code during intake. Intake may create or update only the work archive and optional index artifacts under the configured work path. Do not fabricate relationships to make the topology look complete; use `unknown` and carry the question into `handoff.md`.