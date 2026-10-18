---
id: TASK-000024
title: 'S2 Stage decompose: domain detection and PICOTS/scope with self-reflection'
status: To Do
assignee: []
created_date: '2026-10-18 12:21'
labels:
  - phase-2
  - backend
  - 'lane:s2'
milestone: m-2
dependencies:
  - TASK-000009
  - TASK-000010
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 24000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Quicker shows that few-shot + self-reflection decomposition beats zero-shot, especially for comparisons. The result drives search, screening, and appraisal.

Spec: PLAN.md sections 1.2, 3, 4.4, card "S2 decompose" in section 7.5.
May start against fakes after Gate G0; merge only after its listed adapter dependencies are Done.
Parallel with: every other Phase 2 task (S1-S9, F7).
Worktree: lane/s2-decompose
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 AUTO mode picks MEDICAL or GENERAL via Jev; on Jev failure a keyword fallback decides (test)
- [ ] #2 Decomposition uses 2-3 few-shot examples per mode and a draft -> critique -> revise loop, with seed abstracts as context
- [ ] #3 Empty comparison list is valid; several I-C pairs survive the round trip (tests)
- [ ] #4 LLM response schemas define fake_example() so fake mode works
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
