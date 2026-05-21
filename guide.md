# Brainstorming Session Notes

stepsCompleted: [1, 2, 3, 4]
selected_approach: "progressive-flow"
techniques_used: ["First Principles Thinking", "Morphological Analysis", "Concept Blending", "Solution Matrix"]
session_topic: Re-examining Lens/BMAD project artifact topology for organic, multi-feature, team-scale work
session_goals: Discover structural alternatives or augmentations that solve the knowledge-scatter / feature-pocket-universe problem
ideas_generated: []
context_file:

---

# Brainstorming Session -- 2026-05-12

## Session Overview

**Topic:** Re-examining Lens/BMAD project artifact topology for organic, multi-feature, team-scale work

**Goals:**

- Identify the structural failure modes of the current domain > service > feature hierarchy
- Explore alternative or augmented topologies that support long-lived, interconnected, team-scale projects
- Discover how project knowledge/artifacts can be consolidated across feature boundaries

## Problem Framing

The current domain > service > feature hierarchy was designed for discrete, one-shot deliverables. It breaks down when:

1. **Interdependence**: features share design decisions -- widget1.0 shapes widget1.1
2. **Artifact scatter**: each feature owns its own specs, so service-level knowledge is fragmented
3. **Branch isolation**: features live in their own plan branches -- a new feature cannot access sibling feature artifacts without merging first
4. **Cumulative complexity**: widget1.0 (read API) + widget1.1 (update API) + widgetUI -- the UI feature needs specs from both predecessors but they are in pocket universes
5. **Team scale**: what one developer can mentally track becomes unmanageable for a team

The one-and-done model works fine. The organic, iterative, multi-contributor model does not.

Two distinct failure modes emerged during discussion:

- **Failure Mode A -- Knowledge Consolidation:** the accumulated design truth of a service or domain is scattered across feature folders and branches, so humans never have a single stable place to look
- **Failure Mode B -- Cross-feature Dependency at Authoring Time:** when a new feature needs the design context of sibling or predecessor features, that context is often inaccessible, incomplete, or trapped in another branch

These matter because they are different problems. Consolidation is about durable human-readable truth. Cross-feature dependency is about day-to-day authoring and safe evolution. The eventual model needs to solve both.

## Technique Selection

**Approach:** Progressive Technique Flow

- **Phase 1:** First Principles Thinking -- strip assumptions, find fundamental truths
- **Phase 2:** Morphological Analysis -- map the full parameter space of topology alternatives
- **Phase 3:** Concept Blending -- merge strongest patterns into candidate hybrid topologies
- **Phase 4:** Solution Matrix -- evaluate candidates against real constraints

---

# Brainstorming

## Phase 1 -- First Principles Thinking

### Fundamental Truths

1. Knowledge must be **findable**
2. Knowledge must be **trustworthy**: current vs superseded vs draft
3. Knowledge must be **composable**: assemble a coherent service view
4. Knowledge must be **owned**: or it rots
5. Knowledge must **survive feature completion**
6. Knowledge must be **consolidated**: scattered knowledge is manageable for a machine with an index; humans cannot work that way. A human needs a place, not a search query.

### False Assumptions in the Current Model

- **A1 -- The feature is the right unit of knowledge ownership:** FALSE. Features are work tickets, not knowledge containers.
- **A2 -- Domain > Service > Feature is a natural knowledge hierarchy:** FALSE. It is an org chart, not a knowledge architecture.
- **A3 -- Branches are a good isolation boundary for planning artifacts:** FALSE. Branch isolation solves code conflicts; docs do not conflict. This creates the pocket-universe problem for free.
- **A4 -- Features complete and close:** FALSE. The thing described keeps evolving; we are versioning work, not knowledge.
- **A5 -- Each feature is self-contained enough to carry its own full design context:** FALSE. widget1.1 cannot be understood without widget1.0.
- **A6 -- The contributor will know which other features they depend on:** FALSE. This creates massive cognitive load and assumes the contributor already knows the topology to navigate it.

### Core Structural Pivots

| Pivot | Current Model | What First Principles Demands |
|---|---|---|
| Knowledge unit | Feature | Multi-layer: Feature + Service + Domain + Program |
| Feature role | Knowledge owner | Scoped contributor -- delivery and work context only |
| Branch scope | Feature artifacts live in plan branch | Durable knowledge lives outside the branch model |
| Consolidation trigger | Never / manual | Mandatory promotion on feature completion |
| Human navigation | Search / know topology | Single stable location per layer |

