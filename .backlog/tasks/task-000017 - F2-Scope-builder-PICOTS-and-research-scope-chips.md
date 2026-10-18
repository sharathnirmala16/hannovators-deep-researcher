---
id: TASK-000017
title: 'F2 Scope builder: PICOTS and research scope chips'
status: To Do
assignee: []
created_date: '2026-10-18 12:21'
labels:
  - phase-1
  - frontend
  - 'lane:f2'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: medium
type: feature
ordinal: 17000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The decomposition checkpoint lets the user correct PICOTS (medical) or scope (general) before retrieval, which Quicker shows matters most for the comparison concept.

Spec: PLAN.md sections 4.4, 5.2, card "F2 scope-builder" in section 7.4.
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/f2-scope
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 MEDICAL shows PICOTS chips with I-C pairs; GENERAL shows entity, claim, metric, horizon, and counter-hypothesis chips
- [ ] #2 Chips can be added, edited, and deleted, then saved via PUT decomposition
- [ ] #3 Continue calls POST run; chips are read-only outside AWAITING_REVIEW
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; `pnpm check` and `pnpm build` pass; `pnpm test` passes when tests exist
- [ ] #3 Feature renders both fixtures (medical and general) without console errors
<!-- DOD:END -->
