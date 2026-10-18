---
id: TASK-000010
title: A2 Jev System One adapter
status: Done
assignee:
  - '@devin'
created_date: '2026-10-18 12:20'
updated_date: '2026-10-18 14:21'
labels:
  - phase-1
  - backend
  - 'lane:a2'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Screening, span choice, domain detection, and UI routing all use Jev, served through the Command Code Provider API (POST https://api.commandcode.ai/provider/v1/systemone, model typesafe/jev-1.14.0 pinned). It has no batch endpoint, no prompt cache, and a 32K-token context, so concurrency, state truncation, and error handling live in the adapter.

Spec: PLAN.md sections 1.1-1.2, 4.5, 6, card "A2 jev" in section 7.4. Reference: https://commandcode.ai/models/jev
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/a2-jev
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 DecisionModel posts model, state, and questions with Bearer auth and a JEV_CONCURRENCY semaphore
- [ ] #2 Typed errors for 401, 402, 429 (honors Retry-After), and 5xx (test for 429)
- [ ] #3 A missing answer key and a choice outside the given options raise typed errors (tests)
- [ ] #4 noul exactly 0.5 is handled consistently by a documented threshold rule (test)
- [ ] #5 Live check: one request with one choice, one score, and one noul question
- [ ] #6 Typed error for 403 when the Command Code plan lacks Provider API access
- [ ] #7 A state above JEV_MAX_STATE_TOKENS is truncated before sending (test); a choice question with more than 20 options fails before any call (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Jev DecisionModel on /systemone with semaphore, Retry-After, state truncation, 20-option guard; live check passes. PR: https://github.com/sharathnirmala16/hannovators-deep-researcher/pull/10
<!-- SECTION:FINAL_SUMMARY:END -->
