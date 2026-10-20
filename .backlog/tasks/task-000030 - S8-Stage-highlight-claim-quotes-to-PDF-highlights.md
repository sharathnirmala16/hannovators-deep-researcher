---
id: TASK-000030
title: 'S8 Stage highlight: claim quotes to PDF highlights'
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
updated_date: '2026-10-20 17:40'
labels:
  - phase-2
  - backend
  - 'lane:s8'
milestone: m-2
dependencies:
  - TASK-000010
  - TASK-000013
  - TASK-000014
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Zero-hallucination grounding: each claim must point to exact text in the source PDF.

Spec: PLAN.md sections 1.2, 3, card "S8 highlight" in section 7.5.
May start against fakes after Gate G0; merge only after its listed adapter dependencies are Done.
Parallel with: every other Phase 2 task (S1-S9, F7).
Worktree: lane/s8-highlight
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Quotes are located with page.search_for after whitespace and hyphenation normalization; a quote split across lines is found (test)
- [ ] #2 Fallback asks Jev to choose among top hybrid chunks; below the confidence floor no highlight is written and the claim is kept (test)
- [ ] #3 One highlighted.pdf per source with colors by claim kind; web sources get highlight rows without rects (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Round 2 delivered this behavior; see TASK-000047..TASK-000050. Unit-test ACs stay open because the round-2 test policy allows only live e2e tests.
<!-- SECTION:NOTES:END -->
