"""Source-supplied publication date extraction for venture and deal pages."""

from __future__ import annotations

import re
from html.parser import HTMLParser

DATE_META_NAMES = {
    "article:published_time",
    "date",
    "datepublished",
    "dc.date",
    "dc.date.issued",
    "og:published_time",
    "parsely-pub-date",
    "pubdate",
    "publication_date",
}
ISO_DATE_RE = re.compile(r"^\d{4}(?:-\d{2}(?:-\d{2})?)?$")


class _PublishedDateParser(HTMLParser):
    """Read explicitly tagged publication dates, never modified dates."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.dates: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value for key, value in attrs}
        if tag.casefold() == "time":
            self._record(values.get("datetime"))
        name = (values.get("property") or values.get("name") or "").casefold()
        if name in DATE_META_NAMES:
            self._record(values.get("content") or values.get("datetime"))

    def _record(self, candidate: str | None) -> None:
        if candidate is None:
            return
        value = candidate.strip()
        match = re.match(r"^(\d{4}(?:-\d{2}(?:-\d{2})?)?)", value)
        if match and ISO_DATE_RE.fullmatch(match.group(1)):
            self.dates.append(match.group(1))


def extract_tagged_publication_date(text: str) -> str | None:
    """Extract a publication date from a tagged field or JSON-LD datePublished."""
    parser = _PublishedDateParser()
    parser.feed(text)
    if parser.dates:
        return parser.dates[0]
    json_ld_date = re.search(
        r"[\"']datePublished[\"']\s*:\s*[\"'](\d{4}(?:-\d{2}(?:-\d{2})?)?)",
        text,
        re.IGNORECASE,
    )
    return json_ld_date.group(1) if json_ld_date else None
