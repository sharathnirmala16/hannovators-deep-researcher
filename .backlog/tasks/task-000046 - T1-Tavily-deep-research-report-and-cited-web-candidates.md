---
id: TASK-000046
title: T1 Tavily deep research report and cited web candidates
status: To Do
assignee: []
created_date: '2026-10-18 14:22'
updated_date: '2026-10-20 17:39'
labels:
  - phase-1
  - backend
  - 'lane:t1'
  - demo
milestone: m-1
dependencies:
  - TASK-000001
  - TASK-000011
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 46000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Tavily ships a deep research agent (Research API) that searches, extracts, and writes a cited report. It is already in the installed tavily-python 0.8.5, so it adds no dependency. It gives the demo a live narrative report, scores sponsor points, and its cited URLs feed the Jev-screened candidate pool.

Spec: PLAN.md section 1.1 (Deep research report row) and card "T1 tavily-research" in section 7.4.
Depends on: P0.1, A3 (Done). Parallel with: the demo lanes (API, adapters, stages, frontend A/B).
Worktree: hdr_wt_6, branch demo/deep-research.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 build_deep_research(settings, http) runs AsyncTavilyClient.research(model="mini") and polls get_research until completed, failed, or timeout
- [ ] #2 POST /api/workspaces/{id}/deep-research starts a background run that emits PROGRESS events and stores the record at data/workspaces/<ws>/deep_research.json; GET returns it
- [ ] #3 Each cited source becomes one WEB source with status RAW and extra_json.found_by=tavily_research, deduplicated by canonicalize_url (test)
- [ ] #4 A failed research task records status failed and never breaks the workspace run (test)
- [ ] #5 Live check: one mini research call on a short question
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Round 2 delivered this behavior; see TASK-000047..TASK-000050. Unit-test ACs stay open because the round-2 test policy allows only live e2e tests.
<!-- SECTION:NOTES:END -->
