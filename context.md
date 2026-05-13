Below is the final integrated description of **LENS** as it has evolved across the chat: a BMAD-native module that supports both **top-down system discovery** and **bottom-up slice-scale growth**, with **Salmon** as the upstream correction mechanism.

---

# Final LENS Definition

**LENS** stands for:

```text
Large-system
Exploration,
Navigation,
Slicing,
and validation framework
```

LENS is a **BMAD-native module** for discovering, decomposing, executing, validating, and continuously reorganizing complex software work.

It is not a standalone product framework. It is not a replacement for BMAD. BMAD remains the execution method: PRD, UX, architecture, epics, stories, implementation, code review, correction, and retrospective. LENS wraps around BMAD as the system-understanding, slice-selection, relationship, traceability, and adaptation layer. 

The simplest description is:

```text
BMAD makes the work buildable.
LENS makes the work understandable, traceable, adaptable, and coherent.
```

Or even shorter:

```text
LENS understands the system.
BMAD builds the slice.
LENS checks whether the built slice still matches reality.
```

---

# Core Purpose

LENS helps teams move from either:

```text
large ambiguous vision
```

or:

```text
one tiny useful slice
```

into well-scoped BMAD execution without losing context, overbuilding too early, or allowing downstream implementation discoveries to disappear.

It supports both mental models:

```text
Top-down:
Known or suspected system
→ roles
→ outcomes
→ loops
→ journeys
→ slices
→ capabilities
→ BMAD execution
```

and:

```text
Bottom-up:
Small useful slice
→ local artifact
→ optional adjacency
→ repeated pressure
→ optional capability
→ optional domain
→ optional system
→ BMAD execution only when needed
```

That dual support is the heart of the final design.

---

# What LENS Is Not

LENS is not:

```text
a PRD generator
a standalone app
a domain/service/feature organizer
a forced enterprise architecture tool
a system that assumes everything must grow
a replacement for BMAD
a tool that turns every small idea into a platform
```

LENS must **not** force structure before reality demands it.

The final principle is:

```text
No growth without pressure.
```

Pressure means repeated evidence such as:

```text
repeated artifact reuse
repeated workflow
repeated dependency
repeated risk
repeated ownership concern
repeated cross-slice coordination
repeated user journey
repeated implementation friction
```

Until pressure exists, a slice can remain a slice.

---

# The Central Unit: Slice

The final LENS model makes **slice** the operational unit.

A slice is:

```text
a small, testable, end-to-end unit of useful work
```

It may be:

```text
tiny utility
workflow step
product journey segment
integration path
proof of concept
feature-sized implementation
```

A slice is allowed to exist without:

```text
system
domain
service
capability
program
initiative
roadmap
```

This is what fixes the bottom-up case.

Example:

```yaml
slice:
  id: slice.download_model_images
  goal: Download images from a 3D model website.
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

That slice is complete on its own.

It does not need to become anything else.

---

# The Two Growth Modes

## Mode 1: Top-Down LENS

Top-down mode is used when the user has a large ambiguous system idea.

Example input:

```text
I want to build a platform for schools where students, teachers, coaches,
and leaders all work from the same learning improvement system.
```

LENS should not jump directly to a PRD.

Instead, it opens a discovery epoch:

```text
capture raw thinking
→ extract hypotheses
→ challenge assumptions
→ identify roles
→ map outcomes
→ discover operating loops
→ map journeys
→ select one vertical slice
→ prepare BMAD packet
→ BMAD plans and builds
→ LENS validates and updates landscape
```

The uploaded framework emphasizes that LENS should not ask humans to define the whole product upfront; it should capture raw thinking, extract candidate concepts, challenge assumptions, focus one outcome, map one journey, slice one path, build a little, validate, update the living landscape, and repeat. 

Top-down LENS produces artifacts like:

```text
system thesis
role map
stakeholder map
outcome matrix
operating loop
journey map
slice roadmap
capability candidates
impact map
BMAD packet
```

Example top-down compression:

```text
Broad system:
  education improvement platform

