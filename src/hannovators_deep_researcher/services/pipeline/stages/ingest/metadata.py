"""Seed metadata: PyMuPDF document metadata, first-page text, DOI detection, and the LLM schema."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf
from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel

FIRST_PAGES = 4
FIRST_TEXT_CHARS = 9_000
HEAD_CHARS = 2_000
_ABSTRACT = re.compile(r"^\s*(abstract|summary)\b", re.IGNORECASE | re.MULTILINE)
_DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)
_DOI_TRAILING = ".,;:)]}'"
_YEAR = re.compile(r"(19|20)\d{2}")
_BAD_TITLES = re.compile(r"^(untitled|microsoft word|document\d*|title)\b|\.(pdf|docx?)$", re.I)

EXTRACT_SYSTEM = (
    "You extract bibliographic metadata from the first pages of a scientific paper. Copy the "
    "title exactly. Copy the abstract verbatim when the text has one, else use an empty string. "
    "List at most 5 key findings: each has a short `statement` of a main result (with the "
    "numbers as the text states them) and a `quote`: one sentence or clause copied character "
    "for character from the text that supports it (at most 250 characters, no ellipsis). Use "
    "null for any field the text does not give. Reply with JSON only."
)
MAX_FINDINGS = 5


class SeedFinding(ContractModel):
    statement: str
    quote: str = ""


class SeedMetadata(ContractModel):
    """LLM reply: metadata of a seed PDF read from its first pages."""

    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    study_design: str | None = None
    abstract: str = ""
    findings: list[SeedFinding] = Field(default_factory=list)

    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {
            "title": "Seed study of the intervention versus comparison",
            "authors": ["Doe J", "Roe R"],
            "year": 2023,
            "venue": "Journal of Examples",
            "doi": None,
            "study_design": "Randomized controlled trial",
            "abstract": "",
            "findings": [
                {
                    "statement": "The intervention reduced the primary outcome versus comparison.",
                    "quote": "randomized",
                }
            ],
        }


@dataclass(frozen=True, slots=True)
class PdfFacts:
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    first_text: str = ""


def plausible_title(title: str | None) -> str | None:
    cleaned = " ".join((title or "").split())
    if len(cleaned) < 12 or _BAD_TITLES.search(cleaned):
        return None
    return cleaned


def find_doi(text: str) -> str | None:
    match = _DOI.search(text)
    return match.group(1).rstrip(_DOI_TRAILING) if match else None


def excerpt(text: str) -> str:
    """The opening (title, authors) plus the abstract, even after a long author list.

    Author manuscripts and consortium papers can spend whole pages on names and affiliations,
    so when the abstract heading starts late, keep the head and jump to the abstract.
    """

    match = _ABSTRACT.search(text)
    if match is None or match.start() <= HEAD_CHARS:
        return text[:FIRST_TEXT_CHARS]
    tail = text[match.start() : match.start() + FIRST_TEXT_CHARS - HEAD_CHARS]
    return f"{text[:HEAD_CHARS]}\n[...]\n{tail}"


def read_pdf_facts(path: Path) -> PdfFacts:
    """Metadata and first-page text of a PDF (blocking; run it in a thread)."""

    with pymupdf.open(path) as document:  # type: ignore[no-untyped-call]
        metadata: dict[str, str] = dict(document.metadata or {})
        pages = min(FIRST_PAGES, document.page_count)
        text = excerpt("\n".join(str(document[index].get_text()) for index in range(pages)))
    year_match = _YEAR.search(metadata.get("creationDate") or "")
    authors = [
        name.strip() for name in re.split(r"[;,]| and ", metadata.get("author") or "") if name
    ]
    return PdfFacts(
        title=plausible_title(metadata.get("title")),
        authors=[name for name in authors if name],
        year=int(year_match.group()) if year_match else None,
        doi=find_doi(metadata.get("subject") or "") or find_doi(text),
        first_text=text[:FIRST_TEXT_CHARS],
    )
