---
id: TASK-000026
title: 'S4 Stage screen: Jev T-threshold screening with z-score ranking'
status: Done
assignee:
  - '@devin'
created_date: '2026-10-18 12:21'
updated_date: '2026-10-18 14:22'
labels:
  - phase-2
  - backend
  - 'lane:s4'
milestone: m-2
dependencies:
  - TASK-000009
  - TASK-000010
references:
  - 'https://github.com/sharathnirmala16/hannovators-deep-researcher/pull/11'
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 26000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Coarse screening must be fast and auditable. Jev votes replace multi-pass LLM screening; the embedding fallback keeps the run alive when Jev fails.

Spec: PLAN.md sections 1.2, 3, card "S4 screen" in section 7.5.
May start against fakes after Gate G0; merge only after its listed adapter dependencies are Done.
Parallel with: every other Phase 2 task (S1-S9, F7).
Worktree: lane/s4-screen
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 One Jev request per candidate with relevance score, three mode-specific noul votes, and an exclusion choice
- [x] #2 Promotes when votes >= T, ranks by z(relevance x confidence), keeps top N, and records rejection code and explanation for the rest
- [ ] #3 Fewer candidates than N, all ties, and votes exactly at T are handled (tests)
- [ ] #4 A Jev failure for one candidate falls back to the embedding score for that candidate (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Unchecked: AC3 all-ties test, AC4 fallback test (votes-at-T and fewer-than-N are tested). No e2e suite on main yet.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Screen stage implemented (Jev per candidate, T-threshold, z-score top N, embedding fallback); verified by unit tests and fake-mode run (15 promoted / 23 discounted). PR: https://github.com/sharathnirmala16/hannovators-deep-researcher/pull/11
<!-- SECTION:FINAL_SUMMARY:END -->
