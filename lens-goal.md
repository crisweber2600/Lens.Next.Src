I treated your latest pasted design as the source of truth: BMAD-native LENS, slice as the central unit, top-down and bottom-up modes, “no growth without pressure,” Work Archive + Living Landscape + Derived Map, Salmon, Doctor, Auspex, and focused BMAD packets.

I also shaped it as a Codex-ready, GitHub-issue-style goal with explicit context, constraints, repo-awareness, and validation expectations, matching OpenAI’s Codex guidance to give structure, repo context, file/path patterns, and verification instructions. ([OpenAI][1])

````text
# /goal

You are Codex operating inside a repository intended to build a BMAD-native custom module.

Your goal is to create a new BMAD module named LENS.

LENS stands for:

Large-system
Exploration,
Navigation,
Slicing,
and validation framework

LENS is a BMAD-native slice orchestration and evolving knowledge-topology module.

It supports both:

1. top-down complex-system discovery
2. bottom-up slice-scale growth

It uses:

- Work Archive
- Living Landscape
- Derived Map
- explicit evidence-driven promotion
- relationship lifecycle and gates
- focused BMAD packets
- implementation traceability guards
- Salmon upstream correction
- Doctor topology audits
- Auspex stakeholder visibility

Its purpose is to help teams discover, model, decompose, execute, validate, and continuously reorganize complex software work without losing coherence.

BMAD makes the work buildable.
LENS makes the work understandable, traceable, adaptable, and coherent.
LENS checks whether the built slice still matches reality.

This is a module for BMAD.
It is not a standalone app.
It is not a PRD generator.
It is not a replacement for BMAD.
It is not a domain/service/feature organizer.
It is not NorthStarET.
Do not create NorthStarET.
Do not scaffold a NorthStarET product.
Do not assume the original PDF or uploaded chat files exist.
This goal is self-contained.

NorthStar-like education examples may be used only as tiny illustrative examples, fixtures, docs snippets, or eval scenarios showing how LENS digests a large ambiguous system into focused slices.
Those examples must not become an application implementation.

## Required external references

Before designing or editing the module, read and use these references if internet access is available:

- BMAD Builder documentation:
  https://bmad-builder-docs.bmad-method.org/llms-full.txt

- BMAD Method documentation:
  https://docs.bmad-method.org//llms-full.txt

Use the BMAD Builder documentation as the primary authority for:

- module structure
- skill structure
- setup conventions
- registration conventions
- manifest conventions
- module-help.csv conventions
- validation conventions
- packaging conventions
- marketplace/plugin conventions
- tests/evals/triggers conventions

Use the BMAD Method documentation as the primary authority for:

- BMAD phases
- BMAD workflow names
- BMAD artifact locations
- BMAD help behavior
- BMAD project-context behavior
- BMAD implementation workflow behavior
- BMAD correct-course behavior

If either URL is unavailable, continue using this self-contained goal.
Still include durable references to those URLs in generated docs so future maintainers can re-check official guidance.

When there is a conflict:

1. Preserve the LENS product design in this goal.
2. Follow BMAD Builder conventions for module packaging and validation.
3. Follow repository-local conventions for file placement, style, tests, and naming where they do not conflict with BMAD Builder.
4. Do not invent structure when a BMAD Builder pattern already exists.

## Codex operating expectations

Work like a senior engineer implementing a repository change from a GitHub issue.

Before editing:

1. Inspect the repository.
2. Locate existing BMAD Builder module examples, skill examples, setup examples, validation scripts, test/eval patterns, docs conventions, and manifest patterns.
3. Use `rg`, `find`, repo docs, or available search tools to identify conventions.
4. Read the official BMAD Builder and BMAD Method references if available.
5. Form a concise implementation plan.
6. Then implement.

While editing:

1. Make deterministic, minimal, coherent changes.
2. Do not overwrite unrelated user changes.
3. Do not use destructive git commands.
4. Prefer existing repository patterns over invented patterns.
5. Keep YAML, CSV, JSON, Markdown, and manifests valid.
6. Add tests/evals/fixtures where the repo supports them.
7. Add documentation sufficient for a maintainer to understand and install the module.
8. If the repo uses AGENTS.md or similar persistent context files, add or update a concise LENS module section only when appropriate.
9. Do not include long generated-code dumps in your final response.
10. Report changed files and validation results at the end.

## Core design principle

The central unit of LENS is the slice.

A slice is a small, useful, testable, end-to-end unit of work.

A slice may be:

- a tiny utility
- a workflow step
- a product journey segment
- an integration path
- a proof of concept
- a feature-sized implementation

A slice is allowed to exist without:

- system
- domain
- service
- capability
- program
- initiative
- roadmap

A slice can remain a slice forever.

No growth without pressure.

Pressure means repeated evidence such as:

- repeated artifact reuse
- repeated workflow
- repeated dependency
- repeated risk
- repeated ownership concern
- repeated cross-slice coordination
- repeated user journey
- repeated implementation friction

Promotion is optional, explicit, and evidence-driven.

Do not promote a slice into a capability, domain, program, or system just because the model can imagine one.

## Two growth modes

LENS must support two modes equally.

### Mode 1: Top-down LENS

Use this when the user has a large ambiguous system idea.

Flow:

large ambiguous vision
→ discovery epoch
→ raw capture
→ extracted hypotheses
→ challenged assumptions
→ role and stakeholder map
→ outcome map
→ operating loops
→ journeys
→ selected vertical slice
→ capability and impact analysis
→ focused BMAD packet
→ BMAD planning and implementation
→ LENS validation
→ landscape update
→ Salmon correction when reality disagrees

Top-down LENS must not jump directly from brainstorm to PRD.

It must require:

1. captured context
2. extracted hypotheses
3. context sufficiency check
4. challenged assumptions
5. focused outcome
6. mapped journey
7. selected vertical slice
8. capability and impact map
9. focused BMAD packet
10. then BMAD PRD / UX / architecture / epics

