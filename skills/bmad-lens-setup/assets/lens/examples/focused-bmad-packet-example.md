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
