---
id: TASK-000020
title: 'F5 PDF viewer: highlighted PDF at the selected page'
status: Done
assignee:
  - '@devin'
created_date: '2026-10-18 12:21'
updated_date: '2026-10-18 14:19'
labels:
  - phase-1
  - frontend
  - 'lane:f5'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 20000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Visual grounding is the core trust feature: the selected claim opens the highlighted PDF at the right page.

Spec: PLAN.md section 4.4, card "F5 pdf-viewer" in section 7.4.
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/f5-pdf
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The selected highlight opens highlighted.pdf (or raw.pdf) in an iframe at #page=N
- [ ] #2 A source switcher lists promoted sources
- [ ] #3 Web sources show snapshot text with the quote marked
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
