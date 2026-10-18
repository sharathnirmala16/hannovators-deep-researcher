"""Fake web search router: serves the canned WEB records and their page text."""

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from hannovators_deep_researcher.adapters.fake.catalog import (
    ScoredRecord,
    canned_sets,
    match_records,
)
from hannovators_deep_researcher.models.enums import ProviderAttemptStatus, SourceOrigin
from hannovators_deep_researcher.models.literature import CandidateRecord
from hannovators_deep_researcher.models.web import (
    FetchedDocument,
    ProviderAttempt,
    ProviderError,
    ProviderFailure,
    SearchResult,
    WebSearchRequest,
    WebSearchResponse,
)

if TYPE_CHECKING:
    from hannovators_deep_researcher.models.ports import WebSearch

FAKE_WEB_PROVIDER = "fake"
_WEB_ORIGINS = frozenset({SourceOrigin.WEB})


class FakeWebSearch:
    """Implements the `WebSearch` port. `days` is ignored; unknown URLs fail with NOT_FOUND."""

    async def search(self, request: WebSearchRequest) -> WebSearchResponse:
        matches = [
            item
            for item in match_records(request.query, _WEB_ORIGINS)
            if _domain_allowed(item.record, request)
        ]
        return WebSearchResponse(
            query=request.query,
            results=[_result(item) for item in matches[: request.limit]],
            provider=FAKE_WEB_PROVIDER,
            attempts=[
                ProviderAttempt(
                    provider=FAKE_WEB_PROVIDER, status=ProviderAttemptStatus.OK, latency_ms=0
                )
            ],
        )

    async def fetch(self, url: str, *, max_chars: int = 50_000) -> FetchedDocument:
        record = _web_record(url)
        if record is None:
            raise ProviderFailure(
                ProviderError(
                    provider=FAKE_WEB_PROVIDER,
                    code="NOT_FOUND",
                    message=f"no canned page for {url}",
                    status_code=404,
                )
            )
        content = f"# {record.title}\n\n{record.abstract or ''}\n"
        return FetchedDocument(
            url=url,
            title=record.title,
            content=content[:max_chars],
            content_type="text/markdown",
            provider=FAKE_WEB_PROVIDER,
        )


def _result(item: ScoredRecord) -> SearchResult:
    record = item.record
    return SearchResult(
        title=record.title,
        url=record.url or record.external_id,
        snippet=record.abstract or "",
        published_at=str(record.year) if record.year else None,
        score=min(item.score, 1.0),
        provider=FAKE_WEB_PROVIDER,
    )


def _domain_allowed(record: CandidateRecord, request: WebSearchRequest) -> bool:
    host = urlsplit(record.url or record.external_id).hostname or ""

    def matches(domains: list[str]) -> bool:
        return any(host == domain or host.endswith(f".{domain}") for domain in domains)

    if request.include_domains and not matches(request.include_domains):
        return False
    return not matches(request.exclude_domains)


def _web_record(url: str) -> CandidateRecord | None:
    for candidate_set in canned_sets():
        for record in candidate_set.records:
            if record.origin is SourceOrigin.WEB and url in (record.url, record.external_id):
                return record
    return None


if TYPE_CHECKING:
    _web_search: WebSearch = FakeWebSearch()
