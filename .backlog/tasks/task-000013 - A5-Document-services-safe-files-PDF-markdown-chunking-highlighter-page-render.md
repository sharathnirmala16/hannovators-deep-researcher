---
id: TASK-000013
title: >-
  A5 Document services: safe files, PDF/markdown chunking, highlighter, page
  render
status: To Do
assignee: []
created_date: '2026-10-18 12:20'
labels:
  - phase-1
  - backend
  - 'lane:a5'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Every source file goes through one safe path module, and chunks need page and bounding-box data so claims can be highlighted in the PDF. No network calls except the download helper.

Spec: PLAN.md section 4.1, card "A5 documents" in section 7.4.
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/a5-documents
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 files.py rejects .., absolute, and drive-letter paths and paths outside data/workspaces (tests)
- [ ] #2 Download streams with a size cap and content-type check; over the cap aborts (test)
- [ ] #3 pdf_chunker yields paragraph chunks with page and bbox and an ABSTRACT tier; a PDF without a text layer returns zero chunks and a flag, not an exception (test)
- [ ] #4 markdown_chunker yields heading-aware chunks
- [ ] #5 highlighter writes highlighted.pdf from (page, rects, color); rects outside the page are clipped (test)
- [ ] #6 page_render returns PNG bytes for a page
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
