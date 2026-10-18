---
id: TASK-000042
title: 'X4 More web search providers in the auto chain (Exa, Brave, ...)'
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
updated_date: '2026-10-18 13:21'
labels:
  - phase-4
  - backend
  - stretch
  - 'lane:x4'
milestone: m-4
dependencies:
  - TASK-000011
documentation:
  - PLAN.md
priority: low
type: enhancement
ordinal: 42000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
More providers make auto mode more robust. Can run early (after A3) with spare capacity.

Spec: PLAN.md card "X4 more web providers" in section 7.7. Reference: .archive/freesearch adapters.
Stretch: independent of other stretch tasks. Do not merge during a demo freeze.
Worktree: lane/x4-providers
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Optional fanout merges results with RRF (test for dedup across providers)
- [ ] #2 One live check per adapter
- [ ] #3 Exa (search + contents), Brave, Firecrawl, and You.com adapters implement WebSearchProvider and join WEB_SEARCH_PRIORITY
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
