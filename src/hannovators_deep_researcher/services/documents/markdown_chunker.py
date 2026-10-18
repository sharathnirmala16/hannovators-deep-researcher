"""Heading-aware chunks for markdown web snapshots. Markdown chunks have no page or bbox.

A chunk never crosses a heading. Each chunk keeps the path of headings above it. Lines inside
fenced code blocks are never read as headings.
"""

import re
from dataclasses import dataclass, field

DEFAULT_MAX_CHARS = 1500

_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


@dataclass(frozen=True, slots=True)
class MarkdownChunk:
    ordinal: int
    heading_path: tuple[str, ...]
    text: str

    @property
    def text_with_heading(self) -> str:
        """The text with its heading path as the first line, for indexing."""

        if not self.heading_path:
            return self.text
        return f"{' > '.join(self.heading_path)}\n\n{self.text}"


@dataclass
class _Section:
    heading_path: tuple[str, ...]
    paragraphs: list[str] = field(default_factory=list)


def chunk_markdown(markdown: str, *, max_chars: int = DEFAULT_MAX_CHARS) -> list[MarkdownChunk]:
    """Split markdown into chunks of at most about `max_chars` characters."""

    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    chunks: list[MarkdownChunk] = []
    for section in _sections(markdown):
        for text in _pack(section.paragraphs, max_chars):
            chunks.append(MarkdownChunk(len(chunks), section.heading_path, text))
    return chunks


def _sections(markdown: str) -> list[_Section]:
    headings: list[tuple[int, str]] = []
    sections = [_Section(heading_path=())]
    lines: list[str] = []
    fence: str | None = None

    def flush_paragraph() -> None:
        text = "\n".join(lines).strip()
        if text:
            sections[-1].paragraphs.append(text)
        lines.clear()

    for line in markdown.splitlines():
        fence_match = _FENCE.match(line)
        heading_match = _HEADING.match(line) if fence is None else None
        if fence_match and (fence is None or fence_match.group(1).startswith(fence)):
            fence = fence_match.group(1)[:3] if fence is None else None
            lines.append(line)
        elif heading_match:
            flush_paragraph()
            level = len(heading_match.group(1))
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, heading_match.group(2).strip()))
            sections.append(_Section(heading_path=tuple(title for _, title in headings)))
        elif fence is None and not line.strip():
            flush_paragraph()
        else:
            lines.append(line)
    flush_paragraph()
    return [section for section in sections if section.paragraphs]


def _pack(paragraphs: list[str], max_chars: int) -> list[str]:
    """Join paragraphs greedily up to `max_chars`; split a longer paragraph on words."""

    pieces = [
        piece
        for paragraph in paragraphs
        for piece in (
            [paragraph] if len(paragraph) <= max_chars else _split_words(paragraph, max_chars)
        )
    ]
    packed: list[str] = []
    for piece in pieces:
        if packed and len(packed[-1]) + 2 + len(piece) <= max_chars:
            packed[-1] = f"{packed[-1]}\n\n{piece}"
        else:
            packed.append(piece)
    return packed


def _split_words(text: str, max_chars: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}" if current else word
        if current and len(candidate) > max_chars:
            pieces.append(current)
            current = word
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces
