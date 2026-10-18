---
id: TASK-000008
title: 'Gate G0: foundation ready, freeze [P0] files'
status: To Do
assignee: []
created_date: '2026-10-18 12:20'
labels:
  - phase-0
  - gate
milestone: m-0
dependencies:
  - TASK-000006
  - TASK-000007
documentation:
  - PLAN.md
priority: high
type: task
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Parallel lanes are only safe once the contracts are frozen and the offline system runs. This gate is checked by the integrator on main.

Spec: PLAN.md section 7.3 "Gate G0".
Depends on: P0.5, P0.7.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 All AGENTS.md checks pass on main
- [ ] #2 `uv run alembic upgrade head` works on a fresh database
- [ ] #3 Offline e2e test passes
- [ ] #4 All fixtures pass the pytest and Vitest contract checks
- [ ] #5 `pnpm dev` with fixtures shows the shell with placeholder panes
- [ ] #6 Team is told that [P0] files are frozen
<!-- AC:END -->
