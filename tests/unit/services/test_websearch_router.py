"""Edge cases for web search routing: failover, total failure, and startup validation."""

from typing import Any

import httpx
import pytest
import respx
from pydantic import SecretStr

from hannovators_deep_researcher.adapters.websearch import build_providers
from hannovators_deep_researcher.adapters.websearch.tavily import TavilyProvider
from hannovators_deep_researcher.configuration.settings import Settings
from hannovators_deep_researcher.infrastructure.resilience import ResilientRunner
from hannovators_deep_researcher.models.enums import ProviderAttemptStatus
from hannovators_deep_researcher.models.ports import WebSearchProvider
from hannovators_deep_researcher.models.web import (
    FetchedDocument,
    ProviderError,
    ProviderFailure,
    SearchResult,
    WebSearchRequest,
    WebSearchResponse,
)
from hannovators_deep_researcher.services.websearch_router import (
    WebSearchConfigError,
    WebSearchRouter,
    WebSearchUnavailable,
    create_web_search_router,
)

pytestmark = pytest.mark.unit

FAILED = ProviderAttemptStatus.FAILED
OK = ProviderAttemptStatus.OK


class StubProvider:
    """In-test `WebSearchProvider` double that answers with fixed URLs or one error."""

    supports_fetch = False

    def __init__(
        self, name: str, *, urls: tuple[str, ...] = (), error: ProviderError | None = None
    ) -> None:
        self.name = name
        self._urls = urls
        self._error = error

    def is_configured(self) -> bool:
        return True

    async def search(self, request: WebSearchRequest) -> WebSearchResponse:
        if self._error is not None:
            raise ProviderFailure(self._error)
        results = [SearchResult(title=url, url=url, provider=self.name) for url in self._urls]
        return WebSearchResponse(query=request.query, results=results, provider=self.name)

    async def fetch(self, url: str, *, max_chars: int) -> FetchedDocument:
        raise AssertionError("fetch is not used in these tests")


async def _no_sleep(_: float) -> None:
    return None


def _settings(**overrides: Any) -> Settings:
    """Settings with every web search key unset, whatever the environment or `.env` holds."""

    values = {"tavily_api_key": None, "exa_api_key": None, "web_search_priority": ("tavily", "exa")}
    return Settings.model_validate(values | overrides)


async def test_primary_rate_limit_fails_over_and_attempts_list_both(
    respx_mock: respx.MockRouter,
) -> None:
    tavily_route = respx_mock.post("https://api.tavily.com/search").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, json={"detail": {}})
    )
    tavily = TavilyProvider(SecretStr("tvly-test"))
    backup = StubProvider(
        "backup",
        urls=(
            "https://www.example.com/a?utm_source=news",
            "http://example.com/a/#top",
            "https://example.com/b",
        ),
    )
    router = WebSearchRouter([tavily, backup], runner=ResilientRunner(sleeper=_no_sleep))

    try:
        response = await router.search(WebSearchRequest(query="aspirin"))
    finally:
        await tavily.aclose()

    assert response.provider == "backup"
    assert [(a.provider, a.status) for a in response.attempts] == [
        ("tavily", FAILED),
        ("backup", OK),
    ]
    primary_error = response.attempts[0].error
    assert primary_error is not None
    assert (primary_error.code, primary_error.status_code) == ("rate_limited", 429)
    assert tavily_route.call_count == 3
    assert [r.url for r in response.results] == [
        "https://www.example.com/a?utm_source=news",
        "https://example.com/b",
    ]


async def test_all_providers_fail_raises_one_error_with_each_reason() -> None:
    router = WebSearchRouter(
        [
            StubProvider(
                "alpha",
                error=ProviderError(
                    provider="alpha", code="http_error", message="HTTP 503", retryable=True
                ),
            ),
            StubProvider(
                "beta",
                error=ProviderError(provider="beta", code="invalid_api_key", message="HTTP 401"),
            ),
        ],
        runner=ResilientRunner(sleeper=_no_sleep),
    )

    with pytest.raises(WebSearchUnavailable) as caught:
        await router.search(WebSearchRequest(query="aspirin"))

    assert [(a.provider, a.status) for a in caught.value.attempts] == [
        ("alpha", FAILED),
        ("beta", FAILED),
    ]
    assert "alpha: http_error: HTTP 503" in caught.value.error.message
    assert "beta: invalid_api_key: HTTP 401" in caught.value.error.message


def test_no_configured_provider_fails_at_startup() -> None:
    settings = _settings(web_search_provider="auto")

    with pytest.raises(WebSearchConfigError, match="No web search provider is configured"):
        create_web_search_router(settings, build_providers(settings))


def test_pinned_provider_without_key_errors_instead_of_falling_back() -> None:
    settings = _settings(web_search_provider="tavily")
    providers: list[WebSearchProvider] = [
        *build_providers(settings),
        StubProvider("backup", urls=("https://example.com/",)),
    ]

    with pytest.raises(WebSearchConfigError, match="TAVILY_API_KEY is not set"):
        create_web_search_router(settings, providers)
