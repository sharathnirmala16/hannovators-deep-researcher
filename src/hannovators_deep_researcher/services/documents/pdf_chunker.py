"""PDF text blocks -> paragraph chunks with a 1-based page and a bbox `[x0, y0, x1, y1]`.

Blocks of the first-page abstract become `ABSTRACT` chunks. All other blocks become `FULLTEXT`
chunks. A PDF with no text layer (a scan) gives zero chunks and `has_text_layer=False`.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from hannovators_deep_researcher.models.contracts import Rect
from hannovators_deep_researcher.models.enums import ChunkTier

MIN_CHUNK_CHARS = 200
ABSTRACT_MAX_CHARS = 4000
ABSTRACT_FALLBACK_MIN_CHARS = 300
MERGE_MAX_GAP_PT = 24.0

_TEXT_BLOCK = 0
_ABSTRACT_HEADING = re.compile(r"^(?:abstract|summary)\b[\s:.\-\u2013\u2014]*", re.IGNORECASE)
_ABSTRACT_END = re.compile(
    r"^(?:(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+[A-Z]|introduction\b|keywords?\b|key\s+words\b)",
    re.IGNORECASE,
)
_HYPHENATED_BREAK = re.compile(r"(\w)-\n(\w)")
_WHITESPACE = re.compile(r"\s+")
_LETTER = re.compile(r"[^\W\d_]")


@dataclass(frozen=True, slots=True)
class PdfChunk:
    tier: ChunkTier
    ordinal: int
    page: int
    bbox: Rect
    text: str


@dataclass(frozen=True, slots=True)
class PdfChunkResult:
    chunks: tuple[PdfChunk, ...]
    page_count: int
    has_text_layer: bool


@dataclass(frozen=True, slots=True)
class _Block:
    page: int
    bbox: Rect
    text: str


def chunk_pdf(path: Path) -> PdfChunkResult:
    """Read a PDF and return its paragraph chunks in reading order."""

    with pymupdf.open(path) as document:  # type: ignore[no-untyped-call]
        page_count = document.page_count
        pages = [_page_blocks(document[index], index + 1) for index in range(page_count)]
    if not any(pages):
        return PdfChunkResult(chunks=(), page_count=page_count, has_text_layer=False)

    abstract, first_page_rest = _split_abstract(pages[0])
    tiers = [(ChunkTier.ABSTRACT, abstract), (ChunkTier.FULLTEXT, first_page_rest)]
    tiers += [(ChunkTier.FULLTEXT, blocks) for blocks in pages[1:]]
    chunks: list[PdfChunk] = []
    for tier, blocks in tiers:
        for block in _merge_short(blocks):
            chunks.append(PdfChunk(tier, len(chunks), block.page, block.bbox, block.text))
    return PdfChunkResult(chunks=tuple(chunks), page_count=page_count, has_text_layer=True)


def _page_blocks(page: pymupdf.Page, page_number: int) -> list[_Block]:
    blocks: list[_Block] = []
    for raw in page.get_text("blocks", sort=True):  # type: ignore[no-untyped-call]
        x0, y0, x1, y1, text, _number, block_type = raw[:7]
        if block_type != _TEXT_BLOCK:
            continue
        normalized = _normalize(str(text))
        if _LETTER.search(normalized):
            bbox = (float(x0), float(y0), float(x1), float(y1))
            blocks.append(_Block(page_number, bbox, normalized))
    return blocks


def _normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", _HYPHENATED_BREAK.sub(r"\1\2", text)).strip()


def _split_abstract(blocks: list[_Block]) -> tuple[list[_Block], list[_Block]]:
    """Split first-page blocks into abstract blocks and the rest."""

    start = next(
        (index for index, block in enumerate(blocks) if _ABSTRACT_HEADING.match(block.text)),
        None,
    )
    if start is None:
        return _fallback_abstract(blocks)

    heading = blocks[start]
    body = _ABSTRACT_HEADING.sub("", heading.text, count=1)
    abstract = [_Block(heading.page, heading.bbox, body)] if body else []
    end = start + 1
    total = len(body)
    while end < len(blocks) and total < ABSTRACT_MAX_CHARS:
        if _ABSTRACT_END.match(blocks[end].text):
            break
        abstract.append(blocks[end])
        total += len(blocks[end].text)
        end += 1
    return abstract, blocks[:start] + blocks[end:]


def _fallback_abstract(blocks: list[_Block]) -> tuple[list[_Block], list[_Block]]:
    """Without an abstract heading, use the longest long-enough first-page block."""

    longest = max(blocks, key=lambda block: len(block.text), default=None)
    if longest is None or len(longest.text) < ABSTRACT_FALLBACK_MIN_CHARS:
        return [], blocks
    return [longest], [block for block in blocks if block is not longest]


def _merge_short(blocks: list[_Block]) -> list[_Block]:
    """Join a short block (a heading or a fragment) with the block just below it."""

    merged: list[_Block] = []
    for block in blocks:
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and len(previous.text) < MIN_CHUNK_CHARS
            and previous.page == block.page
            and _directly_below(previous.bbox, block.bbox)
        ):
            merged[-1] = _Block(
                block.page, _union(previous.bbox, block.bbox), f"{previous.text} {block.text}"
            )
        else:
            merged.append(block)
    return merged


def _directly_below(upper: Rect, lower: Rect) -> bool:
    """Same column, and the vertical gap is small, so the union bbox stays tight."""

    same_column = upper[0] < lower[2] and lower[0] < upper[2]
    return same_column and -MERGE_MAX_GAP_PT <= lower[1] - upper[3] <= MERGE_MAX_GAP_PT


def _union(first: Rect, second: Rect) -> Rect:
    return (
        min(first[0], second[0]),
        min(first[1], second[1]),
        max(first[2], second[2]),
        max(first[3], second[3]),
    )
