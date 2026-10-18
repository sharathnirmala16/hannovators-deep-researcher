---
id: TASK-000009
title: 'A1 Nebius adapter: Nemotron 3.5 Super VL chat + embeddings'
status: Done
assignee:
  - '@devin'
created_date: '2026-10-18 12:20'
updated_date: '2026-10-18 14:21'
labels:
  - phase-1
  - backend
  - 'lane:a1'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every stage that reasons or extracts depends on the agent model, and retrieval depends on embeddings. Nemotron 3.5 Super VL is new, so the adapter must absorb structured-output quirks. Embeddings use Qwen/Qwen3-Embedding-8B with Matryoshka (MRL) truncation to EMBEDDING_DIMENSIONS (default 1024) to keep storage small, and instruction-prefixed queries.

Spec: PLAN.md sections 1.1, 5.1, 6, card "A1 nebius" in section 7.4.
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/a1-nebius
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ChatModel returns validated Pydantic objects using JSON-schema response_format and ignores reasoning_content
- [ ] #2 Invalid JSON gets one repair retry, then a typed error (test: fenced and truncated JSON)
- [ ] #3 ModelRole maps to model ID, reasoning effort, and temperature; a MODEL_<ROLE> override wins (test)
- [ ] #4 Images are sent as base64 data URLs for the vision role
- [ ] #5 Embedder sends dimensions, batches at most 64 texts, and returns L2-normalized vectors of length EMBEDDING_DIMENSIONS; a 4096-value response is truncated to the first N values and renormalized (test)
- [ ] #6 Queries are formatted as `Instruct: <instruction>\nQuery: <text>` only when an instruction is given; documents have no prefix (test)
- [ ] #7 Empty embedding input returns [] without a call (test); float32 BLOB helpers round-trip
- [ ] #8 Live checks: one tiny JSON completion and one two-string embedding whose length equals EMBEDDING_DIMENSIONS
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Nemotron ChatModel (json_schema, one repair retry) + Qwen3 Embedder (MRL truncate/renormalize, query prefix); live checks pass. PR: https://github.com/sharathnirmala16/hannovators-deep-researcher/pull/10
<!-- SECTION:FINAL_SUMMARY:END -->
