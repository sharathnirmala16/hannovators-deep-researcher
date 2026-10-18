"""Live Tavily checks. One small request each; skipped when TAVILY_API_KEY is missing."""

import pytest

from hannovators_deep_researcher.adapters.websearch import build_providers
from hannovators_deep_researcher.adapters.websearch.tavily import TavilyProvider
from hannovators_deep_researcher.configuration.settings import Settings, get_settings
from hannovators_deep_researcher.models.web import WebSearchRequest
from hannovators_deep_researcher.services.websearch_router import create_web_search_router

pytestmark = pytest.mark.live


@pytest.fixture
def settings() -> Settings:
    settings = get_settings()
    if settings.tavily_api_key is None:
        pytest.skip("TAVILY_API_KEY is not set")
    return settings


async def test_tavily_search(settings: Settings) -> None:
    provider = TavilyProvider.from_settings(settings)
    try:
        response = await provider.search(
            WebSearchRequest(query="aspirin primary prevention", limit=3)
        )
    finally:
        await provider.aclose()

    assert 1 <= len(response.results) <= 3
    assert all(result.url.startswith("http") for result in response.results)


async def test_tavily_extract(settings: Settings) -> None:
    provider = TavilyProvider.from_settings(settings)
    try:
        document = await provider.fetch("https://example.com/", max_chars=2_000)
    finally:
        await provider.aclose()

    assert document.content.strip()
    assert len(document.content) <= 2_000


async def test_auto_mode_picks_tavily(settings: Settings) -> None:
    auto = settings.model_copy(update={"web_search_provider": "auto"})
    providers = build_providers(auto)
    router = create_web_search_router(auto, providers)
    try:
        response = await router.search(WebSearchRequest(query="evidence synthesis", limit=1))
    finally:
        for provider in providers:
            if isinstance(provider, TavilyProvider):
                await provider.aclose()

    assert response.provider == "tavily"
    assert response.attempts[0].provider == "tavily"
