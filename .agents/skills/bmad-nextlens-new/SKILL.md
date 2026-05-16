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

## Candidate Breakdown Gate

This gate is mandatory and happens before any Feature packet is composed or emitted.

- Ingest the full `context_source` material. Structured `top_down_context` input may already contain `candidateFeatures`; rich prose, raw notes, or Bottom-Up LENS descriptions must be analyzed into candidate Feature slices first.
- For Bottom-Up LENS or freeform descriptions, identify distinct candidate slices from the supplied goals, workflows, users, lifecycle stages, implementation surfaces, risks, and explicit seams in the material. Do not collapse a rich description into one broad packet such as "Enable Bottom-Up Feature Execution" unless the source truly contains only one bounded slice.
- Present the candidate breakdown with `../bmad-nextlens/scripts/candidate_selection.py`. The operator-facing output must include a numbered list or numbered selection breakdown, candidate names/goals, and enough rationale to compare the slices.
- The operator must be able to choose a rank or candidate id for deeper exploration before packet composition. Candidate selection alone must not emit a packet.
- If `vscode_askQuestions` or an equivalent runtime question tool is unavailable, render the numbered candidate menu, state that no Feature packet has been emitted, and stop. Do not infer confirmation from silence, defaults, or the highest-ranked candidate.
- Proceed to packet composition only after an explicit operator response confirms the highlighted candidate. Then run the final packet confirmation gate before emission.

## Confirmation and Post-Confirmation Flow

After the operator confirms the final Feature packet:

- Call `../bmad-nextlens/scripts/feature_packet_emitter.py` to write the JSON packet to the configured docs path.
- Run NextLens Doctor validation on the emitted packet to verify the Feature definition meets governance requirements.
- Display the packet path, Doctor status, and the recommended next step: "Continue the planning flow with `/bmad-nextlens-doctor` for full validation, then delegate Feature development to the normal top-down BMAD planning sequence (PRD → Architecture → Stories → Implementation)."
- Do not stop at the confirmation prompt. Proceed immediately to emission and validation upon operator confirmation.

## Action Contract

Required args:

- `context_source`

Optional args:

- `docs_path`

Output:

- One Feature packet JSON artifact in the configured NextLens docs path
- Doctor validation report
- Framed next steps for continuing the top-down planning flow