### Multi-Layer Knowledge Architecture

| Level | Knowledge Purpose | Primary Audience | Durability |
|---|---|---|---|
| **Feature** | Scope, delivery, WIP design notes | Contributors on this ticket | Ephemeral -- promotes up on close |
| **Service** | Accumulated design truth; API contracts, architectural decisions, data models | Engineers building on or against this service | Durable, ever-growing |
| **Domain** | How services operate together; the user journey | Product, design, business stakeholders | Durable, narrative-oriented |
| **Program / Product** | How domains assemble into a finished product | Strategy, program-level stakeholders | High-level, persistent |

**Key insight:** The domain is the keeper of the user journey. The user does not care about the API. They care about getting their widget. Domain-level knowledge speaks their language.

**Key complication:** The domain may not be the top level. A finished product may require multiple domains, implying a Program layer above domain that the current Lens model has no concept of. The hierarchy is potentially:

program > domain > service > feature

Each layer maintains its own living knowledge artifacts.

---

## Phase 2 -- Morphological Analysis

_Systematically map the full parameter space of topology alternatives._

### Axis Constraints and Eliminations

#### Axis 2 -- Branching Boundary for Planning Artifacts

- Current reality is effectively the control repo plan branch model, but only when merge-back is configured, which has not reliably been the case
- External docs stores and hybrid scratch/governance models are rejected
- PR-as-approval-gate for design was tried and created too much rigidity and operational mess
- The planning branch itself is no longer justified if requirements gates are not being managed through PRs
- Governance-as-home for human-facing docs was also rejected because it creates terrible UX
- Decision: eliminate the planning branch entirely for now; revisit richer operating-model controls far later if they become justified
- Draft/published state should replace branch isolation for planning artifacts

The original appeal of the planning branch was to support a more mature operating model with strong review gates. In practice, that model is aspirational rather than real. The branch therefore imposes complexity without delivering the value it was meant to create.

#### Axis 4 -- Hierarchy Depth

- The fixed 3-level hierarchy is broken
- Story as an artifact-bearing layer is off the table
- The model must support optional depth and, more importantly, additive depth over time
- A quick script must be able to grow into a service, domain, or full program without re-architecture
- Topology is living, not fixed at project start

#### Axis 5 -- Cross-feature Reference / Salmon Process

- Knowledge usually flows downstream: Program -> Domain -> Service -> Feature
- But real feature work can force upstream change
- An upstream note should trigger a recursive consistency check both upward and downward
- The signal itself is non-blocking by default, but the recursive check can discover conditions that must block progress
- Salmon is not just a notification; it is an active consistency-maintenance workflow

The key nuance is that Salmon is paralleled by default, but not toothless. The signal itself does not freeze work; the recursive check may discover inconsistencies severe enough to justify a block. In other words, the block comes from the discovered impact, not from the mere act of raising the signal.

### Emergent Design Principles

1. **No planning branch** -- planning artifacts should live in a single accessible place
2. **Layered knowledge** -- Feature, Service, Domain, and Program each serve different knowledge purposes
3. **Promotable topology** -- layers are added as work grows
4. **Feature as contributor** -- features contribute to higher layers; they do not own durable truth alone
5. **Salmon workflow** -- upstream signals trigger recursive validation
6. **Human-first consolidation** -- humans need a place, not a query

---

## Phase 3 -- Concept Blending

_Merge the strongest surviving patterns into a coherent topology model._

### Model Evolution During the Session

The conversation did not jump directly to the final two-tree model. It evolved through a sequence:

1. **Model C as strongest early candidate** -- a stream-and-ledger hybrid where a flexible graph of entities is paired with living ledgers at each layer
2. **Feature-first inversion** -- an important correction that features are the always-present unit of work, while higher layers are optional scaffolding grown around them
3. **Reorganization tension discovered** -- if features move whenever a new service/domain/program layer is introduced, paths become unstable and Lens path-based addressing breaks down
4. **Final refinement** -- features never move; the hierarchy reorganizes above them; the governance map becomes the join between the permanent feature archive and the reorganizable knowledge landscape

This evolution matters because the final model is not just a new folder layout. It is a reconciliation of two competing truths:

- work starts feature-first and grows upward over time
- human-readable stable knowledge still needs stable higher-order homes

### Candidate Direction -- The Two-Tree Model with Derived Map

