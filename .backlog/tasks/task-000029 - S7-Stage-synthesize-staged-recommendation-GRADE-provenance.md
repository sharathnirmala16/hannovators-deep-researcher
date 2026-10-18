---
id: TASK-000029
title: 'S7 Stage synthesize: staged recommendation, GRADE, provenance'
status: To Do
assignee: []
created_date: '2026-10-18 12:21'
labels:
  - phase-2
  - backend
  - 'lane:s7'
milestone: m-2
dependencies:
  - TASK-000009
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 29000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Quicker synthesizes in three steps and separates evidence from cost and preference. A provenance canary marks AI output.

Spec: PLAN.md sections 3, 4.4 Synthesis, card "S7 synthesize" in section 7.5.
May start against fakes after Gate G0; merge only after its listed adapter dependencies are Done.
Parallel with: every other Phase 2 task (S1-S9, F7).
Worktree: lane/s7-synthesize
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 synthesis_json holds pairwise summaries with per-outcome GRADE, analysis, recommendation, and provenance canary
- [ ] #2 Zero promoted sources -> insufficient-evidence synthesis, not a failure (test)
- [ ] #3 Every source_ids entry refers to a promoted source (test)
- [ ] #4 GRADE never rises above the study-design start level (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