Focused outcome:
  teacher turns student evidence into instructional action

Journey:
  evidence to teacher action

First slice:
  evidence visible to teacher

BMAD packet:
  build only evidence visibility, source metadata, access rules, and safe empty states
```

This matches the earlier NorthStar-style flow where a broad education platform idea becomes focused through discovery, journey mapping, slicing, capability mapping, impact analysis, BMAD planning, validation, and landscape update. 

---

## Mode 2: Bottom-Up LENS

Bottom-up mode is used when the user only knows one useful thing.

Example input:

```text
I want to download images from 3D printing model websites.
```

LENS should not assume this is a platform.

It should create a slice:

```yaml
slice:
  id: slice.download_model_images
  status: active
  goal: Download model listing images locally.
```

Later, if the user says:

```text
Now I want to generate descriptions from those images.
```

LENS creates another slice:

```yaml
slice:
  id: slice.generate_model_description
  goal: Generate a model description from downloaded images.
  consumes:
    - artifact.model_image_set
```

LENS may detect an adjacency:

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

No promotion yet.

Only after repeated pressure appears:

```text
download images
generate descriptions
deduplicate models
tag model categories
detect unsafe content
review flagged models
```

can LENS suggest:

```yaml
promotion_candidate:
  type: capability
  id: capability.model_image_processing
  confidence: medium
  reason:
    - repeated artifact reuse
    - repeated workflow
    - repeated classification need
    - repeated metadata dependency
```

This preserves the slice-scale mindset:

```text
A slice may remain small forever.
A slice may connect later.
A slice may promote later.
Promotion is optional, explicit, and evidence-driven.
```

---

# Final Ontology

LENS has a flexible ontology that supports both top-down and bottom-up work.

```yaml
core_entities:
  slice:
    meaning: Smallest operational unit of useful, testable work.

  artifact:
    meaning: Something produced or consumed by a slice.

  adjacency:
    meaning: A weak relationship between slices, usually because they share artifacts, workflows, users, risks, or dependencies.

  relationship:
    meaning: A typed connection between entities with lifecycle, confidence, and provenance.

  capability:
    meaning: A durable system ability that emerges from repeated slice pressure.

  journey:
    meaning: An end-to-end path through which an outcome becomes real.

  outcome:
    meaning: A desired change for a user, role, business, system, or stakeholder.

  role:
    meaning: A human or system actor.

  stakeholder:
    meaning: A person or group with influence, constraints, or decision power.

  operating_loop:
    meaning: A repeated cycle the product enables or improves.

  domain:
    meaning: A coherent area of product meaning, ownership, capability, or workflow.

  service:
    meaning: A technical/runtime boundary, derived later from architecture and implementation.

  workstream:
    meaning: A coordinated stream of work that may span slices, capabilities, services, domains, and teams.

  program:
    meaning: A larger coherent initiative or product area formed from multiple domains or capability clusters.

  system:
    meaning: The larger product-system when one is known or has emerged.

  decision:
    meaning: A durable choice that constrains future work.

  assumption:
    meaning: A belief used for planning that may be validated, invalidated, or superseded.

  risk:
    meaning: A possible harm to coherence, safety, delivery, trust, privacy, cost, or usability.

  evidence:
    meaning: Proof that a slice, journey, outcome, or relationship holds.

  salmon_signal:
    meaning: A downstream discovery that may need to update upstream truth.

  auspex_status:
    meaning: Read-only stakeholder visibility over current state, risk, evidence, freshness, and progress.
