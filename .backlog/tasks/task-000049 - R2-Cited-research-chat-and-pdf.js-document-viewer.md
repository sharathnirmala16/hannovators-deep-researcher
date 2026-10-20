---
id: TASK-000049
title: R2 Cited research chat and pdf.js document viewer
status: Done
assignee: []
created_date: '2026-10-20 17:39'
updated_date: '2026-10-20 17:39'
labels:
  - frontend
  - round-2
dependencies: []
ordinal: 49000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The chat panel was a placeholder and the document view was an iframe that could only jump to a page, so citations could not show the exact passage.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The Chat view lists history, sends questions, and shows pending, error, and empty states
- [x] #2 Every citation [n] is a button that opens the source in the Document view
- [x] #3 The pdf.js viewer renders pages lazily with page navigation and zoom, and draws highlight rectangles for claims and citations
- [x] #4 Selecting a citation scrolls the highlighted passage into view
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
features/research-chat: useChat hook, safe markdown renderer, citation buttons via citationSelection. features/pdf-viewer: pdf.js with lazy page rendering, toolbar, text layer, highlight overlay in PDF points (top-left origin), quote fallback, scroll-to-highlight.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Verified in Playwright against the live API: chat empty/pending/error/answer states, citation [2] switched the right pane to Document, opened page 2 of 11 and drew the highlight over the cited sentence.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Cited chat and the pdf.js viewer replace the placeholder and the iframe. Citations open the exact highlighted passage. Verified manually in the browser on the seed_1 workspace; pnpm check/build/test pass.
<!-- SECTION:FINAL_SUMMARY:END -->
