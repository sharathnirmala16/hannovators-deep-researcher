---
id: TASK-000044
title: X6 Q2CRBench-3 screening benchmark
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
labels:
  - phase-4
  - backend
  - stretch
  - 'lane:x6'
milestone: m-4
dependencies:
  - TASK-000026
documentation:
  - PLAN.md
priority: low
type: spike
ordinal: 44000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A measured sensitivity number strengthens the pitch. Q2CRBench data has non-commercial data-use terms.

Spec: PLAN.md card "X6 benchmark" in section 7.7; data in .archive/Quicker/Q2CRBench-3.
Stretch: independent of other stretch tasks. Do not merge during a demo freeze.
Worktree: lane/x6-bench
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A script reports screening sensitivity and precision against the included studies for both guidelines
- [ ] #2 Results and data-use terms are documented
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
