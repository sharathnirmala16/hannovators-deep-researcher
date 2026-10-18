---
id: TASK-000039
title: X1 Vision extraction of table metrics (Nemotron VL)
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
labels:
  - phase-4
  - backend
  - stretch
  - 'lane:x1'
milestone: m-4
dependencies:
  - TASK-000028
documentation:
  - PLAN.md
priority: low
type: enhancement
ordinal: 39000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Numerical extraction from tables is the weakest step in Quicker; the VL model can read the rendered page.

Spec: PLAN.md section 1.2, card "X1 VL tables" in section 7.7.
Stretch: independent of other stretch tasks. Do not merge during a demo freeze.
Worktree: lane/x1-vl
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Table pages are detected and sent as PNG to the EXTRACT_VISION role
- [ ] #2 VL metrics are cross-checked against text quotes; disagreements are flagged, not silently merged (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
