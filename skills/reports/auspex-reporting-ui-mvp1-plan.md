---
title: 'Auspex Reporting UI MVP1 Plan'
status: 'planned'
module_code: 'ausx'
created: '2026-05-21'
---

# Auspex Reporting UI MVP1 Plan

## Boundary

This repository now owns the reporting data contract through `ausx-reporting-snapshot` and `assets/reporting-snapshot.schema.json`. A full web UI, authentication layer, refresh scheduler, and deployment target are deferred until an application host is identified.

## MVP1 Experience

- Dashboard summary cards for overall status, blocking findings, advisory findings, completed features, unpromoted knowledge, projection readiness, and Salmon impact.
- Artifact reader for map audits, lens doctor reports, projection outputs, promotion reports, Salmon reports, topology decisions, and snapshots.
- Search and filtering by stable ID, title, entity type, status, publication state, parent, severity, and source path.
- Manual refresh from the latest snapshot JSON, with room for scheduled or CI-driven refresh once a host exists.
- Access model placeholder: repository-read in MVP1 data, enforced by the eventual UI host.

## Data Contract

The UI consumes `snapshot-{date}.json` from `ausx-reporting-snapshot`. The schema must remain backward-compatible once a UI host is built. Source docs remain authored truth; UI state is read-only and time-bound.

## Deferred Implementation

Do not add Kubernetes, EPLX, authentication, or web app files to this module repo without a confirmed host. When the host exists, build against the stable snapshot schema rather than reinterpreting authored ledgers directly in the UI.