---
id: TASK-000033
title: 'Gate G2: full pipeline offline and live'
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
labels:
  - phase-2
  - gate
milestone: m-2
dependencies:
  - TASK-000023
  - TASK-000024
  - TASK-000025
  - TASK-000026
  - TASK-000027
  - TASK-000028
  - TASK-000029
  - TASK-000030
  - TASK-000031
  - TASK-000032
documentation:
  - PLAN.md
priority: high
type: task
ordinal: 33000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The pipeline must work end to end in both modes before integration and demo prep.

Spec: PLAN.md section 7.5 "Gate G2".
Depends on: S1-S9, F7.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 PROVIDER_MODE=fake e2e yields a non-empty funnel, claims, highlights, synthesis, and UI components
- [ ] #2 One live MEDICAL and one live GENERAL e2e run complete within the candidate budget (`uv run pytest -m "live and e2e"`)
- [ ] #3 The frontend shows a full fake-mode run live
<!-- AC:END -->
