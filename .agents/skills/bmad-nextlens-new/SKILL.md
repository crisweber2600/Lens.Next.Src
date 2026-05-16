---
name: bmad-nextlens-new
description: Breaks top-down or Bottom-Up LENS discovery context into candidate feature slices before creating one NextLens Feature packet. Use when the user asks to create or emit a NextLens feature packet.
---

# Create Feature Packet

## Purpose

Break supplied discovery context into candidate Feature slices, let the operator choose one for deeper exploration, then create one deterministic Feature packet only after the candidate-selection and final-confirmation gates pass.

## On Activation

- Treat this skill as the `new` capability of the NextLens module.
- If `{project-root}/_bmad/config.yaml` does not contain an `nxl` section, run `bmad-nextlens-setup` before continuing.
- Normalize arguments with `../bmad-nextlens/scripts/command_surface.py` using action `new`.
- Require `context_source`; optionally accept `docs_path` to override the configured docs root.
- Use the shared implementation under `../bmad-nextlens/scripts/` for context loading, candidate selection, packet composition, confirmation, and emission.
- When the supplied source is raw Bottom-Up prose, notes, or other uncurated discovery material, use the shared extracted-concepts stage first and preserve the provenance chain into the authoritative curated `top_down_context` artifact. Do not synthesize curated context with an ad hoc script or manual inline object construction.
- The `new` flow is discovery intake, candidate selection, packet composition, emission, and non-mutating validation only. Runtime implementation repair belongs to `/lens-nextlens-bugfix`; health-only validation belongs to `bmad-nextlens-doctor`; upstream correction routing belongs to Salmon.

## Candidate Breakdown Gate

This gate is mandatory and happens before any Feature packet is composed or emitted.

- Ingest the full `context_source` material. Structured `top_down_context` input may already contain `candidateFeatures`; rich prose, raw notes, or Bottom-Up LENS descriptions must be analyzed into candidate Feature slices first.
- For raw prose or Bottom-Up discovery, first produce or load the shared extracted-concepts artifact, then derive the authoritative curated `top_down_context` with clear provenance before packet composition. Raw prose or extracted concepts alone must not be emitted directly as a Feature packet.
- For Bottom-Up LENS or freeform descriptions, identify distinct candidate slices from the supplied goals, workflows, users, lifecycle stages, implementation surfaces, risks, and explicit seams in the material. Do not collapse a rich description into one broad packet such as "Enable Bottom-Up Feature Execution" unless the source truly contains only one bounded slice.
- Present the candidate breakdown with `../bmad-nextlens/scripts/candidate_selection.py`. The operator-facing output must include a numbered list or numbered selection breakdown, candidate names/goals, and enough rationale to compare the slices.
- The operator must be able to choose a rank or candidate id for deeper exploration before packet composition. Candidate selection alone must not emit a packet.
- If `vscode_askQuestions` or an equivalent runtime question tool is unavailable, render the numbered candidate menu, state that no Feature packet has been emitted, and stop. Do not infer confirmation from silence, defaults, or the highest-ranked candidate.
- Proceed to packet composition only after an explicit operator response confirms the highlighted candidate. Then run the final packet confirmation gate before emission.

## Confirmation and Post-Confirmation Flow

After the operator confirms the final Feature packet:

- Call `../bmad-nextlens/scripts/feature_packet_emitter.py` to write the JSON packet to the configured docs path.
- Run NextLens Doctor validation on the emitted packet to verify the Feature definition meets governance requirements.
- Generate BMAD handoff artifacts for the selected Feature and initialize the evidence bundle with packet, Doctor, and handoff references.
- Display the packet path, Doctor status, and the recommended next step: "Continue the planning flow with `/bmad-nextlens-doctor` for full validation, then delegate Feature development to the normal top-down BMAD planning sequence (PRD → Architecture → Stories → Implementation)."
- Do not stop at the confirmation prompt. Proceed immediately to emission and validation upon operator confirmation.

## Runtime Defect Boundary

- Do not patch `.agents/skills/bmad-nextlens/scripts/**`, `.agents/skills/bmad-nextlens-new/**`, tests, or other runtime source files during a normal `bmad-nextlens-new` run.
- Do not delete emitted artifacts, edit generated context artifacts to hide a defect, rerun the pipeline after source edits, or present a repaired packet as if it were produced by one uninterrupted `new` run.
- If packet composition, schema validation, Doctor validation, or evidence generation exposes a runtime defect, surface the finding and stop or route it through `/lens-nextlens-bugfix`, `bmad-nextlens-doctor`, or Salmon instead of repairing implementation inline.
- Source-mode mismatches and structured-field serialization defects are runtime findings. They must be reported through validation or bug routing, not fixed as side effects of packet generation.

## Action Contract

Required args:

- `context_source`

Optional args:

- `docs_path`

Output:

- One Feature packet JSON artifact in the configured NextLens docs path
- BMAD handoff artifacts scoped to the selected Feature
- Initial evidence bundle references for downstream lifecycle tracking
- Doctor validation report
- Framed next steps for continuing the top-down planning flow

`bmad-nextlens-new` stops at discovery/context → candidate selection → Feature packet → BMAD handoff artifacts → initial evidence. It must not perform post-BMAD validation, Salmon routing, Landscape mutation, inline runtime repair, or Feature → Capability → Domain → System promotion.
