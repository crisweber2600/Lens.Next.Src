---
title: 'Auspex Module Plan'
status: 'complete'
module_name: 'Auspex'
module_code: 'ausx'
module_description: 'Workflow suite for LENS/BMAD topology governance, living ledgers, Salmon impact analysis, and stakeholder reporting artifacts.'
architecture: 'multi-skill workflow suite'
standalone: true
expands_module: ''
skills_planned:
  - ausx-work-intake
  - ausx-lens-doctor
  - ausx-map-audit
  - ausx-projection-rebuild
  - ausx-ledger-promotion
  - ausx-salmon-impact
  - ausx-topology-design
  - ausx-reporting-snapshot
config_variables:
  - work_intake_path
  - feature_archive_path
  - landscape_root
  - reporting_output_path
  - freshness_threshold_hours
created: '2026-05-20'
updated: '2026-05-21'
---

# Auspex Module Plan

## Vision

Auspex helps teams manage LENS/BMAD project knowledge with a Two-Tree Model: permanent work and feature archives preserve delivery history, and living service/domain/program ledgers preserve current operational truth. The module creates a single entry point for new units of work, then produces governance and reporting artifacts so stakeholders can see status, risk, promotion gaps, and topology health without treating generated projections as authored truth.

Target users are BMAD/LENS maintainers, feature teams promoting completed work, architects managing service topology, and stakeholders who need status snapshots without editing the source docs.

## Architecture

Auspex is a multi-skill workflow suite. It does not need a long-lived conversational agent in v1 because each capability has a distinct input/output workflow and no persistent persona requirement.

The suite is workflow-only:

- `ausx-work-intake` creates durable units of work and hands them to the Lens/BMad lifecycle.
- `ausx-lens-doctor` runs lightweight deterministic health checks over authored topology metadata.
- `ausx-map-audit` validates source topology, stable IDs, parent references, links, and projection rebuild readiness.
- `ausx-projection-rebuild` materializes derived governance map JSON and Markdown from authored frontmatter.
- `ausx-ledger-promotion` promotes completed feature knowledge into living ledgers with provenance.
- `ausx-salmon-impact` reviews upstream-impact signals and recursive consistency risk.
- `ausx-topology-design` creates or updates topology decision reports and optional ledger scaffolds.
- `ausx-reporting-snapshot` creates read-only stakeholder artifacts for human review and future UI ingestion.

### Metadata And Publication Contract

Auspex uses `skills/ausx-setup/assets/metadata-schema.md` as the shared metadata contract and `skills/ausx-setup/assets/templates/` as the scaffold source for work archives, feature archives, ledgers, and generated projections. `status` tracks lifecycle; `publication_state` replaces planning-branch assumptions by marking artifacts as `draft`, `published`, or `retired`. Published projections exclude drafts unless a workflow explicitly requests a draft-inclusive preview.

### Memory Architecture

Durable state lives in project artifacts, not hidden chat history. `ausx-work-intake` writes explicit work memory into each work archive so thread learnings, decisions, related-work context, open loops, and lifecycle status can be inspected, edited, diffed, and reused by future workers. Ledgers, topology decisions, promotion/audit/impact reports, and snapshots remain the other durable knowledge surfaces.

### Memory Contract

Auspex memory is file-based and project-scoped. Each unit of work owns `memory.md` beside `work.md`, `journey.md`, `handoff.md`, and `links.md`. The memory file captures durable context only: decisions, source signals, user constraints, related work, assumptions, open loops, and discarded options worth preserving. It must not become a private agent persona or a replacement for authored ledgers.

### Cross-Agent Patterns

`ausx-work-intake` is the recommended single entry point for new work, then the handoff file routes to the appropriate Lens/BMad workflow: product brief, PRD, UX/design delivery, architecture, epics and stories, sprint planning, story creation, development, quick-dev, or governance. Existing Auspex workflows remain directly invokable for known scopes. Governance ordering is evidence-driven after delivery: lens doctor, map audit, projection rebuild, promotion, Salmon review when triggered, topology decisions when needed, and reporting snapshots.

## Skills

### ausx-work-intake

**Type:** workflow

