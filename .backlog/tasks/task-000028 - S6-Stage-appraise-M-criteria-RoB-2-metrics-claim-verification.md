---
id: TASK-000028
title: 'S6 Stage appraise: M-criteria, RoB 2, metrics, claim verification'
status: To Do
assignee: []
created_date: '2026-10-18 12:21'
labels:
  - phase-2
  - backend
  - 'lane:s6'
milestone: m-2
dependencies:
  - TASK-000009
  - TASK-000014
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 28000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Strict full-text matching loses indirect evidence; Quicker M=2 rule fixes that. RoB 2 needs explicit signaling questions for missing data and selective reporting.

Spec: PLAN.md sections 1.2, 3, card "S6 appraise" in section 7.5.
May start against fakes after Gate G0; merge only after its listed adapter dependencies are Done.
Parallel with: every other Phase 2 task (S1-S9, F7).
Worktree: lane/s6-appraise
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 MEDICAL: M-criteria score per source; M at threshold -> INDIRECT (test); below -> M_BELOW_THRESHOLD
- [ ] #2 RoB 2 covers all five domains with signaling questions; overall equals the worst domain (test)
- [ ] #3 METRIC claims carry verbatim quotes; a quote not in the retrieved text is UNVERIFIED (test)
- [ ] #4 GENERAL: CLAIM rows with verdict, credibility, conflict-of-interest flag, and contradictions
- [ ] #5 Top K become APPRAISE_PROMOTED; an LLM failure for one source emits WARNING and others continue (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
