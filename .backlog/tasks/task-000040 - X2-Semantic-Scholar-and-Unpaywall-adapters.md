---
id: TASK-000040
title: X2 Semantic Scholar and Unpaywall adapters
status: To Do
assignee: []
created_date: '2026-10-18 12:22'
labels:
  - phase-4
  - backend
  - stretch
  - 'lane:x2'
milestone: m-4
dependencies:
  - TASK-000012
documentation:
  - PLAN.md
priority: low
type: enhancement
ordinal: 40000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
More open-access PDFs and citation data improve recall and graph quality. Can run early (after A4) with spare capacity.

Spec: PLAN.md card "X2 more literature" in section 7.7.
Stretch: independent of other stretch tasks. Do not merge during a demo freeze.
Worktree: lane/x2-literature
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Both adapters implement LiteratureSearch (or its OA lookup) and are wired by configuration
- [ ] #2 One live check per adapter
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
