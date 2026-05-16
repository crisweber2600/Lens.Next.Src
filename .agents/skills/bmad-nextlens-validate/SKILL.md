---
name: bmad-nextlens-validate
description: Runs governed post-BMAD validation on implementation evidence for a NextLens Feature packet. Use after BMAD implementation evidence exists; this is not Doctor.
---

# NextLens Validate

## Purpose

Run governed post-BMAD validation against BMAD artifacts, completed stories, and implementation evidence for an emitted Feature packet without redoing packet discovery.

## On Activation

- Treat this skill as the `validate` capability of the NextLens module.
- If `{project-root}/_bmad/config.yaml` does not contain an `nxl` section, run `bmad-nextlens-setup` before continuing.
- Normalize arguments with `../bmad-nextlens/scripts/command_surface.py` using action `validate`.
- Require `packet_source` and `implementation_evidence_source`; optionally accept `bmad_artifacts_source`, `docs_path`, `landscape_update_source`, and `landscape_update_mode`.
- Use the shared post-BMAD validation implementation under `../bmad-nextlens/scripts/post_bmad_validation.py`.
- Do not substitute Doctor for this action: Doctor is non-mutating health validation before implementation evidence; Validate is post-BMAD validation after evidence exists.
- Default `landscape_update_mode` is proposal-only. Apply mode must be explicitly requested before authoritative Living Landscape files are changed.

## Action Contract

Required args:

- `packet_source`
- `implementation_evidence_source`

Optional args:

- `bmad_artifacts_source`
- `docs_path`
- `landscape_update_source`
- `landscape_update_mode`

Output:

- A post-BMAD validation report for the packet and implementation evidence.
- Salmon signals when validation findings require correction routing.
- A default Living Landscape update proposal, or applied Landscape update only when apply mode is explicit.
- Updated evidence bundle refs for BMAD artifacts, implementation evidence, validation result, Salmon signals, Landscape update, and non-authoritative Derived Graph projection.

`bmad-nextlens-validate` owns the lifecycle segment: BMAD artifacts/stories/evidence → validation result → Salmon if needed → Landscape proposal/apply → evidence bundle update. Derived Graph remains non-authoritative in both proposal and apply modes, and validation must not auto-promote Feature work into Capability, Domain, or System hierarchy.
