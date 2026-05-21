---
title: 'Lens Module Plan'
status: 'complete'
module_name: 'Lens'
module_code: 'lens'
module_description: 'Workflow suite for clean-room NextLens lifecycle planning, topology governance, living ledgers, Salmon impact analysis, and stakeholder reporting artifacts.'
architecture: 'multi-skill workflow suite'
standalone: true
expands_module: ''
skills_planned:
  - lens-lifecycle
  - lens-next
  - lens-preplan
  - lens-businessplan
  - lens-techplan
  - lens-expressplan
  - lens-finalizeplan
  - lens-dev
  - lens-preflight
  - lens-work-intake
  - lens-doctor
  - lens-map-audit
  - lens-projection-rebuild
  - lens-ledger-promotion
  - lens-salmon-impact
  - lens-topology-design
  - lens-reporting-snapshot
config_variables:
  - work_intake_path
  - feature_archive_path
  - landscape_root
  - reporting_output_path
  - freshness_threshold_hours
  - lens_mode
  - lens_governance_repo_path
  - lens_lifecycle_contract
  - lens_context_path
created: '2026-05-20'
updated: '2026-05-21'
---

# Lens Module Plan

## Vision

Lens helps teams manage NextLens/BMAD project knowledge with a Two-Tree Model: permanent work and feature archives preserve delivery history, and living service/domain/program ledgers preserve current operational truth. The module creates a single entry point for new units of work, moves them through local clean-room lifecycle phases, then produces governance and reporting artifacts so stakeholders can see status, risk, promotion gaps, and topology health without treating generated projections as authored truth.

Target users are NextLens maintainers, BMAD planners, feature teams promoting completed work, architects managing service topology, and stakeholders who need status snapshots without editing the source docs.

## Architecture

Lens is a multi-skill workflow suite. It does not need a long-lived conversational agent in v1 because each capability has a distinct input/output workflow and no persistent persona requirement.

The suite is workflow-only:

- `lens-preflight` checks Lens config, paths, reporting write scope, and optional Lens context without invoking Lens tools.
- `lens-work-intake` creates durable feature archives and hands them to the local NextLens lifecycle.
- `lens-lifecycle` provides deterministic local phase routing, artifact validation, and phase advancement.
- `lens-next` inspects local feature state and routes to the next command.
- `lens-preplan`, `lens-businessplan`, and `lens-techplan` run the full planning track.
- `lens-expressplan` runs the compact express track.
- `lens-finalizeplan` converts full or express planning inputs into a dev-ready story bundle.
- `lens-dev` executes finalized story work against configured target repositories and records evidence.
- `lens-doctor` runs lightweight deterministic health checks over authored topology metadata.
- `lens-map-audit` validates source topology, stable IDs, parent references, links, and projection rebuild readiness.
- `lens-projection-rebuild` materializes derived governance map JSON and Markdown from authored frontmatter.
- `lens-ledger-promotion` promotes completed feature knowledge into living ledgers with provenance.
- `lens-salmon-impact` reviews upstream-impact signals and recursive consistency risk.
- `lens-topology-design` creates or updates topology decision reports and optional ledger scaffolds.
- `lens-reporting-snapshot` creates read-only stakeholder artifacts for human review and future UI ingestion.

### Metadata And Publication Contract

Lens uses `skills/lens-setup/assets/metadata-schema.md` as the shared metadata contract and `skills/lens-setup/assets/templates/` as the scaffold source for work archives, feature archives, ledgers, and generated projections. Local lifecycle authority lives in `docs/features/<feature-id>/feature.yaml`. `status` tracks delivery state; `phase` tracks the clean-room lifecycle phase; `publication_state` replaces planning-branch assumptions by marking artifacts as `draft`, `published`, or `retired`. Published projections exclude drafts unless a workflow explicitly requests a draft-inclusive preview.

Lens also supports optional external provenance fields such as `lens_feature_id`, `lens_track`, `lens_phase`, `lens_docs_path`, `lens_governance_repo_path`, `lens_feature_yaml_path`, `lens_constitution_status`, and `lens_preflight_status`. These fields are evidence only; they do not replace the local NextLens feature record.

### Clean-Room Lifecycle Ownership

NextLens owns the local lifecycle implementation. Legacy behavior is treated as a behavioral reference, not an implementation dependency. The clean-room lifecycle uses local feature records, local feature archives, and local BMAD skills. It does not run repo sync, create planning branches, depend on branch location for validity, or write external governance mirrors.

The lifecycle tracks are explicit:

- `full`: `preplan -> businessplan -> techplan -> finalizeplan -> dev`
- `express`: `expressplan -> finalizeplan -> dev`

After delivery, governance remains evidence-driven: doctor, projection rebuild, ledger promotion, Salmon review when triggered, topology decisions when needed, and reporting snapshots.

### Memory Architecture

Durable state lives in project artifacts, not hidden chat history. `lens-work-intake` writes explicit work memory into each work archive so thread learnings, decisions, related-work context, open loops, and lifecycle status can be inspected, edited, diffed, and reused by future workers. Ledgers, topology decisions, promotion/audit/impact reports, and snapshots remain the other durable knowledge surfaces.

### Memory Contract

Lens memory is file-based and project-scoped. Each unit of work owns `memory.md` beside `work.md`, `journey.md`, `handoff.md`, and `links.md`. The memory file captures durable context only: decisions, source signals, user constraints, related work, assumptions, open loops, and discarded options worth preserving. It must not become a private agent persona or a replacement for authored ledgers.

### Cross-Agent Patterns

`lens-work-intake` is the recommended single entry point for new work, then the handoff file routes to `/next` or a specific lifecycle command. Local lifecycle commands may use BMAD planning, architecture, sprint, story, development, and review skills, but the feature record, phase state, and artifacts remain under `docs/features/<feature-id>/`. Governance ordering is evidence-driven after delivery: lens doctor, map audit, projection rebuild, promotion, Salmon review when triggered, topology decisions when needed, and reporting snapshots.

## Skills

### lens-preflight

**Type:** workflow with deterministic script

**Core Outcome:** A readiness result states whether Lens can safely read source artifacts, write reports, and consume optional Lens context.

**The Non-Negotiable:** Diagnose readiness only; do not repair config, run Lens commands, or write governance state.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Check readiness | Validates Lens paths, metadata schema, reporting output scope, Lens workspace markers, active Lens context, lifecycle contract presence, and governance repo availability when Lens is required | Project root, config paths, optional Lens paths | JSON preflight result with blocking/advisory findings |

**Activation Modes:** Interactive and headless.

**Design Notes:** This is an Lens-native clean-room counterpart to Lens preflight. It is supplemental in Lens mode and authoritative only for local Lens readiness.

### lens-work-intake

**Type:** workflow

**Core Outcome:** A durable feature archive exists for one feature/change and contains the next local lifecycle handoff.

**The Non-Negotiable:** Work starts as an inspectable file artifact, not as hidden chat memory.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Start work | Creates or resumes a feature archive with goal, success criteria, memory, journey, links, `feature.yaml`, and handoff | Feature idea, change request, existing feature ID, optional relation | Feature archive with `feature.yaml`, `work.md`, `memory.md`, `journey.md`, `handoff.md`, and `links.md` |
| Create related work | Starts a follow-up feature using relevant durable context from prior work | Related feature ID, extension/replacement signal, new goal | New archive with relationship metadata and inherited durable decisions |
| Route lifecycle | Selects the next local lifecycle workflow | Work readiness, existing artifacts, sprint state hints | `handoff.md` with next skill and required context |

**Activation Modes:** Interactive and headless.

**Design Notes:** This workflow gives Lens a single front door and initializes local lifecycle state without absorbing the responsibilities of PRD, architecture, sprint status, story creation, development, or ledger promotion.

### lens-lifecycle

**Type:** internal workflow with deterministic script

**Core Outcome:** Local feature records can be resolved, checked, routed, and advanced without external lifecycle state.

**The Non-Negotiable:** The script never imports or invokes external lifecycle code.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Suggest next | Routes a feature to the next lifecycle command | Feature ID or feature path | JSON recommendation with blockers and missing artifacts |
| Validate phase | Checks required artifacts for a phase | Feature ID and phase | JSON pass/fail result |
| Advance phase | Marks a phase complete after validation | Feature ID and phase | Updated local `feature.yaml` |

**Activation Modes:** Headless deterministic script used by command skills.

**Design Notes:** The lifecycle contract lives in `skills/lens-lifecycle/assets/lifecycle.yaml`; implementation lives in `skills/lens-lifecycle/scripts/lifecycle_ops.py`.

### lens-next, lens-preplan, lens-businessplan, lens-techplan, lens-expressplan, lens-finalizeplan, lens-dev

**Type:** command workflow suite

**Core Outcome:** Feature work moves through either the full or express local lifecycle using durable feature-archive artifacts.

**The Non-Negotiable:** Planning state is file-backed under `docs/features/<feature-id>/`; branch state and external governance mirrors are not authoritative.

**Capabilities:**

