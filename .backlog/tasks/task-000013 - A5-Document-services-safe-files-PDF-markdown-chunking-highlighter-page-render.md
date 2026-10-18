---
id: TASK-000013
title: >-
  A5 Document services: safe files, PDF/markdown chunking, highlighter, page
  render
status: In Progress
assignee:
  - '@devin'
created_date: '2026-10-18 12:20'
updated_date: '2026-10-18 13:41'
labels:
  - phase-1
  - backend
  - 'lane:a5'
milestone: m-1
dependencies:
  - TASK-000001
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
Early start: needs only P0.1 (Done). Parallel with: P0.3, P0.6, A3. May merge before Gate G0 (own files only).
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. files.py: validate POSIX relative data paths (reject empty, backslash, NUL, absolute, drive letter/UNC, '.'/'..'/empty segments, anything not under workspaces/); resolve_data_path() is the only relative->absolute step and re-checks containment after resolve() (symlinks); source_path() builds workspaces/<ws>/sources/<src>/<file> from safe IDs; write_bytes(); async download() streams with httpx, checks content type, aborts on Content-Length or streamed bytes over max_bytes, writes to a .part file and replaces atomically.
2. pdf_chunker.py: PyMuPDF text blocks per page (1-based page, bbox [x0,y0,x1,y1]) -> normalized paragraph chunks (merge short blocks, union bbox); first-page block starting with Abstract/Summary (plus following blocks up to the next heading) -> ABSTRACT tier, fallback to the longest first-page block; rest FULLTEXT. No text layer -> zero chunks and has_text_layer=False.
3. markdown_chunker.py: ATX heading-aware chunks (heading path, fenced code ignored), paragraphs packed up to max_chars, never across headings, long paragraphs split on words.
4. highlighter.py: HighlightSpec(page, rects, color hex) -> highlight annotations; rects normalized and clipped to page.rect, empty/out-of-page rects and pages skipped; save highlighted.pdf atomically; return written/skipped counts.
5. page_render.py: render a 1-based page to PNG bytes at a dpi with a max-side cap.
6. Tests (tests/unit/services/documents): unsafe paths rejected; download over the size cap aborts (header and streamed); no-text-layer PDF -> zero chunks + flag; rects outside the page are clipped. PDFs generated with pymupdf in tmp_path.
7. Run ruff format/check, mypy, pytest, uv build; commit, rebase on origin/main, push, PR, finalize.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented services/documents: files.py (validate_relative_path, resolve_data_path, source_path, write_bytes, async download with content-type check, Content-Length and streamed size cap, .part file removed on any failure), pdf_chunker.py (chunk_pdf -> PdfChunkResult(chunks, page_count, has_text_layer); 1-based page, bbox (x0, y0, x1, y1); abstract heading block plus following blocks up to Introduction/Keywords/numbered heading -> ABSTRACT, fallback to the longest first-page block >= 300 chars; short blocks merge only with the block directly below in the same column), markdown_chunker.py (chunk_markdown -> MarkdownChunk(ordinal, heading_path, text) plus text_with_heading; fenced code ignored for headings), highlighter.py (write_highlighted_pdf -> HighlightResult(annotations, skipped_rects); rects normalized and clipped to page.rect; out-of-page rects and pages skipped; atomic save), page_render.py (render_page_png, 1-based page, dpi with a max-side cap).
Contracts: PLAN.md 4.4 lists no chunk DTO in models/, so chunk outputs are frozen dataclasses local to services/documents (PdfChunk, MarkdownChunk). Stages map them to chunks rows (bbox_json = list(bbox)). If the integrator wants a shared Chunk contract in models/, that is a P0 change. Rect is reused from models/contracts.py.
PyMuPDF is only partly typed; mypy strict needs line-level '# type: ignore[no-untyped-call]' on pymupdf.open/Matrix/Rect/get_text (pyproject is frozen for this lane).
Tests (17): unsafe paths (13 cases), download over cap (Content-Length and streamed), no-text-layer PDF, rects clipped/skipped. Happy paths checked by a throwaway script, not committed.
Checks: ruff format/check, mypy, pytest (21 passed), uv build all pass. 'uv run pytest -m e2e' selects 0 tests: no e2e suite exists on main yet (P0 skeleton not landed).
<!-- SECTION:NOTES:END -->
