"""Edge case: highlight rects outside the page are clipped or skipped."""

from pathlib import Path

import pymupdf
import pytest

from hannovators_deep_researcher.services.documents.highlighter import (
    HighlightResult,
    HighlightSpec,
    write_highlighted_pdf,
)

PAGE_WIDTH = 600
PAGE_HEIGHT = 800


@pytest.mark.unit
def test_rects_outside_the_page_are_clipped(tmp_path: Path) -> None:
    source = tmp_path / "raw.pdf"
    destination = tmp_path / "highlighted.pdf"
    with pymupdf.open() as document:  # type: ignore[no-untyped-call]
        document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        document.save(source)

    result = write_highlighted_pdf(
        source,
        destination,
        [
            HighlightSpec(page=1, rects=[(700, 900, 500, 700)]),
            HighlightSpec(page=1, rects=[(650, 850, 700, 900)]),
            HighlightSpec(page=2, rects=[(10, 10, 20, 20)]),
        ],
    )

    assert result == HighlightResult(annotations=1, skipped_rects=2)
    with pymupdf.open(destination) as document:  # type: ignore[no-untyped-call]
        page = document[0]
        annotations = list(page.annots())
        assert len(annotations) == 1
        vertices = annotations[0].vertices
    xs = [x for x, _ in vertices]
    ys = [y for _, y in vertices]
    assert min(xs) == pytest.approx(500)
    assert min(ys) == pytest.approx(700)
    assert max(xs) == pytest.approx(PAGE_WIDTH)
    assert max(ys) == pytest.approx(PAGE_HEIGHT)
