You are working in `crisweber2600/NextLens` on PR 11.

Goal:
Bring PR 11 closer to the TopDown gold standard by fixing the candidate selection gate so it exposes the full ranked Candidate Feature inventory, not only the top 3.

Context:
PR 11 currently improves the previous gating issue by deriving governed `top_down_context` from `extracted_concepts` when raw discovery input is supplied, then continuing through sufficiency and ranking. Keep that improvement. Do not undo the PR 8 / PR 11 safeguards:
- Raw prose must not emit a Feature packet directly.
- `top_down_context` / curated top-down context must still gate packet emission.
- Candidate Features must still be ranked before selection.
- A selected Feature must still require explicit operator confirmation before packet emission.
- Doctor must remain non-mutating.

Observed remaining bug:
The candidate selection experience still behaves as if only the top 3 candidates matter. In the NorthStar run, the user supplied a large discovery surface: website HTML/JS plus `rawNotes.md` and `brainstorming-session-2026-02-26.md`. The materials contain many possible candidate Feature areas across Joey/student experience, assessment architecture, HFW, writing vocabulary, spelling inventory, teacher dashboard, micro-credentialing, systems coach, workshop model, units, gaming/rewards, reporting, RtI, and more. But the runtime surfaced only three choices in the candidate menu, and reranking again produced only a “New top 3.”

Gold-standard expectation:
The TopDown hierarchy includes:

System
→ Discovery Epoch
→ Source Context
→ Extracted Concepts
→ System Thesis
→ Roles / Stakeholders
→ Outcomes
→ Operating Loops
→ Journeys
→ Candidate Features
→ Selected Feature
→ Feature Packet
→ BMAD Artifacts
→ Stories
→ Implementation Evidence
→ Validation Result
→ Salmon Signals
→ Landscape Update

The important boundary here is:

Candidate Features → Selected Feature

That means the operator must be shown the full ranked list of Candidate Features before selecting one Feature. Ranking should inform selection; ranking must not hide the rest of the design space.

Primary implementation target:
Update the candidate selection renderer and selection flow so all ranked candidates are exposed and selectable.

Likely runtime area:
- `.agents/skills/bmad-nextlens/scripts/candidate_selection.py`
- Tests under `.agents/skills/bmad-nextlens/scripts/tests/`
- Any orchestrator or command-surface code that renders or stores the candidate selection output

Current suspected issue:
`candidate_selection.py` has a top-three display cap such as `MAX_CANDIDATE_SELECTION_RANK = 3`, and rendering/alternative selection logic uses that cap. Remove or refactor that cap so it does not limit the operator-visible candidate inventory or the selectable rank range.

Required behavior:
1. When more than three candidates are ranked, the candidate gate must render or otherwise expose every ranked candidate.
2. The top recommendation may still be highlighted.
3. The top three may still be labeled as “recommended” or summarized, but the complete ranked list must be available in the same gate output.
4. Every ranked candidate must be selectable by rank number.
5. Every ranked candidate must be selectable by candidate id.
6. Candidate ids outside the top three must remain valid selections.
7. Alternative-choice / decline flow must not restrict the operator to the top three.
8. The rendered candidate menu must include the total ranked candidate count.
9. The ranking trace count and candidate menu count must agree.
10. No Feature packet may be emitted merely because candidates are rendered.
11. Explicit confirmation must still be required before packet emission.

Preferred rendering format:
Render a clear full list like:

[stage:candidate-selection]
ranked_candidate_count: 18
selected_candidate_id: feature.example.top

Recommended candidate:
1. Selected Candidate (Rank 1):
id: ...
name: ...
goal: ...
score: ...
rationale: ...

Full ranked candidate list:
1. ...
2. ...
3. ...
4. ...
...
18. ...

Reply with any rank number from 1-18 or any candidate id to inspect/select another candidate.
Confirm highlighted selection? [y/N]
No Feature packet is emitted from candidate selection.

For each full-list item, include at minimum:
- rank
- candidate id
- name
- score
- short goal or summary
- concise reason/rationale or differentiator when available

Do not overbuild UI. This is deterministic script/runtime behavior, not product UI.

Large-list handling:
If there is an existing concern about very large menus, implement a deterministic full-list mode rather than hiding candidates. Acceptable options:
- render all candidates by default;
- or render all candidates grouped under headings;
- or render a “recommended top 3” section followed by “remaining ranked candidates.”

Do not make pagination the only way to see lower-ranked candidates unless the current command/runtime already supports interactive pagination. The immediate acceptance requirement is that a single candidate gate output can expose the full ranked list.

Tests to add or update:
1. Rendering with 5+ ranked candidates displays all candidates, not just the top 3.
2. Rendering includes `ranked_candidate_count` or equivalent total count.
3. Selecting rank 4 or rank 5 works.
4. Selecting a candidate id outside the top 3 works.
5. Decline → select alternative flow allows choosing any non-selected ranked candidate, including outside top 3.
6. Existing confirmation behavior remains unchanged.
7. Candidate rendering still emits no Feature packet.
8. PR 11 orchestrator tests still pass: raw prose can derive curated top_down_context, reach sufficiency/ranking, and block at confirmation rather than emitting.
9. Add a regression test that would fail under `MAX_CANDIDATE_SELECTION_RANK = 3`.

Acceptance criteria:
- No artificial top-three cap remains in the operator’s candidate choice set.
- A complex discovery context can produce and expose the full ranked Candidate Feature inventory.
- The selected Feature is chosen from the full ranked list, not just from the top 3.
- PR 8 safeguards remain intact.
- PR 11’s derived `top_down_context` path remains intact.
- Existing tests pass.
- New tests prove full-list rendering and full-list selection.

Run focused validation:
```bash
python -m pytest .agents/skills/bmad-nextlens/scripts/tests/test_candidate_selection.py -q
python -m pytest .agents/skills/bmad-nextlens/scripts/tests/test_orchestrator.py -q
python -m pytest .agents/skills/bmad-nextlens/scripts/tests/test_stage_pipeline.py -q
