---
id: TASK-000012
title: 'A4 Literature adapters: PubMed E-utilities and Europe PMC'
status: To Do
assignee: []
created_date: '2026-10-18 12:20'
labels:
  - phase-1
  - backend
  - 'lane:a4'
milestone: m-1
dependencies:
  - TASK-000008
documentation:
  - PLAN.md
priority: high
type: feature
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Medical mode needs PubMed records, hit counts for iterative query refinement, citation links, and open-access PDFs.

Spec: PLAN.md sections 1.1, 4.5, card "A4 literature" in section 7.4. Reuse the excluded publication types from .archive/Quicker/Phase2-literature_search.ipynb.
Starts after: Gate G0. Parallel with: every other Phase 1 task (A1-A7, F1-F6).
Worktree: lane/a4-literature
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 count, search, related, and open_access_pdf_url implement LiteratureSearch
- [ ] #2 efetch XML maps to CandidateRecord; structured abstract sections join in order; a record without abstract is handled (tests)
- [ ] #3 Malformed XML raises a typed error (test); XML is parsed with defusedxml
- [ ] #4 Rate limiter never exceeds 3 req/s (10 with NCBI_API_KEY) in a burst (test)
- [ ] #5 Live checks: count > 0 for a fixed query; efetch of one known PMID; OA URL for one known PMCID
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Only files owned by the lane changed (PLAN.md section 2 and the card)
- [ ] #2 Rebased on main; AGENTS.md checks pass; `uv run pytest -m e2e` passes offline
- [ ] #3 Required edge-case tests from the card exist and pass; no extra tests without a reason
<!-- DOD:END -->
