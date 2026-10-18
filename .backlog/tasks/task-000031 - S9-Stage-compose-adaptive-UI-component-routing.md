---
id: TASK-000031
title: 'S9 Stage compose: adaptive UI component routing'
status: In Progress
assignee:
  - '@devin'
created_date: '2026-10-18 12:22'
updated_date: '2026-10-18 14:09'
labels:
  - phase-2
  - backend
  - 'lane:s9'
milestone: m-2
dependencies:
  - TASK-000010
documentation:
  - PLAN.md
priority: medium
type: feature
ordinal: 31000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The UI adapts to the domain and the available data. Jev picks components; a guard keeps the UI correct when Jev is down.

Spec: PLAN.md sections 1.2, 4.3 UiComponentId, card "S9 compose" in section 7.5.
May start against fakes after Gate G0; merge only after its listed adapter dependencies are Done.
Parallel with: every other Phase 2 task (S1-S9, F7).
Worktree: lane/s9-compose
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 One Jev request with a noul per UiComponentId sets ui_components_json
- [ ] #2 scope_builder and screening_funnel are always present; components without data are never mounted (test)
- [ ] #3 Jev down -> guard-only fallback set (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
