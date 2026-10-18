---
id: TASK-000014
title: 'A6 Retrieval: BM25 + dense hybrid with hierarchical fallback'
status: To Do
assignee: []
created_date: '2026-10-18 12:21'
updated_date: '2026-10-18 12:25'
labels:
  - phase-1
  - backend
  - 'lane:a6'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 14000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Appraisal and highlighting need exact matches (doses, gene symbols, table numbers) and semantic matches, following the Quicker abstract -> full text -> rewrite hierarchy.

Spec: PLAN.md section 1.2, card "A6 retrieval" in section 7.4.
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/a6-retrieval
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 BM25 and dense cosine (numpy over float32 BLOBs) combine through ranking.reciprocal_rank_fusion
- [ ] #2 hierarchical_retrieve checks the abstract tier, then the top 5 full-text chunks, then rewrites the query at most once (test)
- [ ] #3 Empty corpus, one-chunk corpus, and abstract-only source are handled (tests)
- [ ] #4 Stored vectors whose model or size differs from the workspace embedding settings raise a typed error (test)
- [ ] #5 Queries are embedded with a retrieval instruction; documents without one
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