### Mode 2: Bottom-up LENS

Use this when the user only knows one useful thing.

Flow:

small useful slice
→ local artifact
→ optional adjacency
→ repeated pressure
→ optional capability candidate
→ optional capability
→ optional domain
→ optional system
→ BMAD execution only when needed

Example:

User says:

"I want to download images from 3D printing model websites."

LENS should create a slice, not a platform:

```yaml
slice:
  id: slice.download_model_images
  goal: Download model listing images locally.
  status: active
  scope:
    includes:
      - fetch model listing page
      - identify image URLs
      - download images locally
      - record source metadata
    excludes:
      - model description generation
      - safety detection
      - moderation workflow
      - marketplace publishing
      - model intelligence platform
```

If a later slice consumes the artifact, create adjacency:

```yaml
adjacency:
  from: slice.download_model_images
  to: slice.generate_model_description
  reason: shared_artifact
  shared_artifacts:
    - artifact.model_image_set
  strength: weak
  recommendation: keep_independent_for_now
```

Only after repeated pressure should LENS suggest promotion:

```yaml
promotion_candidate:
  type: capability
  id: capability.model_image_processing
  confidence: medium
  automatic: false
  reason:
    - repeated artifact reuse
    - repeated workflow
    - repeated classification need
    - repeated metadata dependency
```

## BMAD integration model

LENS is installed as a BMAD module.

Use BMAD-native skill naming.

Prefer `bmad-lens-*` skill names unless BMAD Builder docs require a different convention.

BMAD owns:

* Analysis
* Planning
* Solutioning
* Implementation
* product brief
* PRFAQ
* PRD
* UX
* architecture
* epics
* stories
* sprint planning
* story creation
* dev story
* code review
* correct-course
* retrospective

LENS owns:

* discovery
* capture
* extraction
* context sufficiency
* relationship modeling
* slice selection
* capability derivation
* impact analysis
* workstream awareness
* traceability
* landscape evolution
* focused BMAD packet preparation
* BMAD artifact sync
* story guarding
* slice/journey/outcome validation
* Salmon propagation
* Doctor audits
* Auspex visibility

BMAD plans and executes build work.
LENS discovers and maintains product-system context.
LENS validates that built work still serves the intended slice, journey, and outcome.

LENS must feed BMAD.
LENS must not replace BMAD.

## Required BMAD phase mapping

Map LENS to BMAD’s lifecycle:

### BMAD Analysis

BMAD workflows may include:

* bmad-help
* bmad-brainstorming
* bmad-party-mode
* bmad-advanced-elicitation
* bmad-domain-research
* bmad-market-research
* bmad-technical-research
* bmad-product-brief
* bmad-prfaq
* bmad-investigate

LENS uses this phase for:

* intake
* capture
* extraction
* discovery epoch creation
* context sufficiency checks
* research planning
* system thesis formation
* role and outcome discovery

### BMAD Planning

BMAD creates:

* PRD
* spec
* planning artifacts

LENS provides:

* focused BMAD packet
* system context, if available
* active outcome, if available
* active journey, if available
* active slice
* explicit exclusions
* acceptance evidence
* required capabilities
* decisions needed
* risks and boundaries

### BMAD Solutioning

BMAD creates:

* UX
* architecture
* epics and stories after architecture
* implementation readiness checks

LENS provides:

* journey context
* vertical slice scope
* impact map
* workstream map
* capability candidates
* landscape ledgers
* architecture input
* epic/story input
* readiness check input

### BMAD Implementation

BMAD runs:

* sprint planning
* story creation
* story implementation
* code review
* retrospective
* correct-course

LENS provides:

* story traceability guard
* slice scope guard
* acceptance evidence guard
* validation reports
* Salmon upstream correction
* landscape reconciliation
* Auspex stakeholder visibility

## Required skill surface

Implement the module as a multi-skill BMAD module.

Use the repository’s BMAD Builder conventions for whether each item is a skill, workflow, agent, utility, template, or eval.

Expose discoverable capabilities through BMAD help registration.

Required core/help/setup skills:

* `bmad-lens-help`
* `bmad-lens-setup`
* `bmad-lens-intake`

Required slice-scale skills:

* `bmad-lens-slice-new`
* `bmad-lens-slice-frame`
* `bmad-lens-slice-scope`
* `bmad-lens-detect-adjacency`
* `bmad-lens-detect-repetition`
* `bmad-lens-suggest-promotion`

Required discovery skills:

* `bmad-lens-discover`
* `bmad-lens-capture`
* `bmad-lens-synthesize`
* `bmad-lens-context-check`
* `bmad-lens-research-plan`

Required top-down modeling skills:

* `bmad-lens-map-system`
* `bmad-lens-map-outcomes`
* `bmad-lens-map-loops`
* `bmad-lens-map-journeys`
* `bmad-lens-slice-journey`

Required landscape and impact skills:

* `bmad-lens-map-capabilities`
* `bmad-lens-analyze-impact`
* `bmad-lens-promote-landscape`
* `bmad-lens-map-rebuild`

Required BMAD bridge skills:

* `bmad-lens-prepare-bmad`
* `bmad-lens-sync-bmad`
* `bmad-lens-guard-story`

Required validation skills:

* `bmad-lens-validate-slice`
* `bmad-lens-validate-journey`
* `bmad-lens-validate-outcome`

Required adaptation and visibility skills:

* `bmad-lens-salmon`
* `bmad-lens-doctor`
* `bmad-lens-auspex`

Do not add legacy aliases for old domain/service/feature commands unless BMAD Builder conventions require aliases.
This is a net-new module with no backward compatibility requirement.

## Optional LENS agents or personas

If BMAD Builder supports module agents/personas, include these conceptual roles using the repo’s agent conventions:

* System Cartographer

  * Maps systems, roles, loops, pillars, and system thesis.

* Outcome Strategist

  * Turns ambiguous vision into role-specific outcomes.

* Journey Architect

  * Builds end-to-end journey graphs across roles, data, decisions, and system surfaces.