```

The key rule:

```text
Feature, domain, service, and system are not mandatory planning roots.
They may appear later as landscape metadata.
```

---

# The Final Knowledge Topology

The screenshots and prior design converge on a **Two-Tree Model with a Derived Map**. This is essential because humans need stable places to read current truth, while machines need generated indexes and graphs. The uploaded framework describes the Work Archive, Living Landscape, Derived Map, stable IDs, metadata-based validity, Salmon, and Auspex as the sustainable knowledge topology for LENS. 

## Tree 1: Work Archive

The Work Archive preserves what happened.

It is append-only or mostly append-only.

It contains:

```text
raw sessions
brainstorms
uploaded notes
whiteboards
slice runs
BMAD packets
stories
implementation evidence
validation results
discarded ideas
Salmon signals
historical decisions
superseded assumptions
```

Example:

```text
_bmad-output/lens/archive/
  capture/
  extractions/
  slices/
  bmad-packets/
  implementation-evidence/
  validation-results/
  salmon-signals/
```

A slice belongs here because it is operational history.

The archive answers:

```text
What did we do?
Why did we do it?
What was known then?
What did this slice produce?
What did implementation reveal?
```

---

## Tree 2: Living Landscape

The Living Landscape preserves current truth.

It is curated, reorganizable, and human-readable.

It contains:

```text
system ledgers
program ledgers
domain ledgers
capability ledgers
service ledgers
journey ledgers
workstream ledgers
decision ledgers
risk ledgers
```

Example:

```text
_bmad-output/lens/landscape/
  systems/
  programs/
  domains/
  capabilities/
  services/
  journeys/
  workstreams/
  decisions/
  risks/
```

The landscape answers:

```text
What does the system currently mean?
What capabilities exist?
What domains are forming?
What journeys are active?
What assumptions remain open?
What risks constrain work?
What has changed recently?
```

This is where humans go first.

---

## Tree 3: Derived Map

The Derived Map is generated from archive and landscape metadata.

It is not source truth.

It is rebuildable.

Example:

```text
_bmad-output/lens/graph/
  derived-map.yaml
  derived-map.json
  relationship-index.yaml
  traceability-index.yaml
  freshness-index.yaml
  warnings.yaml
```

The graph powers:

```text
AI context
impact analysis
dependency detection
traceability
Auspex dashboards
BMAD packet generation
Doctor audits
relationship traversal
Salmon propagation
```

The final rule:

```text
Archive records history.
Landscape records current truth.
Graph projects machine-readable relationships.
```

Or:

```text
Slices are reality.
Landscape is interpretation.
Graph is projection.
```

---

# Stable Identity Over Mutable Location

This is one of the most important architecture rules.

```text
IDs are identity.
Paths are addresses.
```

A thing can move without changing identity.

Example:

```yaml
capability:
  id: capability.model_image_processing
  current_path: _bmad-output/lens/landscape/capabilities/model-image-processing/
```

Later it may move under a domain:

```yaml
capability:
  id: capability.model_image_processing
  current_path: _bmad-output/lens/landscape/domains/model-intelligence/capabilities/model-image-processing/
```

The ID survives.

This allows the topology to evolve without breaking references.

The uploaded topology redesign explicitly identifies stable identity over mutable location, promotable topology, human-first consolidation, machine-derived projection, and upstream impact as core architecture principles. 

---

# Planning Artifact Validity

Planning artifacts are not valid because of branch placement.

They are valid because of metadata.

```yaml
artifact:
  id: artifact.prd.evidence_visible_to_teacher
  type: bmad_prd
  status: reviewed
  validity: current
  source_of_truth: false
  planned_for:
    - slice.evidence_visible_to_teacher
```

Allowed statuses:

```text
draft
reviewed
approved
blocked
superseded
archived
```

This avoids the old planning-branch trap where git topology pretends to be governance.

---

# Relationship Lifecycle

Relationships are first-class.

They do not appear fully formed.

They mature.

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

After review and first slice validation:

```yaml
relationship:
  id: rel.outcome.teacher_evidence_action.realized_by.journey.evidence_to_teacher_action
  status: reviewed
  confidence: high
  promotion:
    landscape_status: promoted
  validation:
    implementation_status: partially_validated
    validated_by:
      - slice.evidence_visible_to_teacher