**Core Outcome:** A durable work archive exists for one feature/change and contains the next Lens/BMad handoff.

**The Non-Negotiable:** Work starts as an inspectable file artifact, not as hidden chat memory.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Start work | Creates or resumes a work archive with goal, success criteria, memory, journey, links, and handoff | Feature idea, change request, existing work ID, optional relation | Work archive with `work.md`, `memory.md`, `journey.md`, `handoff.md`, and `links.md` |
| Create related work | Starts a follow-up feature using relevant durable context from prior work | Related feature ID, extension/replacement signal, new goal | New archive with relationship metadata and inherited durable decisions |
| Route lifecycle | Selects the next Lens/BMad workflow | Work readiness, existing artifacts, sprint state hints | `handoff.md` with next skill and required context |

**Activation Modes:** Interactive and headless.

**Design Notes:** This workflow gives Auspex a single front door without absorbing the responsibilities of PRD, architecture, sprint status, story creation, development, or ledger promotion.

### ausx-map-audit

**Type:** workflow

**Core Outcome:** A map audit report that separates blocking inconsistencies from advisory cleanup and states whether projections can be safely rebuilt.

**The Non-Negotiable:** Do not modify source docs; the audit is read-only.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Audit map | Validates stable IDs, parent refs, orphans, broken links, stale records, and completed-but-unpromoted features | Project root, feature archive path, landscape root, optional HTML-capable flag | Markdown audit report with JSON summary |

**Activation Modes:** Interactive and headless.

**Design Notes:** This workflow anchors the rest of the suite because promotion and reporting should not proceed blindly when the source map is inconsistent.

### ausx-lens-doctor

**Type:** workflow

**Core Outcome:** A lightweight topology health report states whether projection rebuilds are safe.

**The Non-Negotiable:** Diagnose only; do not repair source docs.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Run doctor | Checks required metadata, stable IDs, parentage, cycles, links, draft state, promotion gaps, and Salmon signals | Project root or docs scope, optional draft inclusion | JSON doctor result with blocking/advisory findings and projection readiness |

**Activation Modes:** Interactive and headless.

**Design Notes:** This is the fast preflight path. It shares deterministic checks with projection rebuild so the readiness signal is consistent.

### ausx-projection-rebuild

**Type:** workflow with deterministic script

**Core Outcome:** Derived `governance-map.json` and `governance-map.md` are rebuilt from authored frontmatter.

**The Non-Negotiable:** Generated maps are disposable projections, never source truth.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Rebuild projection | Runs doctor checks, then writes derived map artifacts when safe or explicitly forced | Project root, configured source paths, optional `--include-drafts` or `--force` | Governance map JSON and Markdown with source metadata and doctor status |

**Activation Modes:** Interactive and headless.

**Design Notes:** The stdlib script provides deterministic graph checks without adding external dependencies.

### ausx-ledger-promotion

**Type:** workflow

**Core Outcome:** Completed feature knowledge is planned for or promoted into living ledgers with source provenance.

**The Non-Negotiable:** Preserve the permanent feature archive and do not erase delivery history.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Promote ledger knowledge | Moves durable completed-feature knowledge into the correct service/domain/program ledger | Feature folder or scope, landscape root, optional apply flag | Promotion report and optional ledger edits |

**Activation Modes:** Interactive and headless dry-run by default.

**Design Notes:** Headless runs report only unless explicitly told to apply changes.

### ausx-salmon-impact

**Type:** workflow

**Core Outcome:** Upstream-impact signals are traced recursively and classified as advisory refreshes or blocking contradictions.

**The Non-Negotiable:** Do not silently change topology.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Review Salmon impact | Traces downstream findings upstream through service/domain/program ledgers | Origin artifact, feature archive path, landscape root, recent reports | Salmon impact report with impact tree and classification |

**Activation Modes:** Interactive and headless.

**Design Notes:** Salmon review now traverses upward through parent ledgers and downward through inverse or named dependent references. It recommends topology review when parentage or ownership changes are needed.

### ausx-topology-design

**Type:** workflow

**Core Outcome:** A topology decision report defines or updates service/domain/program relationships, stable IDs, and ledger paths.