The strongest synthesis is a two-tree structure:

docs/
  features/                             <- permanent, flat, never reorganized
    auspex/
    widget-1.0/
    widget-1.1/
    widget-ui/

  <landscape>/                          <- reorganizable service/domain/program ledgers
    widget-api/
      service.yaml
      ledger/

    widget-platform/
      domain.yaml
      ledger/
      widget-api/
        service.yaml
        ledger/

    enterprise-suite/
      program.yaml
      ledger/
      widget-platform/
        domain.yaml
        ledger/
        widget-api/
          service.yaml
          ledger/

### Structural Clarification

- **Features never move.** They live permanently under `docs/features/`.
- **The hierarchy floats above them.** Services, domains, and programs reorganize freely because they contain ledgers and references, not feature content.
- A service knows its features by reference, using stable IDs rather than folder moves.
- The hierarchy can grow over time without disrupting feature locations.
- The landscape should be organized top-down as `program/domain/service`, `domain/service`, or just `service`.
- If a service later gets a domain, the landscape directories should be reorganized to reflect that new parent-child structure; the machine-oriented map makes that safe.

This resolved the central path problem from the earlier feature-first idea. The system can still grow upward organically, but growth no longer requires moving the feature artifacts themselves.

### Feature Archive vs. Landscape

| Tree | Contents | Moves | Audience |
|---|---|---|---|
| `docs/features/` | Feature scratchpads, WIP, closed feature artifacts | Never | Contributors |
| `docs/<landscape>/` | Ledgers, accumulated knowledge, journey docs | Yes | Humans across roles |
| Governance map | ID-to-path index, ownership graph, signal state | Derived only | Agents / tooling |

An important distinction emerged here:

- The **Feature Archive** is the archaeological record -- what was known, debated, and produced during a feature's life.
- The **Landscape** is the living present -- the current service, domain, and program truth that downstream humans and agents should read first.

This avoids conflating feature-time knowledge with current-state knowledge.

### Governance Map Design

The governance map is **derived, not authoritative**.

- Humans should not depend on reading it directly.
- It can live in the governance repo or a database.
- It exists as a machine-readable projection of the control-repo frontmatter.
- It must never be hand-edited.
- If it drifts, it should be rebuilt from source files.

Another important principle from the discussion: the map is a **projection**, not the truth itself. The files are the durable source; the map is a cached, machine-optimized view built from them. This keeps the design resilient even if the governance repo or backing database needs to be rebuilt from scratch.

### Minimum Reconstructible Feature Metadata

featureId: widget-1.1
kind: feature
status: active
belongs_to:
  service: widget-api
  domain: null
  program: null
docs_path: docs/features/widget-1.1

### Minimum Reconstructible Service / Domain / Program Metadata

id: widget-api
kind: service
belongs_to:
  domain: widget-platform
  program: enterprise-suite
features:
  - widget-1.0
  - widget-1.1
ledger_path: docs/enterprise-suite/widget-platform/widget-api/ledger

If the service exists by itself, its ledger may temporarily live at `docs/widget-api/ledger`. Once a domain or program is introduced, the landscape directories are reorganized and the projection map is rebuilt.

### Map Rebuild Behavior

1. Scan frontmatter from features and ledgers
2. Reconstruct the ID-to-path index and ownership graph
3. Cross-validate parent/child declarations
4. Report orphans and inconsistencies
5. Rebuild the governance projection

This implies bidirectional consistency checks even if humans mostly think in one direction. A feature can declare its parent service, and a service can declare its owned features; the map rebuild process becomes the place where those declarations are validated against each other.

This also implies a useful `/lens-doctor` capability to audit orphaned features, broken parent references, empty ledgers, and unpromoted completed features.

### Unified Model Summary

| Component | Description |
|---|---|
| **Feature Archive** | Permanent, flat, never reorganized. Frontmatter is source truth for feature identity and attachment |
| **Landscape** | Reorganizable ledgers for service/domain/program knowledge |
| **Governance map** | Derived index rebuilt from frontmatter; machine-only |
| **Salmon workflow** | Recursive consistency-check workflow triggered by upstream-impact discoveries |

**Core statement:** Features are immutable facts. The landscape is an interpretation. The map is a cache.

---

## Phase 4 -- Solution Matrix

_What does Lens need to change? What is the minimum viable first step? What are the implementation risks?_

### Evaluation Dimensions

