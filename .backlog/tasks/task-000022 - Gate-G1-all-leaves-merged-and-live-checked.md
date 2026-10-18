---
id: TASK-000022
title: 'Gate G1: all leaves merged and live-checked'
status: To Do
assignee: []
created_date: '2026-10-18 12:21'
labels:
  - phase-1
  - gate
milestone: m-1
dependencies:
  - TASK-000009
  - TASK-000010
  - TASK-000011
  - TASK-000012
  - TASK-000013
  - TASK-000014
  - TASK-000015
  - TASK-000016
  - TASK-000017
  - TASK-000018
  - TASK-000019
  - TASK-000020
  - TASK-000021
documentation:
  - PLAN.md
priority: high
type: task
ordinal: 22000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stage lanes tune prompts against real adapters, so every adapter must work live first.

Spec: PLAN.md section 7.4 "Gate G1".
Depends on: A1-A7, F1-F6.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `uv run pytest -m live` passes with real keys
- [ ] #2 Offline e2e test still passes on main
- [ ] #3 Every feature renders both fixtures without console errors
<!-- AC:END -->
