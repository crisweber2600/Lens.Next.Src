# Project Context for AI Agents

## LENS Module Active

This project uses the LENS module for BMAD-native system-scale discovery, slice orchestration, topology management, traceability, validation, and correction.

## Traceability Rule

Every BMAD story must trace to an active LENS slice.

For top-down work, trace at minimum:

system -> role -> outcome -> journey -> slice -> capability -> acceptance evidence

For bottom-up work, trace at minimum:

slice -> artifact -> acceptance evidence

## Scope Rule

Do not expand the active slice into adjacent future work unless a LENS Salmon signal, promotion decision, or BMAD correct-course decision changes the plan.

## Architecture Rule

Architecture decisions must update the relevant LENS capability, domain, service, or decision ledger when those ledgers exist. Do not create capability, domain, or service ledgers without evidence pressure.

## Change Rule

If implementation reveals that an upstream assumption is wrong, raise a LENS Salmon signal before silently changing architecture, scope, or acceptance criteria.

## Source Truth Rule

Archive records history. Landscape records current truth. Graph records generated projections. Do not hand-edit Derived Map files.
