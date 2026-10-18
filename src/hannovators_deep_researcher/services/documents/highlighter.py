"""Write `highlighted.pdf`: a copy of the source PDF with highlight annotations.

Rects are `[x0, y0, x1, y1]` in PDF points on a 1-based page. Each rect is clipped to the page.
Rects with no area inside the page, and highlights on pages that do not exist, are skipped.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from hannovators_deep_researcher.models.contracts import Rect

DEFAULT_HIGHLIGHT_COLOR = "#FFE066"

_HEX_COLOR = re.compile(r"^#?([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})([0-9A-Fa-f]{2})$")


@dataclass(frozen=True, slots=True)
class HighlightSpec:
    page: int
    rects: Sequence[Rect]
    color: str = DEFAULT_HIGHLIGHT_COLOR


@dataclass(frozen=True, slots=True)
class HighlightResult:
    annotations: int
    skipped_rects: int


def write_highlighted_pdf(
    source: Path, destination: Path, highlights: Iterable[HighlightSpec]
) -> HighlightResult:
    """Copy `source` to `destination` with one highlight annotation per spec."""

    if source.resolve() == destination.resolve():
        raise ValueError("destination must differ from source")
    specs = [(spec, parse_color(spec.color)) for spec in highlights]
    annotations = 0
    skipped = 0
    partial = destination.with_name(destination.name + ".part")
    with pymupdf.open(source) as document:  # type: ignore[no-untyped-call]
        for spec, color in specs:
            if not 1 <= spec.page <= document.page_count:
                skipped += len(spec.rects)
                continue
            page = document[spec.page - 1]
            clipped = clip_rects(spec.rects, page.rect)
            skipped += len(spec.rects) - len(clipped)
            if not clipped:
                continue
            annotation = page.add_highlight_annot(clipped)
            annotation.set_colors(stroke=color)
            annotation.update()
            annotations += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        document.save(partial, garbage=3, deflate=True)
    partial.replace(destination)
    return HighlightResult(annotations=annotations, skipped_rects=skipped)


def clip_rects(rects: Iterable[Rect], page_rect: pymupdf.Rect) -> list[pymupdf.Rect]:
    """Normalize each rect, clip it to the page, and drop rects with no area left."""

    clipped: list[pymupdf.Rect] = []
    for rect in rects:
        inside = pymupdf.Rect(rect).normalize() & page_rect  # type: ignore[no-untyped-call]
        if not inside.is_empty:
            clipped.append(inside)
    return clipped


def parse_color(color: str) -> tuple[float, float, float]:
    """Parse `#RRGGBB` into PDF RGB floats in 0..1."""

    match = _HEX_COLOR.match(color)
    if match is None:
        raise ValueError(f"color must be #RRGGBB: {color!r}")
    red, green, blue = (int(channel, 16) / 255 for channel in match.groups())
    return red, green, blue