* Slice Designer

  * Finds thin vertical slices that prove useful work.

* Capability Mapper

  * Derives capabilities and service/domain candidates from slices and journeys.

* Impact Analyst

  * Finds codebase, data, privacy, workstream, dependency, repo, file, contract, and test impact.

* BMAD Liaison

  * Packages LENS context into BMAD workflows and syncs BMAD artifacts back.

* Outcome Validator

  * Checks whether built work satisfies slice, journey, and outcome evidence.

Use the smallest BMAD-native implementation that satisfies the behavior.
Do not overbuild autonomous agents if repo conventions favor simpler skills/workflows.

## Required knowledge state model

Implement schemas/templates/docs that support these states:

```yaml
knowledge_states:
  raw:
    meaning: "Captured directly from a user, session, whiteboard, document, codebase, BMAD artifact, or source."
  extracted:
    meaning: "Identified as a possible concept, role, outcome, journey, artifact, risk, relationship, or capability."
  hypothesized:
    meaning: "Structured by LENS but not yet confirmed."
  challenged:
    meaning: "Reviewed for contradictions, missing pieces, or weak assumptions."
  reviewed:
    meaning: "Human reviewed and accepted as plausible."
  approved:
    meaning: "Accepted as current working truth."
  validated:
    meaning: "Supported by implementation, stakeholder evidence, test evidence, or repeated evidence."
  superseded:
    meaning: "Replaced by a newer model."
  archived:
    meaning: "Kept for history but no longer active."

confidence_levels:
  low:
    meaning: "Weak signal, inferred, ambiguous, or contested."
  medium:
    meaning: "Likely correct but not fully validated."
  high:
    meaning: "Confirmed by stakeholder, artifact, implementation, or repeated evidence."
```

AI hypotheses must not be treated as facts.

## Required core entities

Implement schemas/templates/examples for these entities:

* system
* system_thesis
* discovery_epoch
* session
* source
* extraction
* slice
* artifact
* adjacency
* relationship
* role
* stakeholder
* outcome
* operating_loop
* journey
* journey_step
* capability
* domain
* service
* workstream
* program
* decision
* assumption
* unknown
* risk
* evidence
* salmon_signal
* auspex_status
* bmad_packet
* validation_result

The ontology must be flexible.

Top-down hierarchy:

```text
system
→ role / stakeholder
→ outcome
→ operating loop
→ journey
→ journey step
→ vertical slice
→ capability
→ domain / service / repo / file / test
→ BMAD artifact
→ story
→ implementation evidence
→ validation result
```

Bottom-up growth:

```text
slice
→ artifact
→ adjacency
→ repeated pressure
→ promotion candidate
→ capability
→ capability cluster
→ domain
→ program
→ system
```

Feature, domain, service, and system are not mandatory planning roots.
They may appear later as landscape metadata.

## Required identity and metadata rules

IDs are identity.
Paths are addresses.

Every major entity should have stable IDs and metadata.

Minimum metadata:

```yaml
id: string
kind: string
name: string
status: raw|extracted|hypothesized|challenged|reviewed|approved|validated|superseded|archived
confidence: low|medium|high
created_at: string
updated_at: string
source_refs: []
relationships: []
open_questions: []
```

Paths must not be used as identity.

Planning artifacts should have explicit validity metadata:

```yaml
status: draft|reviewed|approved|blocked|superseded|archived
validity: current|stale|needs_review
```

Planning artifact validity must not depend on git branch placement.

## Required knowledge topology

Implement the Two-Tree Model with a Derived Map.

### Tree 1: Work Archive

The Work Archive preserves what happened.

It is append-only or mostly append-only.

It contains:

* raw sessions
* brainstorming artifacts
* stakeholder interviews
* uploads
* extracted concepts
* slice runs
* BMAD packets
* implementation evidence
* validation results
* Salmon signals
* historical decisions
* superseded assumptions
* discarded ideas

Expected storage:

```text
_bmad-output/lens/archive/
├── capture/
│   ├── sessions/
│   ├── uploads/
│   └── sources.yaml
├── extractions/
│   ├── extraction-index.yaml
│   └── extraction-*.yaml
├── slices/
├── bmad-packets/
├── implementation-evidence/
├── validation-results/
└── salmon-signals/
```

### Tree 2: Living Landscape

The Living Landscape preserves current truth.

It is curated, reorganizable, and human-readable.

It contains:

* system ledgers
* program ledgers
* domain ledgers
* capability ledgers
* service ledgers
* journey ledgers
* workstream ledgers
* decision ledgers
* risk ledgers

Expected storage:

```text
_bmad-output/lens/landscape/
├── systems/
├── programs/
├── domains/
├── capabilities/
├── services/
├── journeys/
├── workstreams/
├── decisions/
└── risks/
```

### Tree 3: Derived Map

The Derived Map is generated from archive and landscape metadata.

It is not source truth.
It is rebuildable.
It must not be hand-edited.

Expected storage:

```text
_bmad-output/lens/graph/
├── derived-map.yaml
├── derived-map.json
├── relationship-index.yaml
├── traceability-index.yaml
├── freshness-index.yaml
└── warnings.yaml
```

Core rule:

Archive records history.
Landscape records current truth.
Graph projects machine-readable relationships.

Slices are reality.
Landscape is interpretation.
Graph is projection.

## Required discovery epoch behavior

Implement discovery as an epoch model.

A discovery epoch is an ongoing container that may include many sessions over days or weeks.

It should track:

* id
* system
* status
* purpose
* sessions
* current_focus
* context_sufficiency
* open_questions
* recommended_next_bmad_skills
* recommended_next_lens_skills
* promotion_candidates
* blockers

Example shape:

