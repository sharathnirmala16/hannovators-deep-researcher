"""Find a verbatim quote in a PDF and return its page and line rectangles.

The quote is normalized (whitespace, soft hyphens, line-break hyphenation, ligatures), then
searched with `page.search_for` in this order: the full quote, an ASCII-punctuation variant, and
the first ~60 characters. A prefix hit is extended to the end of the quote when the last ~60
characters are found later on the same page. Preferred pages are searched first.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from hannovators_deep_researcher.models.contracts import Rect

PREFIX_CHARS = 60
MIN_NEEDLE_CHARS = 12
MAX_RECTS = 40
MAX_SPAN_WORDS = 600
SEARCH_FLAGS = pymupdf.TEXT_DEHYPHENATE | pymupdf.TEXT_MEDIABOX_CLIP

_LIGATURES = str.maketrans({"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi"})
_ASCII = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
)
_LINE_HYPHEN = re.compile(r"([a-z])-\s+([a-z])")
_EDGE = " \t\n\"'\u201c\u201d\u2018\u2019.,;:\u2026"


@dataclass(frozen=True, slots=True)
class QuoteMatch:
    page: int
    rects: list[Rect]
    needle: str
    full: bool
    """True when the whole quote (not only its start) was found."""


def normalize_quote(text: str) -> str:
    cleaned = text.replace("\u00ad", "").replace("\ufb04", "ffl").translate(_LIGATURES)
    cleaned = " ".join(cleaned.split())
    cleaned = _LINE_HYPHEN.sub(r"\1\2", cleaned)
    return cleaned.strip(_EDGE).replace("...", " ").replace("\u2026", " ").strip()


def _cut(text: str, size: int, *, from_end: bool = False) -> str:
    if len(text) <= size:
        return text
    if from_end:
        piece = text[-size:]
        return piece.split(" ", 1)[1] if " " in piece else piece
    piece = text[:size]
    return piece.rsplit(" ", 1)[0] if " " in piece else piece


def needles(quote: str) -> list[tuple[str, bool]]:
    """Search strings in order, each with whether it covers the whole quote."""

    normalized = normalize_quote(quote)
    ascii_form = normalized.translate(_ASCII)
    candidates = [
        (normalized, True),
        (ascii_form, True),
        (_cut(normalized, PREFIX_CHARS), False),
        (_cut(ascii_form, PREFIX_CHARS), False),
    ]
    seen: set[str] = set()
    result: list[tuple[str, bool]] = []
    for needle, full in candidates:
        if len(needle) >= MIN_NEEDLE_CHARS and needle not in seen:
            seen.add(needle)
            result.append((needle, full or needle == normalized))
    return result


def _rect(value: pymupdf.Rect) -> Rect:
    return (round(value.x0, 2), round(value.y0, 2), round(value.x1, 2), round(value.y1, 2))


def _line_rects(page: pymupdf.Page, start: pymupdf.Rect, end: pymupdf.Rect) -> list[Rect]:
    """Line rectangles of the words from the one under `start` to the one under `end`."""

    words = page.get_text("words", sort=False)  # type: ignore[no-untyped-call]
    boxes: list[Rect] = [(float(w[0]), float(w[1]), float(w[2]), float(w[3])) for w in words]
    first_box, end_box = _rect(start), _rect(end)
    first = next((i for i, box in enumerate(boxes) if _overlaps(box, first_box)), None)
    last = next(
        (i for i in range(len(boxes) - 1, -1, -1) if _overlaps(boxes[i], end_box)),
        None,
    )
    if first is None or last is None or not 0 <= last - first <= MAX_SPAN_WORDS:
        return []
    lines: dict[tuple[int, int], Rect] = {}
    for word, box in zip(words[first : last + 1], boxes[first : last + 1], strict=True):
        key = (int(word[5]), int(word[6]))
        old = lines.get(key)
        lines[key] = (
            box
            if old is None
            else (
                min(old[0], box[0]),
                min(old[1], box[1]),
                max(old[2], box[2]),
                max(old[3], box[3]),
            )
        )
    return [
        (round(b[0], 2), round(b[1], 2), round(b[2], 2), round(b[3], 2)) for b in lines.values()
    ]


def _overlaps(first: Rect, second: Rect) -> bool:
    return (
        first[0] < second[2]
        and second[0] < first[2]
        and first[1] < second[3]
        and second[1] < first[3]
    )


def _extend(page: pymupdf.Page, prefix_hits: list[pymupdf.Rect], quote: str) -> list[Rect]:
    """Extend a prefix hit to the quote's last characters when they are on the same page."""

    normalized = normalize_quote(quote)
    for tail in (
        _cut(normalized, PREFIX_CHARS, from_end=True),
        _cut(normalized.translate(_ASCII), PREFIX_CHARS, from_end=True),
    ):
        if len(tail) < MIN_NEEDLE_CHARS:
            continue
        tail_hits = page.search_for(tail, flags=SEARCH_FLAGS)
        after = [
            hit for hit in tail_hits if hit.y1 >= prefix_hits[0].y0 or hit.x0 > prefix_hits[0].x1
        ]
        if after:
            span = _line_rects(page, prefix_hits[0], after[-1])
            if span:
                return span
    return [_rect(hit) for hit in prefix_hits]


def _page_order(page_count: int, preferred: Sequence[int]) -> list[int]:
    first = [page for page in dict.fromkeys(preferred) if 1 <= page <= page_count]
    return first + [page for page in range(1, page_count + 1) if page not in first]


def locate_quote(
    path: Path, quote: str, *, preferred_pages: Sequence[int] = (), only_preferred: bool = False
) -> QuoteMatch | None:
    """Find `quote` in the PDF at `path` (blocking; run it in a thread)."""

    candidates = needles(quote)
    if not candidates:
        return None
    with pymupdf.open(path) as document:  # type: ignore[no-untyped-call]
        order = _page_order(document.page_count, preferred_pages)
        if only_preferred:
            order = [page for page in order if page in preferred_pages]
        for needle, full in candidates:
            for number in order:
                page = document[number - 1]
                hits = page.search_for(needle, flags=SEARCH_FLAGS)
                if not hits:
                    continue
                rects = [_rect(hit) for hit in hits] if full else _extend(page, hits, quote)
                return QuoteMatch(page=number, rects=rects[:MAX_RECTS], needle=needle, full=full)
    return None