**The Non-Negotiable:** Generated projections remain derived views, not source truth.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Design topology | Creates or updates topology decisions from project context and prior Auspex reports | Project context, ledgers, feature archives, audit/impact reports | Topology decision report and optional ledger scaffold |

**Activation Modes:** Interactive and headless report-only by default.

**Design Notes:** This workflow can be run early for a new project or later when audits/Salmon reviews reveal topology drift.

### ausx-reporting-snapshot

**Type:** workflow

**Core Outcome:** Stakeholders get a read-only status snapshot with stable JSON for future UI ingestion.

**The Non-Negotiable:** Never write back to source docs.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Create reporting snapshot | Summarizes project health, completed features, promotion gaps, topology risk, Salmon impact, and freshness | Feature archives, ledgers, recent Auspex reports | Markdown snapshot and JSON snapshot |

**Activation Modes:** Interactive and headless.

**Design Notes:** The snapshot is explicitly time-bound and cannot become source truth. Its JSON contract is documented in `skills/ausx-reporting-snapshot/assets/reporting-snapshot.schema.json` for future MVP1 UI ingestion.

## Configuration

| Variable | Prompt | Default | Result Template | User Setting |
| -------- | ------ | ------- | --------------- | ------------ |
| work_intake_path | Where should Auspex create durable work unit archives? | docs/features | Prefix the answer with the literal project-root token | false |
| feature_archive_path | Where should Auspex look for permanent feature archives? | docs/features | Prefix the answer with the literal project-root token | false |
| landscape_root | Where should Auspex look for living service/domain/program ledgers? | docs | Prefix the answer with the literal project-root token | false |
| reporting_output_path | Where should Auspex write reports and snapshots? | _bmad-output/auspex | Prefix the answer with the literal project-root token | false |
| freshness_threshold_hours | How old can reports be before Auspex marks them stale? | 24 | {value} | false |

## External Dependencies

No external CLI tools, MCP servers, web services, or UI runtimes are required in v1. `ausx-projection-rebuild` includes a Python stdlib script for deterministic doctor and rebuild checks.

## UI and Visualization

No web UI is packaged in v1 because this repository does not contain an application host. `ausx-reporting-snapshot` writes JSON designed for future Auspex UI ingestion, and `skills/reports/auspex-reporting-ui-mvp1-plan.md` captures the deferred dashboard, artifact reader, search/filter, refresh, access, and deployment scope.

## Setup Extensions

The generated `ausx-setup` skill collects configuration values, merges help entries, and creates configured output directories. No custom setup extensions are required beyond the standard BMad module setup scaffold.

## Integration

Auspex is standalone and can be installed into any BMad/LENS project with compatible docs. It complements BMAD planning and implementation workflows by creating the initial work archive, then handing off to the existing Lens/BMad lifecycle rather than duplicating it.

## Creative Use Cases

- Start every meaningful feature with `ausx-work-intake` so intent, memory, related work, and next lifecycle step are serialized before implementation begins.
- Run lens doctor and map audits as preflight gates before rebuilding derived governance projections.
- Rebuild `governance-map.json` for dashboards without making the dashboard authoritative.
- Use promotion reports as release-closeout evidence.
- Use Salmon impact reports to decide whether a downstream discovery should block publication.
- Feed snapshot JSON into a lightweight dashboard without making the dashboard authoritative.

## Build Roadmap

1. Build `ausx-work-intake` first so every later feature can start from a durable work archive and lifecycle handoff.
2. Build `ausx-lens-doctor` so topology health can be checked quickly and deterministically.
3. Build `ausx-map-audit` because it produces the reviewable audit report used by every later governance workflow.
4. Build `ausx-projection-rebuild` so derived governance maps can be regenerated after a clean doctor/audit.
5. Build `ausx-ledger-promotion` so completed published feature knowledge can move into living truth.
6. Build `ausx-salmon-impact` after promotion so upstream and downstream changes can be traced with current ledgers.
7. Build `ausx-topology-design` after the evidence workflows so topology decisions can reference audit and impact findings.
8. Build `ausx-reporting-snapshot` last because it summarizes the outputs of the other workflows and feeds future UI ingestion.
