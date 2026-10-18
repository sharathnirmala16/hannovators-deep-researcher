"""Edge cases for search refinement and cross-provider deduplication."""

import pytest

from hannovators_deep_researcher.models.enums import SourceOrigin
from hannovators_deep_researcher.models.literature import CandidateRecord
from hannovators_deep_researcher.models.web import SearchResult
from hannovators_deep_researcher.services.pipeline.stages.search.candidates import (
    merge_candidates,
    web_candidate,
)
from hannovators_deep_researcher.services.pipeline.stages.search.refine import refine_query


@pytest.mark.unit
async def test_refinement_stops_at_max_rounds() -> None:
    """A query that never reaches the hit window is counted max_rounds times, then kept."""

    counted: list[str] = []
    rewrites = 0

    async def count(query: str) -> int:
        counted.append(query)
        return 0

    async def rewrite(query: str, hits: int) -> tuple[str, str]:
        nonlocal rewrites
        rewrites += 1
        return f"{query} broader{rewrites}", f"{hits} hits: broadened"

    attempts = await refine_query(
        "drug A", count=count, rewrite=rewrite, max_rounds=3, hits_min=1, hits_max=5000
    )

    assert counted == ["drug A", "drug A broader1", "drug A broader1 broader2"]
    assert rewrites == 2
    assert [attempt.iteration for attempt in attempts] == [0, 1, 2]
    assert attempts[0].note is None
    assert attempts[-1].note == "0 hits: broadened"


@pytest.mark.unit
def test_duplicate_across_pubmed_and_web_keeps_one_source() -> None:
    pubmed = CandidateRecord(
        origin=SourceOrigin.PUBMED,
        external_id="12345678",
        title="Drug A versus placebo",
        pmid="12345678",
        doi="10.1000/trial.1",
    )
    web_pubmed = web_candidate(
        SearchResult(
            title="Drug A versus placebo - PubMed",
            url="http://www.pubmed.ncbi.nlm.nih.gov/12345678/?utm_source=feed",
            provider="tavily",
        )
    )
    web_doi = web_candidate(
        SearchResult(title="Drug A", url="https://doi.org/10.1000/TRIAL.1", provider="tavily")
    )
    assert web_pubmed is not None
    assert web_doi is not None

    kept = merge_candidates(
        [(pubmed, "q1"), (web_pubmed, "q2"), (web_doi, "q3")], known_keys=set(), cap=10
    )

    assert kept == [(pubmed, "q1")]
