---
id: TASK-000035
title: I2 Demo replay bundle
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
labels:
  - phase-3
  - backend
  - 'lane:i2'
milestone: m-3
dependencies:
  - TASK-000034
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 35000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Network or provider failures must not break the live demo.

Spec: PLAN.md card "I2 demo-replay" in section 7.6.
Depends on: I1. Parallel with: I3, I4.
Worktree: lane/i2-replay
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A completed workspace exports to a bundle (database rows + files) and imports into a fresh data directory
- [ ] #2 DEMO_REPLAY=<bundle> replays trace events over SSE with the original timing, fully offline
- [ ] #3 Import of a bundle with an unsafe path is rejected (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