```yaml
discovery_epoch:
  id: epoch.001
  system: system.learning_improvement_platform
  status: active
  purpose: >
    Discover enough context to identify the first validated outcome, journey,
    and vertical slice.
  sessions:
    - session.001.initial-brainstorm
    - session.002.role-outcome-followup
  current_focus:
    level: outcome
    target: outcome.teacher_turns_evidence_into_action
  context_sufficiency:
    system_thesis: medium
    role_map: medium
    outcome_matrix: medium
    journey_map: low
    slice_readiness: low
    architecture_readiness: not_ready
    bmad_prd_readiness: not_ready
  open_questions:
    - Are families primary users or secondary stakeholders?
    - What counts as student evidence?
    - What teacher/student relationship grants evidence visibility?
  next_recommended_bmad_skills:
    - bmad-brainstorming
    - bmad-advanced-elicitation
    - bmad-review-adversarial-general
```

## Required discovery loop

Each discovery workflow should follow this loop:

1. Ask focused questions.
2. Capture user responses.
3. Extract candidate concepts.
4. Mark each concept as raw, extracted, hypothesized, challenged, reviewed, approved, validated, superseded, or archived.
5. Summarize the current interpretation.
6. Ask for correction or confirmation when appropriate.
7. Run or recommend BMAD review/elicitation/research skills when the model is weak.
8. Record open questions.
9. Promote only reviewed concepts into living LENS artifacts.
10. Recommend the next BMAD or LENS skill.

## Required context sufficiency behavior

Implement `bmad-lens-context-check`.

It must block premature PRD creation.

It should evaluate:

* system thesis readiness
* role map readiness
* stakeholder map readiness
* outcome matrix readiness
* operating loop readiness
* journey readiness
* slice readiness
* capability readiness
* architecture readiness
* BMAD PRD readiness
* open questions
* unresolved decisions
* high-severity risks
* research gaps
* unchallenged assumptions

It should produce:

```text
_bmad-output/lens/gates/context-sufficiency-{n}.md
_bmad-output/lens/gates/context-score.yaml
```

It must be able to say:

```text
We are not ready for PRD yet.
We need another discovery session focused on evidence definitions and role visibility.
```

## Required LENS layers

Represent these layers in docs, templates, schemas, examples, or skill behavior.

### Layer 0: BMAD Core Runtime

BMAD owns formal workflow execution.

BMAD creates:

* product brief
* PRFAQ
* PRD
* UX
* architecture
* epics
* stories
* sprint status
* implementation
* code review
* retrospective
* correct-course artifacts

LENS must not replace BMAD.

### Layer 1: Capture Layer

Purpose:
Capture messy human input without pretending it is truth.

Inputs:

* brainstorming conversations
* stakeholder interviews
* founder notes
* whiteboard photos
* partial docs
* old diagrams
* screenshots
* codebase hints
* operational workflows
* domain constraints
* regulatory constraints
* support tickets
* existing BMAD artifacts

Storage:

```text
_bmad-output/lens/archive/capture/
├── sessions/
├── uploads/
└── sources.yaml
```

### Layer 2: Extraction Layer

Purpose:
Extract candidate concepts from raw material.

Extract:

* candidate roles
* candidate users
* candidate stakeholders
* candidate outcomes
* candidate pain points
* candidate workflows
* candidate operating loops
* candidate risks
* candidate assumptions
* candidate capabilities
* candidate services
* candidate constraints
* candidate open questions
* candidate artifacts
* candidate adjacencies

Storage:

```text
_bmad-output/lens/archive/extractions/
├── extraction-001.yaml
├── extraction-002.yaml
└── extraction-index.yaml
```

### Layer 3: Intent Layer

Purpose:
Form the current system model when a system is known or emerging.

Produce:

* system thesis
* role map
* stakeholder map
* outcome matrix
* operating loop hypotheses
* principles
* non-goals
* constraints
* assumptions
* open questions
* risk register

Storage:

```text
_bmad-output/lens/intent/
├── system-thesis.md
├── system-thesis.yaml
├── role-map.yaml
├── stakeholder-map.yaml
├── outcome-matrix.yaml
├── operating-loops.yaml
├── principles.md
├── assumptions.yaml
├── open-questions.yaml
└── risks.yaml
```

### Layer 4: Journey Layer

Purpose:
Turn outcomes into end-to-end paths across roles, data, decisions, and system surfaces.

A journey answers:

* Who starts where?
* What are they trying to accomplish?
* What other roles or systems are involved?
* What evidence or data moves?
* What decisions are made?
* What state changes?
* What does success look like?

Storage:

```text
_bmad-output/lens/journeys/
├── journey-catalog.yaml
└── {journey-id}/
    ├── journey.yaml
    ├── journey.md
    ├── journey-map.mmd
    └── open-questions.yaml
```

### Layer 5: Slice Layer

Purpose:
Turn huge journeys, tiny ideas, or local useful work into buildable vertical slices.

A slice is a thin, testable, end-to-end unit of useful work.

Storage:

```text
_bmad-output/lens/slices/
├── slice-roadmap.yaml
└── {slice-id}/
    ├── slice.yaml
    ├── slice.md
    ├── acceptance-evidence.yaml
    ├── risks.yaml
    └── bmad-packet.md
```

### Layer 6: Capability / Landscape Layer

Purpose:
Create durable living ledgers for current system truth.

Capabilities are derived from journeys, slices, repeated pressure, and implementation evidence.
They are not guessed up front.

Storage:

```text
_bmad-output/lens/landscape/
├── systems/
├── programs/
├── domains/
├── capabilities/
├── services/
├── journeys/
├── workstreams/
├── decisions/
└── risks/
```

### Layer 7: Derived Map Layer

Purpose:
Generate machine-readable graph/index projections from source files.

Storage:

```text
_bmad-output/lens/graph/
├── derived-map.json
├── derived-map.yaml
├── relationship-index.yaml
├── traceability-index.yaml
├── freshness-index.yaml
└── warnings.yaml
```

### Layer 8: BMAD Bridge Layer

Purpose:
Package LENS artifacts into BMAD-consumable context.

Produce:

* project-wide context
* active slice context
* slice-specific BMAD packet
* PRD input
* UX input
* architecture input
* epic/story input
* readiness check input