The final model was evaluated against the constraints that came out of the session:

| Dimension | Why it matters |
|---|---|
| **Human usability** | Humans must be able to find the current truth without reconstructing it from scattered feature artifacts |
| **Machine tractability** | Agents need a reliable graph/index for loading context, validating consistency, and supporting Salmon |
| **Topology flexibility** | A quick script must be able to grow into a service, domain, or program without destructive restructuring |
| **Operational simplicity** | The design must work in today's operating model, not in an aspirational future model |
| **Recovery / resilience** | Governance data must be rebuildable if the projection store is lost or drifts |
| **Team-scale coordination** | Multiple contributors must be able to work without hidden dependencies and branch-isolated documents |

### Scored Recommendation

| Candidate | Human usability | Machine tractability | Flexibility | Simplicity | Resilience | Overall |
|---|---|---|---|---|---|---|
| **Current branch-scoped feature model** | 1 | 2 | 2 | 2 | 2 | 9 |
| **Governance-only docs model** | 1 | 4 | 3 | 2 | 3 | 13 |
| **Pure graph / no stable human homes** | 2 | 5 | 5 | 2 | 4 | 18 |
| **Two-Tree Model with Derived Map** | 5 | 5 | 5 | 4 | 5 | 24 |

**Conclusion:** The Two-Tree Model with Derived Map is the strongest fit because it solves for both humans and agents simultaneously. It preserves a stable Feature Archive, provides living higher-order knowledge homes, avoids branch isolation, and remains rebuildable from frontmatter.

### What Lens Needs to Change

The brainstorm converged not just on a new structure, but on a concrete set of Lens changes required to support it.

#### 1. Stop treating path as identity

- Today, Lens often assumes path and identity are tightly coupled
- The new model requires stable IDs for features, services, domains, and programs
- Paths become addresses that can change for the landscape layer

#### 2. Introduce first-class higher-order entities

- Add explicit support for `service`, `domain`, and `program` artifacts as peers in the model, not just folder levels
- Each entity needs frontmatter, lifecycle state, parent refs, and a ledger home

#### 3. Introduce a derived map / projection workflow

- Add a rebuild command that scans frontmatter and regenerates the machine-readable topology map
- The governance repo or database becomes a projection target, not the source of truth

#### 4. Add Salmon as a first-class workflow

- A feature-level upstream-impact signal should trigger recursive consistency checks
- The workflow must traverse upward and downward, surfacing both advisories and blocks

#### 5. Add doctor / audit capabilities

- Lens needs a topology audit command to catch drift, orphaning, missing promotions, and broken parent refs

#### 6. Replace planning-branch assumptions

- Planning docs should no longer depend on branch isolation for validity
- Draft vs. published state should become explicit metadata rather than implicit branch location

### Minimum Viable First Step

The right first implementation is **not** a full migration. The smallest viable move is to introduce the mechanics that make the final model possible without forcing immediate structural change.

**MVP recommendation:**

1. **Add stable IDs + parent refs to frontmatter**
   - Ensure feature artifacts can declare `belongs_to` independently of folder placement
2. **Create a rebuildable map command**
   - Build a simple projection from frontmatter into governance metadata
3. **Introduce `docs/features/` as the permanent feature home for new work**
   - Do not migrate everything at once; start with new features
4. **Introduce one pilot ledger**
   - Pick a single service or domain and create a living ledger above its features
5. **Add a lightweight `lens-doctor`**
   - Start with orphan checks and parent/child consistency validation

This MVP proves the model without demanding an all-at-once reorganization.

### Recommended Implementation Sequence

| Sequence | Change | Outcome |
|---|---|---|
| **Step 1** | Extend frontmatter schema with stable IDs and `belongs_to` | Decouples identity from path |
| **Step 2** | Build projection/rebuild command | Makes the governance map derived and recoverable |
| **Step 3** | Introduce `docs/features/` for net-new features | Establishes permanent feature archive pattern |
| **Step 4** | Pilot one service ledger in the landscape | Validates living current-state knowledge model |
| **Step 5** | Add `lens-doctor` consistency checks | Catches drift and establishes trust in the structure |
| **Step 6** | Add Salmon workflow + recursive validation | Enables safe upstream propagation |
| **Step 7** | Expand to domain/program ledgers where warranted | Supports larger organic products |

