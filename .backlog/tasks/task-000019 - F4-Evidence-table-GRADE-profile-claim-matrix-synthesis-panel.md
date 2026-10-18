---
id: TASK-000019
title: 'F4 Evidence table: GRADE profile, claim matrix, synthesis panel'
status: Done
assignee:
  - '@devin'
created_date: '2026-10-18 12:21'
updated_date: '2026-10-18 14:19'
labels:
  - phase-1
  - frontend
  - 'lane:f4'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Numerical extraction is the least reliable step, so every metric cell must link to its highlighted source text for human verification.

Spec: PLAN.md section 4.4, card "F4 evidence-table" in section 7.4.
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/f4-evidence
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 MEDICAL: GRADE profile per outcome with RoB 2 traffic lights per study and certainty badges
- [ ] #2 Clicking a metric cell (e.g. 2/70 vs 8/53) sets the selection store to its claim and highlight
- [ ] #3 GENERAL: claim matrix with verdict, confidence, sources, and contradictions
- [ ] #4 Synthesis panel shows pairwise summaries, analysis, recommendation, and provenance
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [x] #2 Rebased on main; `pnpm check` and `pnpm build` pass; `pnpm test` passes when tests exist
- [ ] #3 Feature renders both fixtures (medical and general) without console errors
<!-- DOD:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Built in PR https://github.com/sharathnirmala16/hannovators-deep-researcher/pull/8; pnpm check/build/test green; manual fixture-mode browser check still pending, so ACs left unchecked.
<!-- SECTION:FINAL_SUMMARY:END -->
