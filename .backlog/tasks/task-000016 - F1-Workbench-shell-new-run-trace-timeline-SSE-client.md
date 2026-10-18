---
id: TASK-000016
title: 'F1 Workbench shell: new run, trace timeline, SSE client'
status: To Do
assignee: []
created_date: '2026-10-18 12:21'
labels:
  - phase-1
  - frontend
  - 'lane:f1'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 16000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Users start runs and watch the pipeline live. This lane also owns the workspace domain client and the event reducer that every feature reads from.

Spec: PLAN.md sections 4.4, 4.6, 5.2, card "F1 workbench-shell" in section 7.4.
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/f1-shell
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New-run form supports question, AUTO/MEDICAL/GENERAL mode, seed upload (PDF, PMID, DOI, URL), and auto-continue
- [ ] #2 Live trace timeline and status header show stage progress; clone button creates a re-run
- [ ] #3 Reducer ignores duplicate event IDs and handles out-of-order IDs (tests)
- [ ] #4 SSE hook reconnects and sends the last event ID (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; `pnpm check` and `pnpm build` pass; `pnpm test` passes when tests exist
- [ ] #3 Feature renders both fixtures (medical and general) without console errors
<!-- DOD:END -->
