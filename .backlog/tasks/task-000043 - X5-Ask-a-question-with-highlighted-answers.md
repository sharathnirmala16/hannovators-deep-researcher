---
id: TASK-000043
title: X5 Ask a question with highlighted answers
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
updated_date: '2026-10-20 17:39'
labels:
  - phase-4
  - backend
  - frontend
  - stretch
  - 'lane:x5'
milestone: m-4
dependencies:
  - TASK-000014
  - TASK-000030
  - TASK-000015
documentation:
  - PLAN.md
priority: low
type: feature
ordinal: 43000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Users want to query the evidence after a run and see grounded answers.

Spec: PLAN.md card "X5 ask" in section 7.7.
Stretch: independent of other stretch tasks. Do not merge during a demo freeze.
Worktree: lane/x5-ask
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 POST /workspaces/{id}/ask returns an answer with claim and highlight references
- [ ] #2 A question with no supporting chunks returns an explicit no-evidence answer (test)
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