| Command | Track | Outcome |
| ------- | ----- | ------- |
| `next` | all | Suggests and loads the next local lifecycle command. |
| `preplan` | full | Creates brainstorm, research, product brief, and review artifacts. |
| `businessplan` | full | Creates PRD, UX design, and review artifacts. |
| `techplan` | full | Creates architecture and review artifacts. |
| `expressplan` | express | Creates compact business, technical, sprint, and review artifacts. |
| `finalizePlan` | all | Creates final review, epics, stories, implementation readiness, sprint status, and story files. |
| `dev` | all | Executes finalized stories against configured target repositories and records evidence. |

**Activation Modes:** Interactive and headless where enough feature context exists.

### lens-map-audit

**Type:** workflow

**Core Outcome:** A map audit report that separates blocking inconsistencies from advisory cleanup and states whether projections can be safely rebuilt.

**The Non-Negotiable:** Do not modify source docs; the audit is read-only.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Audit map | Validates stable IDs, parent refs, orphans, broken links, stale records, and completed-but-unpromoted features | Project root, feature archive path, landscape root, optional HTML-capable flag | Markdown audit report with JSON summary |

**Activation Modes:** Interactive and headless.

**Design Notes:** This workflow anchors the rest of the suite because promotion and reporting should not proceed blindly when the source map is inconsistent.

### lens-doctor

**Type:** workflow

**Core Outcome:** A lightweight topology health report states whether projection rebuilds are safe.

**The Non-Negotiable:** Diagnose only; do not repair source docs.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Run doctor | Checks required metadata, stable IDs, parentage, cycles, links, draft state, promotion gaps, and Salmon signals | Project root or docs scope, optional draft inclusion | JSON doctor result with blocking/advisory findings and projection readiness |

**Activation Modes:** Interactive and headless.

**Design Notes:** This is the fast preflight path. It shares deterministic checks with projection rebuild so the readiness signal is consistent.

### lens-projection-rebuild

**Type:** workflow with deterministic script

**Core Outcome:** Derived `governance-map.json` and `governance-map.md` are rebuilt from authored frontmatter.

**The Non-Negotiable:** Generated maps are disposable projections, never source truth.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Rebuild projection | Runs doctor checks, then writes derived map artifacts when safe or explicitly forced | Project root, configured source paths, optional `--include-drafts` or `--force` | Governance map JSON and Markdown with source metadata and doctor status |

**Activation Modes:** Interactive and headless.

**Design Notes:** The stdlib script provides deterministic graph checks without adding external dependencies.

### lens-ledger-promotion

**Type:** workflow

**Core Outcome:** Completed feature knowledge is planned for or promoted into living ledgers with source provenance.

**The Non-Negotiable:** Preserve the permanent feature archive and do not erase delivery history.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Promote ledger knowledge | Moves durable completed-feature knowledge into the correct service/domain/program ledger | Feature folder or scope, landscape root, optional apply flag | Promotion report and optional ledger edits |

**Activation Modes:** Interactive and headless dry-run by default.

**Design Notes:** Headless runs report only unless explicitly told to apply changes.

### lens-salmon-impact

**Type:** workflow

**Core Outcome:** Upstream-impact signals are traced recursively and classified as advisory refreshes or blocking contradictions.

**The Non-Negotiable:** Do not silently change topology.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Review Salmon impact | Traces downstream findings upstream through service/domain/program ledgers | Origin artifact, feature archive path, landscape root, recent reports | Salmon impact report with impact tree and classification |

**Activation Modes:** Interactive and headless.

**Design Notes:** Salmon review now traverses upward through parent ledgers and downward through inverse or named dependent references. It recommends topology review when parentage or ownership changes are needed.

### lens-topology-design

**Type:** workflow

**Core Outcome:** A topology decision report defines or updates service/domain/program relationships, stable IDs, and ledger paths.

**The Non-Negotiable:** Generated projections remain derived views, not source truth.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Design topology | Creates or updates topology decisions from project context and prior Lens reports | Project context, ledgers, feature archives, audit/impact reports | Topology decision report and optional ledger scaffold |

**Activation Modes:** Interactive and headless report-only by default.

**Design Notes:** This workflow can be run early for a new project or later when audits/Salmon reviews reveal topology drift.

### lens-reporting-snapshot

**Type:** workflow

**Core Outcome:** Stakeholders get a read-only status snapshot with stable JSON for future UI ingestion.

**The Non-Negotiable:** Never write back to source docs.

**Capabilities:**

