---
id: TASK-000021
title: F6 Citation graph (cytoscape)
status: In Progress
assignee:
  - '@devin'
created_date: '2026-10-18 12:21'
updated_date: '2026-10-18 14:11'
labels:
  - phase-1
  - frontend
  - 'lane:f6'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: medium
type: feature
ordinal: 21000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The graph shows how seeds relate to promoted, discounted, and web sources.

Spec: PLAN.md sections 4.4 GraphView, 5.2, card "F6 citation-graph" in section 7.4.
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/f6-graph
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Graph renders GraphView with node color by status and origin
- [ ] #2 Clicking a node selects the source for the PDF viewer
- [ ] #3 An empty graph renders a clear empty state
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; `pnpm check` and `pnpm build` pass; `pnpm test` passes when tests exist
- [ ] #3 Feature renders both fixtures (medical and general) without console errors
<!-- DOD:END -->
