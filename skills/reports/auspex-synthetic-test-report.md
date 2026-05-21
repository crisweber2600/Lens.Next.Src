---
title: 'Auspex Synthetic Verification Report'
created: '2026-05-20'
fixture: 'skills/reports/synthetic-project'
status: 'pass'
---

# Auspex Synthetic Verification Report

## Fixture

The fixture at `skills/reports/synthetic-project` contains:

- One orphan feature: `feature:orphan-001` belongs to missing `service:missing-service`.
- One valid service ledger: `service:attendance-api` belongs to `domain:identity`.
- One mismatched parent reference: `service:clever-sso` belongs to missing `domain:student-auth`.
- One completed-but-unpromoted feature: `feature:roster-sync` targets valid `service:attendance-api`.
- One Salmon upstream-impact note: `feature:district-link-impact`.
- All authored fixture entities declare `publication_state: published` so doctor findings focus on intended topology and promotion cases.

## Workflow Exercise

| Workflow | Expected Result | Blocking | Advisory |
| -------- | --------------- | -------- | -------- |
| `ausx-lens-doctor` | Published projection readiness is blocked until parent references are fixed. | Missing `service:missing-service`; missing `domain:student-auth`. | Completed-but-unpromoted features; Salmon upstream signal. |
| `ausx-map-audit` | Projection rebuild is blocked until parent references are fixed. | Missing `service:missing-service`; missing `domain:student-auth`. | `feature:roster-sync` is completed but unpromoted. |
| `ausx-projection-rebuild` | Rebuild refuses to write a published map unless forced because doctor status is blocked. | Carries forward doctor blockers. | Forced draft/preview rebuilds must be labeled derived and unsafe. |
| `ausx-ledger-promotion` | Promotion can plan `feature:roster-sync`; orphan promotion is blocked. | `feature:orphan-001` has no resolvable ledger target. | `feature:roster-sync` can promote to `service:attendance-api`. |
| `ausx-salmon-impact` | Upstream and downstream review requires blocking consistency action. | Domain says district account linking is out of scope; Salmon note says it is required. | Add source breadcrumbs after resolution. |
| `ausx-topology-design` | Decision report should propose fixing `service:clever-sso` parentage or creating `domain:student-auth`. | Current topology has an unresolved service parent. | Document whether student auth is a domain or service boundary. |
| `ausx-reporting-snapshot` | Snapshot is read-only and overall status is `RED`. | Carries forward map and Salmon blockers. | Shows unpromoted roster-sync as advisory, not blocking. |

## Result

The workflow contracts distinguish advisory findings from blocking inconsistencies and preserve the read-only rule for reporting snapshots. This verification is a static fixture exercise, not a full BMad runtime execution.