```

The relationship lifecycle and gate model were explicitly developed in the prior framework: relationships move from extracted and hypothesized through review, promotion, planning, implementation, validation, and supersession; they pass through discovery, challenge, promotion, BMAD, implementation, Salmon, and validation gates. 

---

# Relationship Types

```yaml
relationship_types:
  - id: expresses
    example: system_thesis expresses system intent

  - id: serves
    example: outcome serves role

  - id: realized_by
    example: outcome realized_by journey

  - id: decomposed_into
    example: journey decomposed_into slice

  - id: produces_artifact
    example: slice.download_model_images produces_artifact artifact.model_image_set

  - id: consumes_artifact
    example: slice.generate_model_description consumes_artifact artifact.model_image_set

  - id: adjacent_to
    example: slice.download_model_images adjacent_to slice.generate_model_description

  - id: requires
    example: slice.evidence_visible_to_teacher requires capability.role_based_visibility

  - id: participates_in
    example: capability.evidence_artifact_model participates_in domain.evidence_and_portfolios

  - id: implemented_by
    example: capability.role_based_visibility implemented_by service.identity_access

  - id: planned_by
    example: slice.evidence_visible_to_teacher planned_by artifact.bmad_prd

  - id: decomposed_by
    example: artifact.bmad_prd decomposed_by artifact.bmad_epics

  - id: implemented_by_story
    example: slice.evidence_visible_to_teacher implemented_by_story story.evidence_detail_view

  - id: validated_by
    example: acceptance_evidence validates slice

  - id: impacted_by
    example: domain.identity_access impacted_by salmon.001

  - id: supersedes
    example: decision.support_relationship_policy supersedes decision.teacher_roster_only_policy
```

---

# Promotion Model

Promotion is explicit.

Promotion is not automatic.

Promotion means a local thing becomes part of the Living Landscape.

The promotion ladder is:

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

```yaml
promotion_gate:
  candidate: capability.model_image_processing
  promoted_from:
    - slice.download_model_images
    - slice.generate_model_description
    - slice.detect_duplicate_models
    - slice.detect_unsafe_models
  evidence:
    - repeated use of artifact.model_image_set
    - repeated image processing workflow
    - repeated metadata dependency
    - repeated classification concern
  recommendation: consider_promotion
  automatic: false