### Biggest Risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| **Dual truth drift** | Feature archive and living ledger can diverge if promotion discipline is weak | Make promotion explicit, auditable, and eventually agent-assisted |
| **Projection drift** | Governance map can become stale or incorrect | Rebuild from frontmatter; never hand-edit |
| **Over-modeling too early** | Teams may create unnecessary service/domain/program layers | Keep depth optional; require a real need before adding layers |
| **Salmon overload** | Too many upstream signals can create noise | Default to advisory; escalate only when recursive checks detect material impact |
| **Migration fatigue** | Retrofitting all historical work would be too disruptive | Start with new work and pilot areas; backfill selectively |

### Strategic Recommendation

The strongest strategic conclusion from the session is:

**Do not try to perfect the mature operating model first. Build the topology that matches how work actually evolves now, and leave room for more formal controls later.**

That means:

- remove planning-branch dependence now
- introduce stable IDs and derived projections now
- separate feature archive from living landscape now
- pilot ledgers and Salmon workflows incrementally
- defer richer formal review gates until there is a real operating model that can sustain them

### Phase 4 Outcome

The brainstorming session produced not just a conceptual model, but an actionable direction:

- **Target architecture:** Two-Tree Model with Derived Map
- **Primary operating principle:** Features are immutable facts; the landscape is a living interpretation
- **Machine principle:** the map is a rebuildable projection, never hand-authored truth
- **Workflow principle:** upstream change is handled through Salmon and recursive validation
- **Implementation strategy:** evolutionary rollout via frontmatter, projection rebuild, pilot ledgers, and audit tooling

This is strong enough to move from brainstorming into architecture/design work.

---

# Architecture Document Preview

# Auspex Architecture — LENS Topology Redesign

## 1. Executive Summary

This document formalizes the architecture proposed during the Auspex brainstorming session for restructuring how LENS/BMAD stores, navigates, and evolves project knowledge.

The current `domain > service > feature` model works adequately for one-shot work, but it breaks down for organic, team-scale projects where features accumulate into services, services collaborate into domains, and domains may themselves participate in a larger program or product. The failure is not only structural; it is cognitive. Machines can search scattered documents. Humans need stable homes for truth.

The proposed solution is a Two-Tree Model with Derived Map:

- a Feature Archive that is permanent, flat, and never reorganized
- a Landscape of service/domain/program ledgers that can be reorganized as the product topology evolves
- a Derived Governance Map that is rebuilt from frontmatter and used by agents/tooling, but is never hand-authored truth
- a Salmon Workflow that handles upstream-impact discoveries through recursive validation across the topology

This architecture is designed to support both present-day operating reality and future maturation without forcing a rigid process too early.

## 2. Problem Statement

The current artifact topology creates two distinct failure modes.

### 2.1 Failure Mode A — Knowledge Consolidation

The accumulated design truth of a service or domain is spread across multiple feature folders and branches. This means:

- there is no single human-readable place to learn what a service currently is
- downstream work must reconstruct service truth from historical feature artifacts
- higher-order views like user journeys or program flows become fragmented

### 2.2 Failure Mode B — Cross-feature Dependency at Authoring Time

A new feature often needs design context from sibling or predecessor features. Under the current model, that context is often:

- stored in another feature folder
- trapped in another branch
- incomplete, duplicated, or stale

This forces contributors to rely on memory, tribal knowledge, or manual hunting.

## 3. Architecture Principles

| Principle | Meaning |
|---|---|
| P1 — Human-first consolidation | A human must have a stable place to read the current truth at each meaningful layer |
| P2 — Machine-derived projection | Tooling may maintain indexes and graphs, but those are projections, not source truth |
| P3 — Stable identity over mutable location | IDs are stable; paths are addresses that may change for landscape artifacts |
| P4 — Promotable topology | A standalone script or feature can grow into a service, domain, or program without destructive redesign |
| P5 — Features are contributors, not durable truth owners | Feature artifacts record work and local decisions, but higher-order truth lives above them |
| P6 — Upstream impact is first-class | Reality discovered at the feature layer must be able to influence service/domain/program layers |
| P7 — Present operating model over aspirational purity | The architecture must work now, without depending on heavyweight PR-gated planning workflows |

## 4. Why the Current Branch Model Fails

Historically, the planning branch tried to solve for a more mature approval-oriented design process. In theory, that offers cleaner review boundaries. In practice, it imposes cost without delivering proportional value:

