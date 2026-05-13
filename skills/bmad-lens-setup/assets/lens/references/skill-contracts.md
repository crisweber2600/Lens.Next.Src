# LENS Skill Contracts

Every LENS skill follows these contracts:

1. Preserve BMAD ownership of formal planning and implementation workflows.
2. Preserve LENS ownership of discovery, topology, slice selection, traceability, validation, correction, and visibility.
3. Mark status, confidence, provenance, and open questions on major entities.
4. Do not promote without repeated evidence pressure and human review.
5. Keep bottom-up slices complete without requiring system or capability context.
6. Keep top-down work gated before PRD creation.
7. Write source truth to archive or landscape, and write generated projections to graph.

## bmad-lens-help

Route the request to the right LENS skill and BMAD skill. Explain whether the request is top-down, bottom-up, bridge, validation, correction, audit, or visibility. Output a next-step recommendation.

## bmad-lens-intake

Capture the incoming request, classify mode, identify current knowns, unknowns, non-goals, and the next LENS skill. Never create a platform from one bottom-up slice.

## bmad-lens-slice-new

Create `slice.yaml` for a thin, useful slice, with `scope.includes`, `scope.excludes`, `acceptance_evidence`, and `risks` inline. `slice.md` may summarize the slice for humans. Do not split source-truth acceptance or risk data into separate YAML files. For bottom-up work, system/outcome/journey/capability are optional and can be omitted.

## bmad-lens-slice-frame

Frame start state, end state, vertical path, artifacts, risks, decisions, acceptance evidence, and explicit exclusions.

## bmad-lens-slice-scope

Tighten includes and excludes. Move adjacent work into exclusions. Preserve acceptance evidence that proves only this slice.

## bmad-lens-detect-adjacency

Detect relationships between slices through shared artifacts, workflow, risks, dependencies, workstreams, roles, or decisions. Default to weak adjacency unless evidence supports stronger classification.

## bmad-lens-detect-repetition

Detect repeated pressure across archive, slices, implementation evidence, risks, and decisions. Produce a pressure report; do not promote automatically.

## bmad-lens-suggest-promotion

Prepare a promotion gate with candidate, promoted_from, evidence, recommendation, automatic: false, and human_review_required: true.

## bmad-lens-discover

Create or update a discovery epoch. Ask focused questions, capture responses, extract concepts, challenge assumptions, record open questions, and recommend BMAD review/research skills.

## bmad-lens-capture

Capture raw material into the Work Archive without treating it as truth. Source references are required.

## bmad-lens-synthesize

Extract candidate entities and relationships from raw material. Mark each extracted concept with status, confidence, source refs, and open questions.

## bmad-lens-context-check

Block premature PRD creation when readiness is low. This is the required LENS gate before `bmad-lens-prepare-bmad`; failing the gate should recommend more discovery, elicitation, review, or research. Write `_bmad-output/lens/gates/context-sufficiency-{n}.md` and `_bmad-output/lens/gates/context-score.yaml`.

## bmad-lens-research-plan

Translate context gaps into focused BMAD domain, market, technical, adversarial review, or advanced elicitation work. Store research plans with evidence expectations.

## bmad-lens-map-system

Create or update system thesis, role map, stakeholder map, principles, non-goals, constraints, assumptions, open questions, and risks. Only promoted or reviewed content belongs in Living Landscape.

## bmad-lens-map-outcomes

Create an outcome matrix by role and stakeholder. Outcomes describe changed reality, not features.

## bmad-lens-map-loops

Map operating loops as repeated evidence/action/decision/state cycles. Keep loop confidence explicit.

## bmad-lens-map-journeys

Map journeys from outcomes across roles, data, decisions, state changes, and success evidence. Produce journey YAML, Markdown, Mermaid map, and open questions.

## bmad-lens-slice-journey

Select vertical slices from a journey and document why-first sequencing rationale.

## bmad-lens-map-capabilities

Derive capability candidates from journeys, slices, repeated pressure, and implementation evidence. Capabilities are not guessed up front.

## bmad-lens-analyze-impact

Generate a slice impact map covering likely files, services, components, contracts, stories, workstreams, artifacts, tests, observability, rollout, data, privacy, policy, and architecture decisions. Include directly impacted workstreams, possibly conflicting workstreams, shared files, shared contracts, and a related workstream gate result.

## bmad-lens-promote-landscape

Promote reviewed concepts or promotion gates into Living Landscape ledgers. Supersede stale records instead of deleting history.

## bmad-lens-map-rebuild

Regenerate Derived Map projections from archive and landscape. Do not hand-edit graph outputs. Use `scripts/lens_artifact_ops.py map-rebuild` when available.

## bmad-lens-prepare-bmad

Prepare a focused BMAD packet for the active slice. Include active slice goal, included scope, explicit exclusions, required capabilities, risks, decisions, and acceptance evidence. Exclude adjacent future slices and speculative architecture. Emit both Markdown and YAML packet forms from the same slice context.

## bmad-lens-sync-bmad

Sync PRD, UX, architecture, epics, stories, reviews, and implementation evidence back into LENS traceability. BMAD artifacts are evidence, not automatically validated truth.

## bmad-lens-guard-story

Check story traceability to an active slice, scope discipline, acceptance evidence, risks, privacy/security/policy boundaries, BMAD packet reference, promoted capability references, and Salmon triggers.

## bmad-lens-validate-slice

Validate implementation evidence against slice goal, scope, exclusions, and acceptance evidence.

## bmad-lens-validate-journey

Validate implemented slices against journey steps, decisions, state changes, data movement, and success evidence.

## bmad-lens-validate-outcome

Validate whether implementation and journey evidence satisfy the intended outcome, not just whether work shipped.

## bmad-lens-salmon

Raise an upstream correction signal when implementation reveals false assumptions or changed reality. Include id, raised_from, severity, discovery, impacted_nodes, recommended_action, BMAD action, propagation report, decision record, and sync status.

## bmad-lens-doctor

Audit topology and write graph warnings and doctor report. Deterministic checks include duplicate IDs, orphan references, missing source refs, stale or needs-review records, missing ledger directories, unresolved promoted references, untraced stories, BMAD sync gaps, relationship anomalies, unresolved decisions, and workstream impact gates.

## bmad-lens-auspex

Publish read-only stakeholder status from the Derived Map. Do not mutate archive or landscape.