Storage:

```text
_bmad-output/
├── project-context.md
└── lens/
    └── bmad-bridge/
        ├── system-context.md
        ├── active-slice-context.md
        ├── prd-input.md
        ├── ux-input.md
        ├── architecture-input.md
        ├── epic-story-input.md
        └── readiness-check-input.md
```

### Layer 9: Implementation Guard Layer

Purpose:
Ensure BMAD stories remain traceable to the active LENS slice and do not silently expand scope.

Storage:

```text
_bmad-output/lens/implementation/
├── story-traceability/
├── validation/
└── salmon-signals/
```

### Layer 10: Salmon / Correction Layer

Purpose:
Let downstream implementation discoveries update upstream system truth.

Storage:

```text
_bmad-output/lens/salmon/
├── signals/
├── propagation/
└── decisions/
```

### Layer 11: Auspex Visibility Layer

Purpose:
Provide read-only stakeholder visibility into current truth, risk, freshness, evidence, and BMAD progress.

Auspex is not the source of truth.
It reads the Derived Map.

Storage:

```text
_bmad-output/lens/auspex/
├── status.json
├── status.yaml
├── dashboard.html
├── stakeholder-summary.md
└── read-only-report.md
```

## Required slice model

A slice must include:

* id
* kind
* status
* confidence
* goal
* scope includes
* scope excludes
* artifacts produced
* artifacts consumed
* relationships
* acceptance evidence
* risks
* decisions needed
* source refs
* optional system
* optional outcome
* optional journey
* optional capabilities
* optional domains
* optional services
* optional BMAD packet references
* validation status

For top-down slices, include:

* journey
* outcome
* role
* operating loop, if known
* why_first / sequencing rationale
* vertical path
* required capabilities

For bottom-up slices, allow the slice to be complete without system/outcome/journey/capability.

Example top-down slice:

```yaml
slice:
  id: slice.evidence_visible_to_teacher
  kind: slice
  status: selected
  confidence: medium
  journey: journey.evidence_to_teacher_action
  outcome: outcome.teacher_turns_evidence_into_action
  goal: >
    Teacher can view a student evidence artifact with source metadata.
  why_first: >
    This establishes the minimum evidence object, visibility rule, and teacher
    workspace touchpoint before introducing AI guidance or coaching rollups.
  starts_with:
    - student evidence artifact exists
    - teacher has relationship to student or class
    - artifact has source metadata
  ends_with:
    - teacher can view artifact
    - teacher can see source and timestamp
    - unauthorized users cannot view artifact
    - missing artifact state is handled clearly
  scope:
    includes:
      - evidence artifact visibility
      - source metadata
      - timestamp or freshness display
      - role-based visibility check
      - safe missing state
    excludes:
      - AI interpretation
      - goal alignment
      - next-action guidance
      - coaching dashboards
      - district analytics
      - family portal
  vertical_path:
    experience:
      - teacher evidence inbox
      - evidence detail page
    data:
      - EvidenceArtifact
      - EvidenceSource
      - StudentContext
      - TeacherAccessPolicy
    policy:
      - teacher can view evidence for assigned students
      - source metadata must be visible
      - stale or missing evidence must be indicated
  acceptance_evidence:
    - permitted teacher can open evidence artifact
    - artifact source is visible
    - artifact timestamp is visible
    - unauthorized teacher cannot access artifact
    - missing artifact renders safe empty state
```

Example bottom-up slice:

```yaml
slice:
  id: slice.download_model_images
  kind: slice
  status: active
  confidence: high
  goal: Download model listing images locally.
  scope:
    includes:
      - fetch model listing page
      - identify image URLs
      - download images locally
      - record source metadata
    excludes:
      - model description generation
      - safety detection
      - moderation workflow
      - marketplace publishing
      - model intelligence platform
  produces:
    - artifact.model_image_set
  acceptance_evidence:
    - downloads images from supported listing URL
    - stores source URL metadata
    - handles missing images safely
```

## Required promotion model

Promotion is explicit.
Promotion is not automatic.

Promotion ladder:

```text
slice
→ adjacency
→ repeated pattern
→ capability candidate
→ capability
→ capability cluster
→ domain
→ program
→ system
```

A slice does not have to climb the ladder.

Promotion requires evidence.

Implement promotion gates that produce artifacts such as:

```yaml
promotion_gate:
  candidate: capability.model_image_processing
  promoted_from:
    - slice.download_model_images
    - slice.generate_model_description
    - slice.detect_duplicate_models
  evidence:
    - repeated use of artifact.model_image_set
    - repeated image processing workflow
    - repeated metadata dependency
  recommendation: consider_promotion
  automatic: false
  human_review_required: true
```

## Required relationship model

Relationships are first-class.

They must carry lifecycle, confidence, provenance, and validation state.

Relationship lifecycle:

```text
raw
→ extracted
→ hypothesized
→ challenged
→ reviewed
→ promoted
→ planned
→ implemented
→ validated
→ superseded
→ archived
```

Required relationship types:

```yaml
relationship_types:
  - expresses
  - serves
  - realized_by
  - decomposed_into
  - produces_artifact
  - consumes_artifact
  - adjacent_to
  - requires
  - participates_in
  - implemented_by
  - planned_by
  - decomposed_by
  - implemented_by_story
  - validated_by
  - impacted_by
  - supersedes
```

Example:

```yaml
relationship:
  id: rel.outcome.teacher_evidence_action.realized_by.journey.evidence_to_teacher_action
  from: outcome.teacher_turns_evidence_into_action
  type: realized_by
  to: journey.evidence_to_teacher_action
  status: hypothesized
  confidence: medium
  discovered_from:
    - extraction.001
  review:
    status: human_review_needed
  promotion:
    landscape_status: not_promoted
  validation:
    implementation_status: not_validated
```

## Required relationship gates

Relationships must be worked through gates:

Discovery gate:
Do we have enough signal to model this relationship?

