---
id: TASK-000011
title: A3 Web search provider abstraction with auto mode (Tavily)
status: To Do
assignee: []
created_date: '2026-10-18 12:20'
updated_date: '2026-10-18 13:21'
labels:
  - phase-1
  - backend
  - 'lane:a3'
milestone: m-1
dependencies:
  - TASK-000001
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The project must work with any web search provider and survive provider failures during the demo. This ports the freesearch provider contract, resilience, and routing in slim form, with Tavily as the only provider for now (Exa and others are X4). High priority: time is short.

Spec: PLAN.md sections 1.1, 4.5, 5.1, 6, card "A3 websearch" in section 7.4. Reference: .archive/freesearch/src/freesearch/adapters/base.py, registry.py, services/routing.py, services/aggregation.py (canonicalize_url), infrastructure/resilience.py, adapters/tavily.py.
Early start: needs only P0.1 (Done). Parallel with: P0.3, P0.6, A5. May merge before Gate G0 (own files only).
Worktree: lane/a3-websearch
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Router supports auto, prefer, and require; auto follows WEB_SEARCH_PRIORITY and skips unconfigured or open-circuit providers
- [ ] #2 Primary 429 -> fallback answers and attempts lists both (test); all fail -> one typed error with each reason (test)
- [ ] #3 No configured provider -> clear startup error; pinned provider without a key -> error, no silent fallback (tests)
- [ ] #4 Tavily (search + extract via tavily-python) implements WebSearchProvider without freesearch quota, PAYGO, or usage bookkeeping
- [ ] #5 Priority names without a registered adapter (e.g. exa) are skipped with a startup warning
- [ ] #6 fetch uses only providers with supports_fetch; services/urls.py canonicalize_url strips tracking params, www., default ports, and fragments, and results are deduplicated by it (test)
- [ ] #7 Live checks: Tavily search (limit 3) and extract (one URL); auto picks Tavily
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
