---
id: TASK-000041
title: X3 Borderline chain-of-thought screening
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
labels:
  - phase-4
  - backend
  - stretch
  - 'lane:x3'
milestone: m-4
dependencies:
  - TASK-000026
documentation:
  - PLAN.md
priority: low
type: enhancement
ordinal: 41000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Quicker shows CoT maximizes screening sensitivity; use it only where Jev votes are one short of T.

Spec: PLAN.md card "X3 borderline CoT" in section 7.7.
Stretch: independent of other stretch tasks. Do not merge during a demo freeze.
Worktree: lane/x3-cot
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Only candidates with votes == T - 1 get an LLM CoT review, which can promote them with a recorded rationale
- [ ] #2 Budget cap on CoT calls per run (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
