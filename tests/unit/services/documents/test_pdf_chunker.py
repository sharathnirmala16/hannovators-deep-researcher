"""Edge case: a PDF without a text layer (a scan) gives zero chunks and a flag."""

from pathlib import Path

import pymupdf
import pytest

from hannovators_deep_researcher.services.documents.pdf_chunker import chunk_pdf


@pytest.mark.unit
def test_pdf_without_text_layer_returns_zero_chunks_and_flag(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    with pymupdf.open() as document:  # type: ignore[no-untyped-call]
        page = document.new_page()
        page.draw_rect((72, 72, 300, 300), color=(0, 0, 0), fill=(0.5, 0.5, 0.5))
        document.save(path)

    result = chunk_pdf(path)

    assert result.chunks == ()
    assert result.has_text_layer is False
    assert result.page_count == 1
