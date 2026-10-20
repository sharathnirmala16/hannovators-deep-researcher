---
id: TASK-000047
title: 'R2 Grounding: seed ingest, full-text acquire, highlights, cited chat backend'
status: Done
assignee: []
created_date: '2026-10-20 17:39'
updated_date: '2026-10-20 17:39'
labels:
  - backend
  - round-2
dependencies: []
ordinal: 47000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Round 2 lane grounding was written during the hackathon but never run. Seeds, open-access downloads, highlights, and the cited chat had to work end to end so every answer can open the exact PDF passage.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Seed PDFs are chunked with page and bbox, embedded, and get findings with verified quotes
- [x] #2 Promoted sources get an open-access PDF or web snapshot; downloads appear as DOWNLOAD trajectory steps
- [x] #3 Claim quotes become highlight rows with page and rects
- [x] #4 POST /chat returns an answer whose PDF citations carry page and rects; a CHAT step parents its retrieval and LLM steps
- [x] #5 Live e2e tests in tests/e2e/test_live_grounding.py pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Fix data-root resolution for ASGI apps; move OA lookup to adapters/europepmc.py (AWS PMC copy, Unpaywall repositories); route downloads through record_download; extract seed findings; locate chat citation rects by quote search with bbox fallbacks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Real seed_1 run through the UI (workspace 426eebdc): COMPLETED, 3 seeds chunked, 55 highlights, 4 DOWNLOAD steps in the agent run. Chat answer in the UI cited 5 passages with pages; citation [2] opened the Lancet meta-analysis at page 2 with the highlight over the quoted sentence. Fixed after review: chat dropped all citations when the model set covered=false on a partly covered answer; the prompt also leaked the field name.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Grounding works end to end: seed ingest, OA full text (Europe PMC/AWS/Unpaywall), DOWNLOAD trajectory steps, quote highlights, and cited chat with page+rects. Verified by tests/e2e/test_live_grounding.py (2 live tests pass), a real seed_1 run, and the UI citation-to-PDF check.
<!-- SECTION:FINAL_SUMMARY:END -->
