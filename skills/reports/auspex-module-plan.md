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
  - ausx-map-audit
  - ausx-ledger-promotion
  - ausx-salmon-impact
  - ausx-topology-design
  - ausx-reporting-snapshot
config_variables:
  - feature_archive_path
  - landscape_root
  - reporting_output_path
  - freshness_threshold_hours
created: '2026-05-20'
updated: '2026-05-20'
---

# Auspex Module Plan

## Vision

Auspex helps teams manage LENS/BMAD project knowledge with a Two-Tree Model: permanent feature archives preserve delivery history, and living service/domain/program ledgers preserve current operational truth. The module also produces read-only reporting artifacts so stakeholders can see status, risk, promotion gaps, and topology health without treating generated projections as authored truth.

Target users are BMAD/LENS maintainers, feature teams promoting completed work, architects managing service topology, and stakeholders who need status snapshots without editing the source docs.

## Architecture

Auspex is a multi-skill workflow suite. It does not need a long-lived conversational agent in v1 because each capability has a distinct input/output workflow and no persistent persona requirement.

The suite is workflow-only:

- `ausx-map-audit` validates source topology, stable IDs, parent references, links, and projection rebuild readiness.
- `ausx-ledger-promotion` promotes completed feature knowledge into living ledgers with provenance.
- `ausx-salmon-impact` reviews upstream-impact signals and recursive consistency risk.
- `ausx-topology-design` creates or updates topology decision reports and optional ledger scaffolds.
- `ausx-reporting-snapshot` creates read-only stakeholder artifacts for human review and future UI ingestion.

### Memory Architecture

No agent memory is required in v1. Durable state lives in project artifacts: feature archives, ledgers, topology decisions, promotion/audit/impact reports, and snapshots.

### Memory Contract

Not applicable for v1. The workflows read project artifacts and write reports rather than storing personal or shared agent memory.

### Cross-Agent Patterns

No cross-agent handoff is required. Workflow ordering is evidence-driven: audit first, then promotion, Salmon review, topology decisions, and reporting snapshots. Users may invoke any workflow directly when they already know the scope.

## Skills

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

**Design Notes:** Salmon review recommends topology review when parentage or ownership changes are needed.

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

**Design Notes:** The snapshot is explicitly time-bound and cannot become source truth.

## Configuration

| Variable | Prompt | Default | Result Template | User Setting |
| -------- | ------ | ------- | --------------- | ------------ |
| feature_archive_path | Where should Auspex look for permanent feature archives? | docs/features | Prefix the answer with the literal project-root token | false |
| landscape_root | Where should Auspex look for living service/domain/program ledgers? | docs | Prefix the answer with the literal project-root token | false |
| reporting_output_path | Where should Auspex write reports and snapshots? | _bmad-output/auspex | Prefix the answer with the literal project-root token | false |
| freshness_threshold_hours | How old can reports be before Auspex marks them stale? | 24 | {value} | false |

## External Dependencies

No external CLI tools, MCP servers, web services, or UI runtimes are required in v1.

## UI and Visualization

No web UI is packaged in v1. `ausx-reporting-snapshot` writes JSON designed for future Auspex UI ingestion.

## Setup Extensions

The generated `ausx-setup` skill collects configuration values, merges help entries, and creates configured output directories. No custom setup extensions are required beyond the standard BMad module setup scaffold.

## Integration

Auspex is standalone and can be installed into any BMad/LENS project with compatible docs. It complements BMAD planning and implementation workflows but does not require another Auspex service or UI.

## Creative Use Cases

- Run map audits as a preflight gate before rebuilding derived governance projections.
- Use promotion reports as release-closeout evidence.
- Use Salmon impact reports to decide whether a downstream discovery should block publication.
- Feed snapshot JSON into a lightweight dashboard without making the dashboard authoritative.

## Build Roadmap

1. Build `ausx-map-audit` first because it validates the knowledge graph used by every later workflow.
2. Build `ausx-ledger-promotion` next so completed feature knowledge can move into living truth.
3. Build `ausx-salmon-impact` after promotion so upstream changes can be traced with current ledgers.
4. Build `ausx-topology-design` after the evidence workflows so topology decisions can reference audit and impact findings.
5. Build `ausx-reporting-snapshot` last because it summarizes the outputs of the other workflows.