Challenge gate:
Is this relationship coherent, or is it an AI guess?

Promotion gate:
Should this relationship update the living landscape?

BMAD gate:
Should this relationship constrain PRD, UX, architecture, or stories?

Implementation gate:
Did the code prove or disprove the relationship?

Salmon gate:
Did downstream work reveal upstream truth?

Validation gate:
Did the relationship help satisfy an outcome?

## Required impact and workstream analysis

Implement `bmad-lens-analyze-impact`.

For every proposed slice, LENS should generate a Journey Impact Graph or Slice Impact Map.

It should ask:

* What files likely change?
* What services or components are involved?
* What contracts are touched?
* What existing stories or workstreams conflict?
* What artifacts are produced or consumed?
* What tests prove the slice?
* What observability proves it in production?
* What feature flags or rollout controls are needed?
* What data, privacy, policy, or trust boundaries are affected?
* What architecture decisions are needed before implementation?

Expected output shape:

```yaml
workstream_impact:
  directly_impacted:
    - checkout-payment-recovery
  possibly_conflicting:
    - wallet-redesign
    - payment-provider-migration
  shared_files:
    - packages/payment-contracts/src/retry.ts
    - apps/checkout/src/payment/PaymentFailurePanel.tsx
  shared_contracts:
    - PaymentAttempt
    - PaymentMethod
    - OrderPaymentStatus
  decisions_needed:
    - Should retry behavior belong to checkout or payment orchestration?
    - Should wallet redesign own saved-card selector changes?
```

Before implementation, LENS should force a related workstream review gate:

* no impact: continue
* impact found: create dependency note, block, split slice, update BMAD packet, or recommend BMAD correct-course

## Required BMAD packet behavior

Implement `bmad-lens-prepare-bmad`.

LENS must never dump the whole messy system into BMAD.

It prepares a focused packet for the current slice.

For bottom-up slices, the packet may be small:

```yaml
bmad_packet:
  active_slice: slice.download_model_images
  include:
    - slice_goal
    - current artifact expectations
    - acceptance_evidence
    - explicit_exclusions
  exclude:
    - model description
    - content moderation
    - safety classification
    - platform architecture
```

For top-down systems, the packet may include:

```yaml
bmad_packet:
  active_slice: slice.evidence_visible_to_teacher
  include:
    - system_thesis_if_available
    - focused_outcome_if_available
    - journey_context_if_available
    - slice_scope
    - explicit_out_of_scope
    - required_capabilities
    - risks
    - decisions_needed
    - acceptance_evidence
  exclude:
    - adjacent future slices
    - unvalidated system assumptions
    - speculative platform architecture
    - unpromoted capability clusters
```

Expected Markdown packet:

```md
# LENS BMAD Packet

## Active Slice

slice.evidence_visible_to_teacher

## Slice Goal

Teacher can view a student evidence artifact with source metadata.

## Included Scope

- Evidence artifact exists
- Teacher can view permitted evidence
- Source metadata is visible
- Timestamp/freshness is visible
- Unauthorized access is blocked
- Missing/stale evidence has safe UI handling

## Explicitly Out of Scope

- AI interpretation
- Goal/standard alignment
- Next-action guidance
- Coaching signals
- Leadership dashboards
- Family views

## Required Capabilities

- Evidence Artifact Model
- Evidence Source Metadata
- Teacher/Student Relationship
- Role-Based Visibility
- Teacher Workspace
- Stale/Missing Evidence Handling

## Required Decisions

- Minimum evidence shape
- Teacher access policy
- Source freshness display
- Missing artifact behavior

## Acceptance Evidence

- Permitted teacher can view artifact.
- Unauthorized teacher cannot view artifact.
- Source is visible.
- Timestamp is visible.
- Missing artifact renders safe empty state.
- Stale artifact is clearly marked.
```

This packet then feeds BMAD workflows such as:

* `bmad-product-brief`
* `bmad-prfaq`
* `bmad-create-prd`
* `bmad-create-ux-design`
* `bmad-create-architecture`
* `bmad-create-epics-and-stories`
* `bmad-check-implementation-readiness`

## Required project-context behavior

LENS must generate or update `_bmad-output/project-context.md` when appropriate.

It should include guidance like:

```md
# Project Context for AI Agents

## LENS Module Active

This project uses the LENS module for system-scale discovery, slice orchestration, and traceability.

## Traceability Rule

Every BMAD story must trace to an active LENS slice.

For top-down work, trace:

system → role → outcome → journey → slice → capability → acceptance evidence

For bottom-up work, trace at minimum:

slice → artifact → acceptance evidence

## Scope Rule

Do not expand the active slice into adjacent future work unless a LENS Salmon signal,
promotion decision, or BMAD correct-course decision changes the plan.

## Architecture Rule

Architecture decisions must update the relevant LENS capability, domain, service, or decision ledger.

## Change Rule

If implementation reveals that an upstream assumption is wrong, raise a LENS Salmon signal before silently changing architecture or scope.
```

## Required implementation guard behavior

Implement `bmad-lens-guard-story`.

It must check:

* story traces to an active LENS slice
* story does not silently expand scope
* acceptance evidence is present
* relevant risks are acknowledged
* privacy/security/policy boundaries are preserved when applicable
* story references the BMAD packet or active slice context
* related capabilities are present when promoted
* if story changes upstream assumptions, Salmon is recommended

For top-down work, trace may be:

```text
system
→ role
→ outcome
→ journey
→ slice
→ capability
→ story
→ evidence
```

For bottom-up work, trace may be:

```text
slice
→ artifact
→ acceptance evidence
```

Example output:

