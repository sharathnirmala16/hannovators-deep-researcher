---
id: TASK-000032
title: F7 Frontend live wiring against the fake-mode backend
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
labels:
  - phase-2
  - frontend
  - 'lane:f7'
milestone: m-2
dependencies:
  - TASK-000015
  - TASK-000016
  - TASK-000017
  - TASK-000018
  - TASK-000019
  - TASK-000020
  - TASK-000021
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 32000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Features were built on fixtures; they must now work with the real API, live SSE, and partial run states.

Spec: PLAN.md sections 4.6, 5.2, card "F7 live wiring" in section 7.5.
Parallel with: S1-S9.
Worktree: lane/f7-live
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 With the backend in PROVIDER_MODE=fake, a run can be created, reviewed, continued, and watched to completion in the UI
- [ ] #2 Running, awaiting-review, and failed states render correctly in every feature
- [ ] #3 Fixture mode still works
- [ ] #4 Reducer handles STAGE_FAILED followed by a reconnect (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; `pnpm check` and `pnpm build` pass; `pnpm test` passes when tests exist
- [ ] #3 Feature renders both fixtures (medical and general) without console errors
<!-- DOD:END -->
