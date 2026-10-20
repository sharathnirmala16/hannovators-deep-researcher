---
id: TASK-000037
title: I4 Design pass
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
updated_date: '2026-10-20 17:39'
labels:
  - phase-3
  - frontend
  - 'lane:i4'
milestone: m-3
dependencies:
  - TASK-000034
documentation:
  - PLAN.md
priority: medium
type: enhancement
ordinal: 37000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The demo needs a distinct, intentional look without behavior changes.

Spec: PLAN.md card "I4 design pass" in section 7.6; skill .agents/skills/frontend-design.
Depends on: I1. Parallel with: I2, I3.
Worktree: lane/i4-design
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Shell and features follow one coherent visual direction from the frontend-design skill
- [ ] #2 No behavior or contract changes; the smoke test (if merged) still passes
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; `pnpm check` and `pnpm build` pass; `pnpm test` passes when tests exist
- [ ] #3 Feature renders both fixtures (medical and general) without console errors
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Round 2 delivered this behavior; see TASK-000047..TASK-000050. Unit-test ACs stay open because the round-2 test policy allows only live e2e tests.
<!-- SECTION:NOTES:END -->