```

This directly addresses the over-modeling risk: the prior design called out that teams may create too much structure too early, and the mitigation is to keep depth optional and add layers only when justified. 

---

# BMAD Integration

LENS is installed as a BMAD module.

Skills should use BMAD-native naming:

```text
bmad-lens-help
bmad-lens-intake
bmad-lens-discover
bmad-lens-capture
bmad-lens-synthesize
bmad-lens-context-check
bmad-lens-research-plan
bmad-lens-map-system
bmad-lens-map-outcomes
bmad-lens-map-loops
bmad-lens-map-journeys
bmad-lens-slice-journey
bmad-lens-map-capabilities
bmad-lens-analyze-impact
bmad-lens-promote-landscape
bmad-lens-prepare-bmad
bmad-lens-sync-bmad
bmad-lens-guard-story
bmad-lens-validate-slice
bmad-lens-validate-journey
bmad-lens-validate-outcome
bmad-lens-salmon
bmad-lens-doctor
bmad-lens-auspex
```

BMAD owns:

```text
analysis
planning
solutioning
implementation
story creation
dev story
code review
correct-course
retrospective
```

LENS owns:

```text
discovery
context sufficiency
relationship modeling
slice selection
impact analysis
traceability
landscape evolution
Salmon propagation
Doctor audits
Auspex visibility
```

The prior prompt explicitly defined this relationship: LENS discovers and maintains the product-system, BMAD plans and executes build work, and LENS validates whether built work still serves the intended outcome. 

---

# LENS Layers

```yaml
layers:
  0_bmad_core_runtime:
    owns:
      - BMAD workflows
      - PRD
      - UX
      - architecture
      - epics
      - stories
      - implementation
      - code review
      - correct-course

  1_capture_layer:
    owns:
      - raw sessions
      - brainstorming
      - stakeholder notes
      - whiteboards
      - uploaded docs
      - existing artifacts

  2_extraction_layer:
    owns:
      - candidate concepts
      - roles
      - outcomes
      - workflows
      - risks
      - assumptions
      - unknowns

  3_intent_layer:
    owns:
      - system thesis
      - role map
      - stakeholder map
      - outcome matrix
      - operating loops
      - principles
      - constraints

  4_journey_layer:
    owns:
      - journey catalog
      - journey maps
      - journey steps
      - cross-role paths

  5_slice_layer:
    owns:
      - selected slice
      - slice scope
      - acceptance evidence
      - explicit out-of-scope
      - slice roadmap

  6_capability_landscape_layer:
    owns:
      - promoted capabilities
      - domains
      - services
      - workstreams
      - ledgers

  7_derived_map_layer:
    owns:
      - generated graph
      - relationship index
      - traceability index
      - freshness index

  8_bmad_bridge_layer:
    owns:
      - focused BMAD packet
      - project-context.md
      - PRD input
      - UX input
      - architecture input
      - epic/story input

  9_implementation_guard_layer:
    owns:
      - story traceability
      - scope guard
      - acceptance evidence guard
      - risk guard

  10_salmon_correction_layer:
    owns:
      - upstream impact detection
      - recursive consistency traversal
      - correct-course recommendation
      - landscape reconciliation

  11_auspex_visibility_layer:
    owns:
      - read-only stakeholder status
      - evidence state
      - freshness
      - risks
      - blockers
      - BMAD progress
```

The layered architecture from the prior work defines these same layers and clarifies that LENS structures complexity, BMAD formalizes and executes delivery, and LENS watches whether execution still matches system intent. 

---

# BMAD Packet

LENS never dumps the whole messy system into BMAD.

It prepares a focused packet for the current slice.

```yaml
bmad_packet:
  id: bmad_packet.slice.evidence_visible_to_teacher
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

For bottom-up slices, the packet may be extremely small:

```yaml
bmad_packet:
  active_slice: slice.download_model_images
  include:
    - slice_goal
    - current artifact expectations
    - acceptance evidence
    - explicit exclusions
  exclude:
    - model description
    - content moderation
    - safety classification
    - platform architecture
```

For top-down systems, it may include more context:

```yaml
bmad_packet:
  active_slice: slice.evidence_visible_to_teacher
  include:
    - system thesis
    - focused outcome
    - journey
    - slice scope
    - capabilities
    - risks
    - decisions
    - acceptance evidence
  exclude:
    - AI recommendations
    - coaching dashboards
    - district analytics
    - family portal
```

The prior design emphasized that LENS prepares a focused BMAD packet and BMAD then creates formal planning artifacts such as PRD, architecture, epics, and stories; LENS later syncs the BMAD artifacts back into its traceability graph. 

---

# Implementation Guard

Once BMAD creates stories, LENS guards them.

A BMAD story must trace to:

```text
system, if known
→ outcome, if known
→ journey, if known
→ slice
→ capability, if promoted
→ acceptance evidence
```

For small bottom-up work, the trace may be:

```text
slice
→ artifact
→ acceptance evidence
```

For top-down work, the trace may be:

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

Example guard result:

```yaml
guard_result:
  story: story.evidence_detail_view
  status: pass
  lens_trace:
    system: system.learning_improvement_platform
    outcome: outcome.teacher_turns_evidence_into_action
    journey: journey.evidence_to_teacher_action
    slice: slice.evidence_visible_to_teacher
    capabilities:
      - capability.evidence_artifact_model
      - capability.role_based_visibility
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

LENS guards BMAD stories for traceability, scope boundaries, and outcome evidence while BMAD owns story-by-story execution. 

---

# Salmon

Salmon is the upstream correction mechanism.

It exists because implementation reveals reality.

Sometimes a slice discovers something that invalidates upstream assumptions.

Examples:

```text
teacher access cannot be determined from roster alone
downloaded model images are not enough without listing metadata
safety classification requires human review
a service boundary is wrong
a journey is incomplete
a capability does not exist yet
a privacy rule is missing
a related workstream is impacted
```

Salmon lets that discovery swim upstream.

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

Salmon does not replace BMAD correct-course.

Salmon decides:

```text
Is this local?
Does it update landscape truth?
Does it require BMAD correct-course?
Does it invalidate a slice?
Does it change a journey?
Does it affect architecture?
Does it impact another workstream?
```

BMAD correct-course handles formal replanning when scope, architecture, or assumptions materially change.

The prior framework defines Salmon as the upstream-change layer: implementation discoveries propagate from story to slice, journey, outcome, capability/domain/service ledger, and possibly BMAD plan; if needed, LENS recommends BMAD correct-course and then syncs the result back. 

Example Salmon signal:

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

Salmon is not just an alert.

It is:

```text
recursive upstream consistency validation
```

---

# Doctor

Doctor audits the topology.

It finds:

```text
orphaned slices
missing IDs
duplicate IDs
broken references
stale ledgers
missing source refs
unpromoted completed slices
BMAD artifacts not synced
stories without LENS traceability
derived map drift
relationship contradictions
unresolved high-severity decisions
```

Example:

```yaml
doctor_warning:
  id: warning.unresolved_decision
  severity: high
  message: >
    slice.evidence_visible_to_teacher requires decision.teacher_access_policy
    before implementation can proceed safely.
```

Doctor is the consistency safety net.

---

# Auspex

Auspex is the read-only visibility plane.

It reads the Derived Map.

It is not source truth.

It shows:

```text
system status
active slices
active journeys
risks
open decisions
BMAD progress
artifact freshness
validation evidence
Salmon signals
blocked work
```

Example:

```yaml
auspex_status:
  active_focus:
    slice: slice.evidence_visible_to_teacher
  bmad_status:
    prd: in_progress
    architecture: not_started
    epics_and_stories: not_started
  risks:
    - risk.privacy_boundary
    - risk.evidence_definition_ambiguity
  open_decisions:
    - decision.teacher_access_policy
  salmon_signals:
    open: 0
    resolved: 0
```

The prior design positions Auspex as a stakeholder visibility layer that shows system status, active journeys and slices, risks, blockers, freshness, validation evidence, BMAD links, and source traceability without requiring stakeholders to navigate the repo. 

---

# Top-Down Example

```text
User:
I want a school learning platform where students, teachers, coaches,
and leaders all work from shared evidence.
```

LENS flow:

```bash
bmad-lens-intake
bmad-lens-discover
bmad-lens-synthesize
bmad-lens-context-check
bmad-lens-map-system
bmad-lens-map-outcomes
bmad-lens-map-loops
bmad-lens-map-journeys
bmad-lens-slice-journey
bmad-lens-map-capabilities
bmad-lens-analyze-impact
bmad-lens-prepare-bmad
```

Result:

```yaml
system:
  id: system.learning_improvement_platform
  status: hypothesized

focused_outcome:
  id: outcome.teacher_turns_evidence_into_action

journey:
  id: journey.evidence_to_teacher_action

selected_slice:
  id: slice.evidence_visible_to_teacher

explicit_out_of_scope:
  - AI interpretation
  - coaching dashboards
  - leadership analytics
  - family portal