- planning branches create document pocket universes
- feature-to-feature visibility is reduced
- the team is not actually using PRs as the authoritative requirements gate
- planning validity becomes tied to git topology instead of document state

The conclusion from the brainstorming session is explicit:

> Planning artifacts should no longer depend on a planning branch for legitimacy.

Instead, planning artifacts should live in stable locations and use explicit metadata such as `draft` or `published` status.

## 5. Core Architecture — The Two-Tree Model

The architecture separates immutable feature history from reorganizable higher-order knowledge.

### 5.1 Tree One — Feature Archive

`docs/features/` is the permanent home of all features.

Characteristics:

- flat or shallow organizational model
- features never move once created
- each feature keeps its own scratchpad, WIP notes, and closed artifacts
- feature frontmatter is the source truth for feature identity and attachment

Example:

docs/
  features/
    auspex/
    widget-1.0/
    widget-1.1/
    widget-ui/

### 5.2 Tree Two — Landscape

The landscape contains the living higher-order knowledge homes.

Characteristics:

- reorganizable over time
- contains service/domain/program ledgers, not feature content
- supports additive depth: a service can later gain a parent domain; a domain can later join a program
- is where humans should go first for current truth
- is organized top-down as `program/domain/service`, `domain/service`, or just `service`, depending on what layers currently exist

Example:

docs/
  widget-api/
    service.yaml
    ledger/

  widget-platform/
    domain.yaml
    ledger/
    widget-api/
      service.yaml
      ledger/

  enterprise-suite/
    program.yaml
    ledger/
    widget-platform/
      domain.yaml
      ledger/
      widget-api/
        service.yaml
        ledger/

If a service later gets a domain, or a domain later gets a program, the landscape directories should be reorganized to reflect that parent-child relationship. That reorganization is safe because the machine-readable map tracks stable IDs separately from current paths.

### 5.3 Separation of Concern

| Area | Purpose | Audience |
|---|---|---|
| Feature Archive | Archaeological record of work, decisions, and artifacts produced during a feature's life | Contributors |
| Landscape | Living present-state truth for service, domain, and program interpretation | Humans across roles |
| Derived Map | Machine-readable index, ownership graph, signal state | Agents / tooling |

This avoids conflating feature-time knowledge with current-state knowledge.

## 6. Entity Model

The architecture recognizes four entity kinds.

| Kind | Role | Durability |
|---|---|---|
| Feature | Unit of work and local artifact production | Permanent archive |
| Service | Accumulated technical truth across related features | Living ledger |
| Domain | Cohesive cross-service capability and user journey layer | Living ledger |
| Program / Product | Cross-domain assembly into a finished product | Living ledger |

The important nuance is that these are not mandatory levels. They are additive, introduced when the work demands them.

## 7. Identity and Addressing

The redesign requires a strict separation between identity and path.

- `featureId`, `serviceId`, `domainId`, and `programId` are stable identities
- `docs_path` and `ledger_path` are mutable addresses
- the Feature Archive uses effectively permanent paths
- the Landscape may reorganize over time as parent-child relationships evolve

This enables growth without breaking references.

## 8. Source of Truth and Derived Map

The machine-readable map is not authoritative.

### 8.1 Source of Truth

Source truth lives in the control-repo files themselves, primarily in frontmatter / YAML metadata:

- `feature.yaml`
- `service.yaml`
- `domain.yaml`
- `program.yaml`

### 8.2 Derived Projection

The governance repo or a database may hold a machine-readable topology map, but that map is:

- rebuilt from source files
- never hand-edited
- a performance/query optimization only
- recoverable if lost or corrupted

This architecture intentionally treats the map as a projection.

### 8.3 Minimum Feature Metadata

featureId: widget-1.1
kind: feature
status: active
belongs_to:
  service: widget-api
  domain: null
  program: null
docs_path: docs/features/widget-1.1

### 8.4 Minimum Service / Domain / Program Metadata

id: widget-api
kind: service
belongs_to:
  domain: widget-platform
  program: enterprise-suite
features:
  - widget-1.0
  - widget-1.1
ledger_path: docs/enterprise-suite/widget-platform/widget-api/ledger

When a service exists without a domain or program, that same ledger can temporarily live at `docs/widget-api/ledger`. The service ID remains stable; only the landscape path changes.

### 8.5 Projection Rebuild Behavior