```yaml
story:
  id: story.evidence_detail_view
  bmad_story_file: _bmad-output/planning-artifacts/epics/epic-001/story-evidence-detail-view.md
lens_trace:
  system: system.learning_improvement_platform
  outcome: outcome.teacher_turns_evidence_into_action
  journey: journey.evidence_to_teacher_action
  slice: slice.evidence_visible_to_teacher
  capabilities:
    - capability.evidence_artifact_model
    - capability.evidence_source_metadata
    - capability.teacher_workspace
guard_result:
  status: pass
checks:
  - name: story_traces_to_active_slice
    status: pass
  - name: story_does_not_expand_scope
    status: pass
  - name: acceptance_evidence_present
    status: pass
  - name: privacy_boundary_acknowledged
    status: pass
```

## Required Salmon behavior

Implement `bmad-lens-salmon`.

Salmon is the upstream correction mechanism.

It exists because implementation reveals reality.

Salmon flow:

```text
story
→ slice
→ journey
→ outcome
→ capability
→ domain
→ program
→ system
```

Salmon decides:

* Is this local?
* Does it update landscape truth?
* Does it require BMAD correct-course?
* Does it invalidate a slice?
* Does it change a journey?
* Does it affect architecture?
* Does it impact another workstream?

Salmon does not replace BMAD correct-course.
Salmon detects and propagates upstream impact.
BMAD correct-course handles formal replanning when scope, architecture, or assumptions materially change.

A Salmon signal must include:

* id
* raised_from
* severity
* discovery
* impacted_nodes
* recommended_action
* suggested BMAD workflow if needed
* propagation report
* decision record
* sync status

Example:

```yaml
salmon_signal:
  id: salmon.001
  raised_from: story.evidence_detail_view
  severity: high
  discovery: >
    Teacher access cannot be determined from class roster alone.
    Some support staff need limited visibility without being assigned classroom teachers.
  impacted_nodes:
    - slice.evidence_visible_to_teacher
    - capability.teacher_student_relationship
    - capability.role_based_visibility
    - decision.teacher_access_policy
    - domain.identity_and_access
  recommended_action:
    type: correct_course
    reason: >
      The current acceptance criteria and architecture assumptions depend on
      an incomplete access model.
  bmad_action:
    suggested_workflow: bmad-correct-course
```

## Required Doctor behavior

Implement `bmad-lens-doctor`.

It must audit:

* orphaned entities
* missing source references
* missing IDs
* duplicate IDs
* mismatched parent-child refs
* missing referenced ledgers
* stale landscape ledgers
* unresolved high-severity decisions
* completed slices not promoted into the landscape when promotion is warranted
* BMAD artifacts not synced into the relationship graph
* stories without LENS traceability
* derived map inconsistencies
* relationship contradictions
* stale or missing freshness metadata

It should produce:

```text
_bmad-output/lens/graph/warnings.yaml
_bmad-output/lens/graph/doctor-report.md
```

## Required Auspex behavior

Implement `bmad-lens-auspex`.

Auspex is read-only stakeholder visibility.

It should show:

* system status
* active outcomes
* active journeys
* active slices
* artifact freshness
* open decisions
* risks
* blockers
* BMAD progress
* validation evidence
* Salmon signals
* source traceability

It should produce:

```text
_bmad-output/lens/auspex/status.yaml
_bmad-output/lens/auspex/status.json
_bmad-output/lens/auspex/stakeholder-summary.md
```

If repo conventions support HTML report generation, also produce:

```text
_bmad-output/lens/auspex/dashboard.html
```

Auspex must not be source truth.
It reads the Derived Map.

## Required illustrative examples and evals

Include small illustrative examples in docs, fixtures, or evals.

### Top-down example

Use a NorthStar-scale education example only as an illustrative fixture.

Input:

```text
I want to build a platform for schools where students, teachers, coaches,
and leaders all work from the same learning improvement system. It should use
evidence from student work, help teachers know what to do next, help coaches
support teachers, and help leaders see where the school needs support.
```

Expected LENS progression:

1. Candidate system:

   * learning improvement platform

2. Candidate roles:

   * student
   * teacher
   * coach
   * school leader
   * district leader
   * family as low-confidence stakeholder unless confirmed

3. Candidate operating loop:

   * assess
   * set goals
   * learn
   * apply
   * evidence
   * improve

4. Candidate outcomes:

   * student understands next goal
   * teacher turns evidence into action
   * coach identifies support need
   * leader sees implementation health

5. Candidate risks:

   * AI overreach
   * student privacy
   * teacher surveillance
   * dashboard sprawl

6. Focused outcome:

   * teacher turns evidence into action

7. Journey:

   * evidence captured
   * teacher views evidence
   * system interprets evidence
   * evidence aligns to goal or standard
   * system suggests next action
   * teacher accepts, adjusts, or rejects
   * decision is recorded
   * coaching signal may be created

8. Slice roadmap:

   * evidence visible to teacher
   * evidence interpreted for teacher
   * evidence aligned to goal
   * guidance recommended to teacher
   * teacher decision recorded
   * coach signal created

9. First BMAD packet:

   * active slice: evidence visible to teacher
   * include: slice scope, acceptance evidence, risks, decisions needed
   * exclude: AI recommendations, coaching dashboards, district analytics, family portal

This example must not implement NorthStarET.

### Bottom-up example

Input:

```text
I want to download images from 3D printing model websites.
```

Expected LENS progression:

1. Create `slice.download_model_images`.
2. Do not create system/domain/service/capability by default.
3. Record produced artifact `artifact.model_image_set`.
4. If later slices reuse that artifact, create weak adjacency.
5. Only after repeated pressure, suggest optional promotion.
6. Promotion must be human-reviewed and evidence-based.

## Required README/module documentation

Add or update module documentation explaining:

* What LENS is
* What LENS is not
* Why slice is the central operational unit
* How LENS supports top-down discovery
* How LENS supports bottom-up growth
* What “no growth without pressure” means
* How LENS fits inside BMAD
* How to install/register it as a BMAD module
* How to invoke LENS through BMAD help
* How to start a discovery epoch
* How to create a bottom-up slice
* How to detect adjacency and repeated pressure
* How to promote into the Living Landscape
* How to move from capture → extraction → intent → journey → slice → capability → BMAD packet
* How to run BMAD workflows after LENS prepares a packet
* How to sync BMAD artifacts back into LENS
* How to use guard-story, Salmon, Doctor, and Auspex
* Where artifacts are stored
* Which files are source truth vs derived projections
* Why the original PDF or any uploaded chat file is not required

