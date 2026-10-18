---
id: TASK-000025
title: 'S3 Stage search: core queries, iterative refinement, multi-source retrieval'
status: To Do
assignee: []
created_date: '2026-10-18 12:21'
labels:
  - phase-2
  - backend
  - 'lane:s3'
milestone: m-2
dependencies:
  - TASK-000009
  - TASK-000011
  - TASK-000012
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 25000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Quicker iterative search beat human experts on sensitivity by separating LLM core queries from fixed filters and refining on hit counts.

Spec: PLAN.md section 3, card "S3 search" in section 7.5.
May start against fakes after Gate G0; merge only after its listed adapter dependencies are Done.
Parallel with: every other Phase 2 task (S1-S9, F7).
Worktree: lane/s3-search
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Generates 3-5 core queries plus standardized filters per mode and logs each in search_queries
- [ ] #2 Refines when hits are 0 or above 5000, stopping at search_max_rounds with a refinement note (tests)
- [ ] #3 PubMed, web router, and elink run concurrently; one provider down still returns others (test)
- [ ] #4 Duplicates across sources collapse to one RAW source; total capped at RUN_BUDGET_MAX_CANDIDATES (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