1. Scan feature and landscape metadata
2. Reconstruct the ID-to-path index
3. Reconstruct the parent-child ownership graph
4. Cross-validate declarations in both directions
5. Report orphans, broken links, and inconsistencies
6. Rebuild the governance projection target

This also enables a future `/lens-doctor` command for topology audit and repair guidance.

## 9. Salmon Workflow

The brainstorming session introduced a new first-class workflow: Salmon.

### 9.1 Purpose

Salmon exists because organic work does not only flow downward. Sometimes feature implementation discovers a reality that should force reconsideration at the service, domain, or program level.

### 9.2 Behavior

- A feature can raise an upstream-impact signal
- That signal is non-blocking by default
- Raising the signal triggers a recursive consistency check
- The check traverses both upward and downward
- If the check finds material inconsistency or breakage, the result may block progression

This means the block comes from discovered impact, not from the mere act of signaling.

### 9.3 Traversal Expectations

If a feature raises a Salmon signal:

- upward traversal asks whether the parent service, domain, or program assumptions are still valid
- downward traversal asks whether sibling features or dependent landscape ledgers are now inconsistent

Salmon is therefore a consistency-maintenance workflow, not just an alert channel.

## 10. Lens Capability Changes Required

To support this architecture, Lens must evolve in the following ways.

### 10.1 Stable IDs and Parent References

Lens must stop treating path as identity and begin treating IDs as the canonical linkage mechanism.

### 10.2 First-class Higher-order Entities

Lens must support `service`, `domain`, and `program` artifacts as entities with their own metadata, lifecycle, and ledger homes.

### 10.3 Derived Map Rebuild

Lens must add a command to rebuild the topology projection from source files.

### 10.4 Doctor / Audit

Lens should add a topology audit command capable of identifying:

- orphaned features
- mismatched parent-child refs
- empty or disconnected ledgers
- completed features that have not been promoted into the living landscape

### 10.5 Salmon Workflow Support

Lens must support upstream-impact signaling and recursive consistency traversal.

### 10.6 Replace Planning-Branch Assumptions

Planning artifact validity should be based on explicit document metadata rather than branch placement.

## 11. Recommended Rollout Strategy

This architecture should be introduced incrementally.

### 11.1 Minimum Viable First Step

1. Extend frontmatter/YAML schema with stable IDs and `belongs_to`
2. Build a projection/rebuild command
3. Introduce `docs/features/` for all new work
4. Pilot one living ledger at service or domain level
5. Add a lightweight `lens-doctor`

### 11.2 Suggested Sequence

| Step | Change | Outcome |
|---|---|---|
| 1 | Extend metadata schema | Decouple identity from path |
| 2 | Build projection/rebuild command | Make the map derived and recoverable |
| 3 | Start using `docs/features/` for new work | Establish permanent feature archive pattern |
| 4 | Pilot one landscape ledger | Validate living current-state knowledge |
| 5 | Add `lens-doctor` | Build trust through auditability |
| 6 | Add Salmon workflow | Enable safe upstream propagation |
| 7 | Expand to domain/program ledgers as needed | Support larger organic systems |

## 12. Risks and Mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| Dual truth drift | Feature archive and living landscape can diverge | Make promotion explicit, visible, and eventually agent-assisted |
| Projection drift | Derived map can become stale | Rebuild from source; never hand-edit |
| Over-modeling | Teams may create structure too early | Keep depth optional; add layers only when justified |
| Salmon overload | Too many upstream signals can create noise | Default to advisory; escalate only when recursive checks find material impact |
| Migration fatigue | Retroactive full migration would be disruptive | Start with new work and pilot areas |

## 13. Strategic Recommendation

The strongest conclusion from the brainstorming session is this:

> Do not perfect the mature operating model first. Build the topology that matches how work actually evolves now, and leave room for more formal controls later.

That means implementing the enabling structure first:

- stable IDs
- derived projections
- permanent feature archive
- living landscape ledgers
- Salmon + audit tooling

Formal review gates and heavier process can be layered on later if and when the operating model genuinely requires them.

## 14. Decision Summary

| Area | Decision |
|---|---|
| Primary topology | Two-Tree Model with Derived Map |
| Feature location | Permanent under `docs/features/` |
| Higher-order knowledge | Reorganizable landscape ledgers |
| Machine-readable topology | Derived projection, never hand-authored source truth |
| Upstream change handling | Salmon workflow with recursive validation |
| Adoption strategy | Evolutionary rollout, not big-bang migration |

## 15. Next Design Step