## Required module packaging

Follow BMAD Builder conventions exactly.

At minimum, include the repository-standard equivalent of:

```text
skills/
├── bmad-lens-setup/
│   ├── SKILL.md
│   ├── assets/
│   │   ├── module.yaml
│   │   └── module-help.csv
│   └── scripts/
├── bmad-lens-help/
├── bmad-lens-intake/
├── bmad-lens-slice-new/
├── bmad-lens-slice-frame/
├── bmad-lens-slice-scope/
├── bmad-lens-detect-adjacency/
├── bmad-lens-detect-repetition/
├── bmad-lens-suggest-promotion/
├── bmad-lens-discover/
├── bmad-lens-capture/
├── bmad-lens-synthesize/
├── bmad-lens-context-check/
├── bmad-lens-research-plan/
├── bmad-lens-map-system/
├── bmad-lens-map-outcomes/
├── bmad-lens-map-loops/
├── bmad-lens-map-journeys/
├── bmad-lens-slice-journey/
├── bmad-lens-map-capabilities/
├── bmad-lens-analyze-impact/
├── bmad-lens-promote-landscape/
├── bmad-lens-map-rebuild/
├── bmad-lens-prepare-bmad/
├── bmad-lens-sync-bmad/
├── bmad-lens-guard-story/
├── bmad-lens-validate-slice/
├── bmad-lens-validate-journey/
├── bmad-lens-validate-outcome/
├── bmad-lens-salmon/
├── bmad-lens-doctor/
└── bmad-lens-auspex/
```

Adjust the exact structure to match BMAD Builder and this repository’s conventions.

Include the repository-standard plugin/marketplace manifest if required.

Ensure `module-help.csv` exposes LENS capabilities in a way that `bmad-help` can discover.

Use clear menu codes and action-oriented descriptions.

## Required validation

Use the repository’s validation conventions.

If BMAD Builder provides Validate Module, VM, or equivalent scripts, run them.

Validate at least:

* module structure
* setup skill
* registration behavior
* skill folders
* `SKILL.md` files
* `module.yaml`
* `module-help.csv`
* marketplace/plugin manifest if applicable
* missing references
* duplicate menu/help codes
* BMAD help discoverability
* YAML validity
* JSON validity
* CSV validity
* tests/evals/triggers if present
* generated schemas/templates
* no dependency on uploaded PDF or chat files
* no NorthStarET application scaffolding

Add or update tests/evals if the repo supports them.

Required eval coverage:

1. A large ambiguous product idea routes to LENS discovery rather than direct PRD generation.
2. A bottom-up small slice remains a slice and does not automatically promote to platform/system.
3. Repeated pressure can produce a promotion candidate, but not automatic promotion.
4. A focused top-down slice produces a BMAD packet with included scope, explicit exclusions, required capabilities, decisions, risks, and acceptance evidence.
5. BMAD story guard accepts a traceable story and flags an untraceable or scope-expanding story.
6. Salmon raises upstream impact when implementation reveals a wrong assumption.
7. Doctor detects at least one invalid topology condition.
8. Auspex produces read-only status from the Derived Map.

## Acceptance criteria

The task is complete when all of the following are true:

1. The repository contains a BMAD-native LENS module.
2. The module follows BMAD Builder conventions.
3. The module is registered or registerable with BMAD help.
4. The module uses `bmad-lens-*` naming or the repo-approved BMAD naming equivalent.
5. The module is self-contained and does not require the original PDF or uploaded chat files.
6. The module does not create NorthStarET.
7. The module supports top-down complex-system discovery.
8. The module supports bottom-up slice-scale growth.
9. The module makes slice the central operational unit.
10. The module enforces “no growth without pressure.”
11. The module supports optional evidence-driven promotion.
12. The module includes discovery epochs.
13. The module captures raw material without treating it as truth.
14. The module extracts hypotheses with status, confidence, and provenance.
15. The module includes context sufficiency gates that prevent premature PRD generation.
16. The module maps systems, roles, outcomes, operating loops, journeys, and slices when top-down context exists.
17. The module allows slices without systems, domains, services, capabilities, programs, initiatives, or roadmaps.
18. The module derives capabilities and landscape ledgers from slices, journeys, repeated pressure, and implementation evidence.
19. The module implements the Work Archive.
20. The module implements the Living Landscape.
21. The module generates the Derived Map as a projection, not source truth.
22. The module uses stable IDs rather than paths as identity.
23. The module includes relationship lifecycle, relationship types, and relationship gates.
24. The module includes adjacency detection.
25. The module includes repetition detection.
26. The module includes impact and workstream analysis.
27. The module prepares focused BMAD packets.
28. The module updates or generates `_bmad-output/project-context.md` guidance when appropriate.
29. The module guards BMAD stories for traceability and scope.
30. The module validates slices, journeys, and outcomes.
31. The module implements Salmon upstream correction.
32. The module implements Doctor audits.
33. The module implements Auspex visibility.
34. The module includes docs showing the BMAD interaction flow.
35. The module includes illustrative top-down and bottom-up examples.
36. The module includes tests/evals according to repo conventions.
37. Relevant validation commands pass, or any blocker is explicitly documented with exact command/output.

## Final response expected from Codex

When finished, report:

* Files changed
* Module structure created
* BMAD Builder conventions followed
* BMAD Method integration points used
* Validation commands run and results
* Tests/evals added
* Assumptions made
* Any blockers or follow-up required

Do not include long dumps of generated files in the final response.
Reference paths instead.

````

::contentReference[oaicite:3]{index=3}

[1]: https://openai.com/business/guides-and-resources/how-openai-uses-codex/ "How OpenAI uses Codex | OpenAI"
