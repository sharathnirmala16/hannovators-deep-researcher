"""Web result conversion and cross-provider deduplication of candidates."""

import re
from collections.abc import Iterable, Sequence
from urllib.parse import unquote

from hannovators_deep_researcher.models.enums import SourceOrigin
from hannovators_deep_researcher.models.literature import CandidateRecord
from hannovators_deep_researcher.models.web import SearchResult
from hannovators_deep_researcher.services.urls import canonicalize_url

_PUBMED_URL = re.compile(r"//(?:www\.)?pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")
_DOI_URL = re.compile(r"//(?:dx\.)?doi\.org/(10\.[^?#]+)", re.IGNORECASE)
_YEAR = re.compile(r"^(\d{4})")


def web_candidate(result: SearchResult) -> CandidateRecord | None:
    """A WEB candidate whose external ID is the canonical URL; None when the URL is empty."""

    url = canonicalize_url(result.url)
    if not url:
        return None
    year = _YEAR.match(result.published_at or "")
    return CandidateRecord(
        origin=SourceOrigin.WEB,
        external_id=url,
        title=result.title or url,
        abstract=result.snippet or None,
        year=int(year[1]) if year else None,
        url=url,
    )


def dedupe_keys(
    *,
    external_id: str,
    url: str | None = None,
    doi: str | None = None,
    pmid: str | None = None,
) -> set[str]:
    """Keys that identify one work: canonical URLs, `pmid:<id>`, and `doi:<doi>`.

    PubMed and doi.org URLs map to their PMID or DOI, so a web hit on a PubMed page matches
    the PubMed record.
    """

    pmids = {pmid} if pmid else set()
    dois = {doi.lower()} if doi else set()
    keys: set[str] = set()
    for value in (external_id, url):
        value = (value or "").strip()
        if value.startswith(("http://", "https://")):
            canonical = canonicalize_url(value)
            keys.add(canonical)
            if match := _PUBMED_URL.search(canonical):
                pmids.add(match[1])
            if match := _DOI_URL.search(canonical):
                dois.add(unquote(match[1]).lower())
        elif value.isdigit():
            pmids.add(value)
        elif value.startswith("10."):
            dois.add(value.lower())
        elif value:
            keys.add(value.lower())
    return keys | {f"pmid:{value}" for value in pmids} | {f"doi:{value}" for value in dois}


def record_keys(record: CandidateRecord) -> set[str]:
    return dedupe_keys(
        external_id=record.external_id, url=record.url, doi=record.doi, pmid=record.pmid
    )


def round_robin[T](groups: Sequence[Sequence[T]]) -> list[T]:
    """Interleave groups (first of each, then second of each, ...), so the candidate cap
    keeps a share of every query instead of only the first queries' results."""

    merged: list[T] = []
    for index in range(max((len(group) for group in groups), default=0)):
        merged.extend(group[index] for group in groups if index < len(group))
    return merged


def merge_candidates[T](
    found: Iterable[tuple[CandidateRecord, T]], *, known_keys: set[str], cap: int
) -> list[tuple[CandidateRecord, T]]:
    """Keep the first record of each work, skip works in `known_keys`, stop at `cap`."""

    seen = set(known_keys)
    kept: list[tuple[CandidateRecord, T]] = []
    for record, tag in found:
        if len(kept) >= cap:
            break
        keys = record_keys(record)
        if keys & seen:
            continue
        seen |= keys
        kept.append((record, tag))
    return kept
