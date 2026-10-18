---
id: TASK-000027
title: 'S5 Stage acquire: full text, chunks, embeddings, citation links'
status: To Do
assignee: []
created_date: '2026-10-18 12:21'
labels:
  - phase-2
  - backend
  - 'lane:s5'
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
ordinal: 27000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Appraisal and highlighting need full text where possible and abstracts where not.

Spec: PLAN.md sections 3, 4.1, card "S5 acquire" in section 7.5.
May start against fakes after Gate G0; merge only after its listed adapter dependencies are Done.
Parallel with: every other Phase 2 task (S1-S9, F7).
Worktree: lane/s5-acquire
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 SCREEN_PROMOTED sources get an OA PDF or web snapshot, chunks, and embeddings
- [ ] #2 Download failure -> ACQUIRE_FAILED with a reason (test)
- [ ] #3 An abstract-only source still has an ABSTRACT chunk and a NO_FULL_TEXT note (test)
- [ ] #4 elink adds CITES and RELATED links for promoted PMIDs
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
