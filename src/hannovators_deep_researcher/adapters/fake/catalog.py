"""Canned medical and general candidate sets in `data/`, with query-overlap scoring."""

import re
from collections.abc import Collection
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from pydantic import Field

from hannovators_deep_researcher.adapters.fake.text import tokenize
from hannovators_deep_researcher.models.base import ContractModel
from hannovators_deep_researcher.models.enums import DomainMode, SourceOrigin
from hannovators_deep_researcher.models.literature import CandidateRecord, SourceLinkRecord

DATA_DIR = Path(__file__).resolve().parent / "data"
_SET_FILES = {DomainMode.MEDICAL: "medical.json", DomainMode.GENERAL: "general.json"}
_FIELD_TAG = re.compile(r"\[[^\]]*\]")


class CannedCandidateSet(ContractModel):
    """One domain's canned records. All names, identifiers, and numbers are invented."""

    domain: DomainMode
    research_question: str
    note: str
    records: list[CandidateRecord]
    links: list[SourceLinkRecord] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ScoredRecord:
    record: CandidateRecord
    score: float


@cache
def canned_set(domain: DomainMode) -> CannedCandidateSet:
    path = DATA_DIR / _SET_FILES[domain]
    return CannedCandidateSet.model_validate_json(path.read_text(encoding="utf-8"))


def canned_sets() -> tuple[CannedCandidateSet, ...]:
    return tuple(canned_set(domain) for domain in DomainMode)


def all_links() -> list[SourceLinkRecord]:
    return [link for candidate_set in canned_sets() for link in candidate_set.links]


def match_records(query: str, origins: Collection[SourceOrigin]) -> list[ScoredRecord]:
    """Records of the given origins that match `query`, best first.

    A query that names a record identifier (PMID, PMCID, DOI, URL) returns those records.
    Otherwise each record scores the share of query tokens in its title and abstract, and only
    the best-matching domain set answers, so medical and general results never mix.
    """

    exact = _exact_matches(query, origins)
    if exact:
        return exact
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return []
    best: list[ScoredRecord] = []
    for candidate_set in canned_sets():
        scored = [
            ScoredRecord(record, _overlap(query_tokens, record))
            for record in candidate_set.records
            if record.origin in origins
        ]
        matches = [item for item in scored if item.score > 0]
        if sum(item.score for item in matches) > sum(item.score for item in best):
            best = matches
    return sorted(best, key=lambda item: item.score, reverse=True)


def _exact_matches(query: str, origins: Collection[SourceOrigin]) -> list[ScoredRecord]:
    terms = {term.lower() for term in _FIELD_TAG.sub(" ", query).split()}
    return [
        ScoredRecord(record, 1.0)
        for candidate_set in canned_sets()
        for record in candidate_set.records
        if record.origin in origins and terms & _identifiers(record)
    ]


def _identifiers(record: CandidateRecord) -> set[str]:
    values = (record.external_id, record.pmid, record.pmcid, record.doi, record.url)
    return {value.lower() for value in values if value}


def _overlap(query_tokens: set[str], record: CandidateRecord) -> float:
    record_tokens = set(tokenize(f"{record.title} {record.abstract or ''}"))
    return round(len(query_tokens & record_tokens) / len(query_tokens), 4)
