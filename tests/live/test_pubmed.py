"""Live PubMed check. Runs without a key at 3 requests/s."""

import pytest

from hannovators_deep_researcher.adapters.pubmed import build_literature_search
from hannovators_deep_researcher.configuration.settings import get_settings
from hannovators_deep_researcher.infrastructure.http import create_http_client

pytestmark = pytest.mark.live


async def test_pubmed_count_and_search() -> None:
    async with create_http_client() as http:
        pubmed = build_literature_search(get_settings(), http)
        assert await pubmed.count("aspirin myocardial infarction") > 0
        records = await pubmed.search("aspirin myocardial infarction randomized", limit=2)

    assert 1 <= len(records) <= 2
    assert all(record.pmid and record.title for record in records)
