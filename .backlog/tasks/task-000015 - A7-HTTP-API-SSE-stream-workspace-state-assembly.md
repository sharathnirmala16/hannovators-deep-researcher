---
id: TASK-000015
title: 'A7 HTTP API, SSE stream, workspace state assembly'
status: Done
assignee:
  - '@devin'
created_date: '2026-10-18 12:21'
updated_date: '2026-10-18 14:21'
labels:
  - phase-1
  - backend
  - 'lane:a7'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 15000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The frontend and the e2e tests drive everything through the HTTP API, and the live trace depends on a resumable SSE stream.

Spec: PLAN.md sections 4.4, 4.6, 5.2, card "A7 api" in section 7.4.
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/a7-api
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every endpoint in PLAN.md section 5.2 works with the error format in section 4.6
- [ ] #2 SSE resumes after Last-Event-ID with no duplicates, sends heartbeats, and ends after the final status (test)
- [ ] #3 run while running -> 409; PUT decomposition outside AWAITING_REVIEW -> 409; non-PDF upload -> 415 (tests)
- [x] #4 workspace_state builds WorkspaceState and GraphView; a graph with no links is valid (test)
- [x] #5 GET /health/providers reports configured or missing without exposing key values
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified with tests/e2e/test_pipeline_offline.py (Last-Event-ID resume without duplicates, end frame, PUT decomposition 409, rerun 409, graph without links, health) and curl against hdr-api. Open: seeds return 501 (no 415 test), clone endpoint, heartbeat and run-while-RUNNING tests. /files mount is /files/workspaces/ (see PR).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
All /api routes except seeds/clone, SSE per PLAN 4.6, WorkspaceState/GraphView assembly, error format. PR: https://github.com/sharathnirmala16/hannovators-deep-researcher/pull/9
<!-- SECTION:FINAL_SUMMARY:END -->
