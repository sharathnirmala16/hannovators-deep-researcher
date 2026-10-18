---
id: TASK-000018
title: 'F3 Screening funnel: PRISMA flow, query log, rejection audit'
status: To Do
assignee: []
created_date: '2026-10-18 12:21'
labels:
  - phase-1
  - frontend
  - 'lane:f3'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: medium
type: feature
ordinal: 18000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Judges must see why sources were dropped. The funnel makes the screening auditable in both modes.

Spec: PLAN.md section 4.4, card "F3 screening-funnel" in section 7.4.
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/f3-funnel
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Funnel renders from funnel counts with MEDICAL (PRISMA) and GENERAL labels
- [ ] #2 Query log shows tool, iteration, hit count, and refinement note
- [ ] #3 Rejection audit lists code and explanation and selects the source on click
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; `pnpm check` and `pnpm build` pass; `pnpm test` passes when tests exist
- [ ] #3 Feature renders both fixtures (medical and general) without console errors
<!-- DOD:END -->