| Capability | Outcome | Inputs | Outputs |
| ---------- | ------- | ------ | ------- |
| Create reporting snapshot | Summarizes project health, completed features, promotion gaps, topology risk, Salmon impact, and freshness | Feature archives, ledgers, recent Lens reports | Markdown snapshot and JSON snapshot |

**Activation Modes:** Interactive and headless.

**Design Notes:** The snapshot is explicitly time-bound and cannot become source truth. Its JSON contract is documented in `skills/lens-reporting-snapshot/assets/reporting-snapshot.schema.json` for future MVP1 UI ingestion.

## Configuration

| Variable | Prompt | Default | Result Template | User Setting |
| -------- | ------ | ------- | --------------- | ------------ |
| work_intake_path | Where should Lens create durable work unit archives? | docs/features | Prefix the answer with the literal project-root token | false |
| feature_archive_path | Where should Lens look for permanent feature archives? | docs/features | Prefix the answer with the literal project-root token | false |
| landscape_root | Where should Lens look for living service/domain/program ledgers? | docs | Prefix the answer with the literal project-root token | false |
| reporting_output_path | Where should Lens write reports and snapshots? | _bmad-output/lens | Prefix the answer with the literal project-root token | false |
| freshness_threshold_hours | How old can reports be before Lens marks them stale? | 24 | {value} | false |
| lens_mode | How should Lens handle Lens context? | auto | {value} | false |
| lens_governance_repo_path | Optional Lens governance repo path for required Lens mode. | empty | {value} | false |
| lens_lifecycle_contract | Optional NextLens lifecycle contract path. | skills/lens-lifecycle/assets/lifecycle.yaml | Prefix the answer with the literal project-root token | false |
| lens_context_path | Optional Lens feature context path. | .lens/personal/context.yaml | Prefix the answer with the literal project-root token | false |

## External Dependencies

No external CLI tools, MCP servers, web services, or UI runtimes are required in v1. `lens-preflight`, `lens-lifecycle`, and `lens-projection-rebuild` include Python stdlib scripts for deterministic readiness, lifecycle routing, doctor, and rebuild checks.

## UI and Visualization

No web UI is packaged in v1 because this repository does not contain an application host. `lens-reporting-snapshot` writes JSON designed for future Lens UI ingestion, and `skills/reports/lens-reporting-ui-mvp1-plan.md` captures the deferred dashboard, artifact reader, search/filter, refresh, access, and deployment scope.

## Setup Extensions

The generated `lens-setup` skill collects configuration values, merges help entries, and creates configured output directories. No custom setup extensions are required beyond the standard BMad module setup scaffold.

## Integration

Lens is standalone and can be installed into any BMAD-compatible project with compatible docs. It complements BMAD planning and implementation workflows by creating the initial feature archive, then running the local NextLens lifecycle around BMAD planning, architecture, story, development, and review skills.

External Lens context, when present, is consumed only as provenance and readiness evidence. Local lifecycle state remains governed by `docs/features/<feature-id>/feature.yaml`; generated projections remain derived caches; living ledgers remain authored operational truth.

## Creative Use Cases

- Start every meaningful feature with `lens-work-intake` so intent, memory, related work, `feature.yaml`, and next lifecycle step are serialized before implementation begins.
- Use `/next` to route full-track and express-track features from the local feature record.
- Run Lens preflight, lens doctor, and map audits as readiness gates before rebuilding derived governance projections.
- Rebuild `governance-map.json` for dashboards without making the dashboard authoritative.
- Use promotion reports as release-closeout evidence.
- Use Salmon impact reports to decide whether a downstream discovery should block publication.
- Feed snapshot JSON into a lightweight dashboard without making the dashboard authoritative.

## Build Roadmap

1. Build `lens-preflight` first so every later workflow has a consistent local readiness and optional external context signal.
2. Build `lens-work-intake` so every later feature can start from a durable feature archive and lifecycle handoff.
3. Build `lens-lifecycle` and the command skills so local phase routing, validation, and advancement are deterministic.
4. Build `lens-doctor` so topology and local lifecycle metadata can be checked quickly and deterministically.
5. Build `lens-map-audit` because it produces the reviewable audit report used by every later governance workflow.
6. Build `lens-projection-rebuild` so derived governance maps can be regenerated after a clean doctor/audit.
7. Build `lens-ledger-promotion` so completed published feature knowledge can move into living truth.
8. Build `lens-salmon-impact` after promotion so upstream and downstream changes can be traced with current ledgers.
9. Build `lens-topology-design` after the evidence workflows so topology decisions can reference audit and impact findings.
10. Build `lens-reporting-snapshot` last because it summarizes the outputs of the other workflows and feeds future UI ingestion.