This document is strong enough to move into a more detailed implementation design. The next logical artifact should define:

- concrete file schemas for feature/service/domain/program metadata
- ledger structure and minimum required sections
- command design for projection rebuild, doctor, and Salmon
- migration strategy for net-new work versus legacy content

---

# Auspex Product Feature Specification — MVP1 Reporting UI

## Executive Summary

Auspex is the first product feature under `specdriven/adeptus`. It provides a thin, stakeholder-facing reporting UI that makes project delivery artifacts and status visible without requiring direct GitHub access. MVP1 focuses on reliable, automated, read-only reporting so Product Owners, Scrum Masters, leadership, and developers can quickly assess project health.

## Problem Statement

Project delivery evidence exists, but is fragmented across repository paths and tooling that assumes developer access. Non-developer stakeholders cannot self-serve status effectively and depend on manual report assembly or developer mediation.

Key pain points:

- Artifact discovery is slow and path-dependent.
- Reporting is manual and inconsistent.
- Consumers require repository permissions to view source artifacts.
- Team-level visibility exists, but enterprise rollup is not standardized.

## Users and Personas

- Primary: Product Owners, Scrum Masters, leadership stakeholders.
- Secondary: Developers performing quick status checks.
- Operations/Security Stakeholders: Need compliance-aligned access and auditability.

## Product Goals

1. Provide a read-only UI for project status and artifacts sourced from `/Docs` and `/TargetProjects`.
2. Remove direct GitHub access requirements for reporting consumers.
3. Automate refresh/publication of reporting views.
4. Preserve team-pod autonomy while enabling future enterprise federation.

## Non-Goals (MVP1)

- Artifact authoring/edit workflows.
- Replacing `lens.core` lifecycle orchestration.
- Broad conversational agent authoring capabilities.
- Full enterprise cross-pod federation implementation.

## Scope (MVP1)

### In Scope

- Team-pod level dashboard with project/domain/service/feature status views.
- Artifact browse/read views for core delivery docs: PRD, architecture, epics, stories, sprint status.
- Automated refresh pipeline for reporting data.
- Access abstraction so end users do not need GitHub repo access.
- EPLX Kubernetes deployment baseline.

### Out of Scope

- Write-back operations to governance artifacts.
- Manual script-run-only operation model.
- Cross-authority governance mutations.

## Functional Requirements

1. Project Rollup View
   - Show project-level summary counts: active features, phase distribution, risks/open blockers.

2. Feature Lifecycle View
   - Show feature status, phase, owner, and key timestamps from governance artifacts.

3. Artifact Reader
   - Render key markdown artifacts in-app with source traceability.

4. Search and Filter
   - Filter by domain, service, feature, phase, owner, status.

5. Automated Data Refresh
   - Refresh reporting data on an automated schedule or trigger (TBD) with visible freshness timestamp.

6. Access Abstraction
   - Consumers authenticate to Auspex; they do not require direct repository permissions.

7. Source Failure/Staleness Visibility
   - Clear UI indication when an artifact source fails to load or when data exceeds freshness thresholds.

## Non-Functional Requirements

- Security: Least privilege, read-only by default, auditable access and refresh operations.
- Auth: Enterprise-approved authN/authZ controls; no uncontrolled secret sprawl.
- Availability: Reporting surfaces remain available for stakeholder read paths during normal operations.
- Performance: Common status views should load quickly for day-to-day operational checks.
- Deployability: Configuration-driven deployment so teams can clone and run their own pod.
- Rollup readiness: Pod output contracts must be stable and compatible with future rollup.
- Data Freshness (MVP1): Reporting data must be refreshed within 24 hours.
- Authorization Role: Viewer-only role is sufficient for MVP1 as a read-only reporting surface.

## Deployment Assumptions

- Initial target: small EPLX-hosted Kubernetes deployment.
- Team-pod model in MVP1.
- Source of truth remains repository artifacts; no authoring datastore introduced by Auspex.
- Pod-of-Pods rollup is additive and must not break local pod operation.

## Success Metrics

### Business Outcomes

- Stakeholders can self-serve status/artifacts without developer intervention.
- Status report preparation effort is measurably reduced.
- Consumers access reporting views without direct GitHub permissions.

### Adoption Metrics

- Pod deployment reproducibility across multiple teams.
- 24-hour SLA for reporting data is met consistently.
- Stakeholder adoption for weekly planning/review use cases.