"""Render one PDF page to PNG bytes for the vision model."""

from pathlib import Path

import pymupdf

DEFAULT_DPI = 144
DEFAULT_MAX_SIDE_PX = 2048
_POINTS_PER_INCH = 72


def render_page_png(
    path: Path, page: int, *, dpi: int = DEFAULT_DPI, max_side_px: int = DEFAULT_MAX_SIDE_PX
) -> bytes:
    """Render a 1-based page at `dpi`, scaled down so the longer side is at most `max_side_px`."""

    if dpi < 1 or max_side_px < 1:
        raise ValueError("dpi and max_side_px must be positive")
    with pymupdf.open(path) as document:  # type: ignore[no-untyped-call]
        if not 1 <= page <= document.page_count:
            raise ValueError(f"page {page} is outside 1..{document.page_count}")
        pdf_page = document[page - 1]
        longest_side = max(pdf_page.rect.width, pdf_page.rect.height)
        zoom = dpi / _POINTS_PER_INCH
        if longest_side > 0:
            zoom = min(zoom, max_side_px / longest_side)
        matrix = pymupdf.Matrix(zoom, zoom)  # type: ignore[no-untyped-call]
        pixmap = pdf_page.get_pixmap(matrix=matrix, alpha=False)
        return bytes(pixmap.tobytes("png"))