```

Then BMAD:

```bash
bmad-product-brief
bmad-create-prd
bmad-create-ux-design
bmad-create-architecture
bmad-create-epics-and-stories
bmad-check-implementation-readiness
```

Then LENS:

```bash
bmad-lens-sync-bmad
bmad-lens-guard-story
bmad-lens-validate-slice
bmad-lens-doctor
bmad-lens-auspex
```

---

# Bottom-Up Example

```text
User:
I want to download images from a 3D printing model website.
```

LENS flow:

```bash
bmad-lens-slice-new "download model images"
bmad-lens-prepare-bmad --slice slice.download_model_images
```

BMAD builds the tiny slice.

Later:

```text
User:
Now I want to generate descriptions from those images.
```

LENS:

```bash
bmad-lens-slice-new "generate model descriptions"
bmad-lens-detect-adjacency
```

Result:

```yaml
adjacency:
  from: slice.download_model_images
  to: slice.generate_model_description
  shared_artifact:
    - artifact.model_image_set
  recommendation: keep_independent_for_now
```

Later, repeated pressure emerges.

```bash
bmad-lens-detect-repetition
bmad-lens-suggest-promotion
```

Result:

```yaml
promotion_candidate:
  type: capability
  id: capability.model_image_processing
  confidence: medium
  automatic: false
```

The system grows only when it has earned growth.

---

# Final Command Surface

```text
bmad-lens-help

# Slice-scale
bmad-lens-slice-new
bmad-lens-slice-frame
bmad-lens-slice-scope
bmad-lens-prepare-bmad

# Discovery
bmad-lens-intake
bmad-lens-discover
bmad-lens-capture
bmad-lens-synthesize
bmad-lens-context-check
bmad-lens-research-plan

# Top-down modeling
bmad-lens-map-system
bmad-lens-map-outcomes
bmad-lens-map-loops
bmad-lens-map-journeys
bmad-lens-slice-journey

# Bottom-up evolution
bmad-lens-detect-adjacency
bmad-lens-detect-repetition
bmad-lens-suggest-promotion
bmad-lens-promote-landscape

# Impact and bridge
bmad-lens-map-capabilities
bmad-lens-analyze-impact
bmad-lens-prepare-bmad
bmad-lens-sync-bmad

# Implementation guard
bmad-lens-guard-story
bmad-lens-validate-slice
bmad-lens-validate-journey
bmad-lens-validate-outcome

# Adaptation
bmad-lens-salmon
bmad-lens-doctor
bmad-lens-auspex
```

---

# Final Architecture in One Diagram

```text
                         ┌──────────────────────────┐
                         │          BMAD             │
                         │ PRD / UX / Architecture   │
                         │ Epics / Stories / Code    │
                         └─────────────▲────────────┘
                                       │
                              focused BMAD packet
                                       │
┌──────────────────────────────────────┴──────────────────────────────────────┐
│                                   LENS                                      │
│                                                                              │
│  Top-down mode:                                                              │
│  system → role → outcome → loop → journey → slice                            │
│                                                                              │
│  Bottom-up mode:                                                             │
│  slice → artifact → adjacency → repeated pressure → optional promotion        │
│                                                                              │
│  Knowledge topology:                                                         │
│  Work Archive  +  Living Landscape  +  Derived Map                           │
│                                                                              │
│  Adaptation:                                                                 │
│  Salmon upstream correction + Doctor audits + Auspex visibility              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

# Final LENS Philosophy

```text
Do not force the whole system up front.
Do not let small work lose context.
Do not promote structure before reality demands it.
Do not let implementation discoveries die downstream.
Do not let BMAD plan more than the selected slice needs.
Do not make the graph source truth.
Do not make folders identity.
Do not treat AI hypotheses as facts.
```

Instead:

```text
Start at the right scale.
Preserve what happened.
Curate what is currently true.
Generate maps for machines.
Promote only under pressure.
Correct upstream through Salmon.
Use BMAD to build focused slices.
Validate, learn, and update the landscape.
```

---

# Final One-Sentence Description

```text
LENS is a BMAD-native slice orchestration and evolving knowledge-topology module
that supports both top-down complex-system discovery and bottom-up slice-scale growth,
using Work Archive, Living Landscape, Derived Map, explicit promotion, Doctor audits,
Auspex visibility, and Salmon upstream correction to keep software work coherent as it is built.
```
