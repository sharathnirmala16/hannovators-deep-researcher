---
id: TASK-000011
title: 'A3 Web search provider abstraction with auto mode (Tavily, Exa)'
status: To Do
assignee: []
created_date: '2026-10-18 12:20'
labels:
  - phase-1
  - backend
  - 'lane:a3'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The project must work with any web search provider and survive provider failures during the demo. This ports the freesearch provider contract, resilience, and routing in slim form.

Spec: PLAN.md sections 1.1, 4.5, 5.1, 6, card "A3 websearch" in section 7.4. Reference: .archive/freesearch/src/freesearch/adapters/base.py, registry.py, services/routing.py, infrastructure/resilience.py, adapters/tavily.py.
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/a3-websearch
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tavily (search + extract) and Exa (search + contents) implement WebSearchProvider
- [ ] #2 Router supports auto, prefer, and require; auto follows WEB_SEARCH_PRIORITY and skips unconfigured or open-circuit providers
- [ ] #3 Primary 429 -> fallback answers and attempts lists both (test); all fail -> one typed error with each reason (test)
- [ ] #4 No configured provider -> clear startup error; pinned provider without a key -> error, no silent fallback (tests)
- [ ] #5 fetch uses only providers with supports_fetch; result URLs are canonicalized and deduplicated
- [ ] #6 Live checks: Tavily search (limit 3) and extract (one URL); auto picks the first configured provider
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
