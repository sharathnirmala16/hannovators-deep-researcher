---
id: TASK-000023
title: 'S1 Stage ingest: resolve and chunk seed materials'
status: To Do
assignee: []
created_date: '2026-10-18 12:21'
updated_date: '2026-10-20 17:40'
labels:
  - phase-2
  - backend
  - 'lane:s1'
milestone: m-2
dependencies:
  - TASK-000009
  - TASK-000011
  - TASK-000012
  - TASK-000013
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 23000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Seeds anchor decomposition and screening. PDFs, PMIDs, DOIs, and URLs must all become chunked, embedded sources.

Spec: PLAN.md section 3, card "S1 ingest" in section 7.5.
May start against fakes after Gate G0; merge only after its listed adapter dependencies are Done.
Parallel with: every other Phase 2 task (S1-S9, F7).
Worktree: lane/s1-ingest
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 PDF, PMID, DOI, and URL seeds become SEED sources with chunks and embeddings
- [ ] #2 The same PMID seeded twice yields one source (test)
- [ ] #3 A seed URL that fails to fetch emits WARNING and the run continues (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Round 2 delivered this behavior; see TASK-000047..TASK-000050. Unit-test ACs stay open because the round-2 test policy allows only live e2e tests.
<!-- SECTION:NOTES:END -->
