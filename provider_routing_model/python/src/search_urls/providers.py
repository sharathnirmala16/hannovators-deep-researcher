"""Search provider construction and environment-backed credential resolution."""

from __future__ import annotations

import os
from typing import Protocol

from search_urls.configuration import SearchConfig
from search_urls.models import SearchResponse
from search_urls.providers_primary import BraveAdapter, ExaAdapter, FirecrawlAdapter, TavilyAdapter
from search_urls.providers_secondary import (
    KeenableAdapter,
    ParallelAdapter,
    TinyfishAdapter,
    YouAdapter,
)
from search_urls.transport import SearchTransport

__all__ = ["SearchAdapter", "create_adapter"]

_API_KEY_ENV: dict[str, tuple[str, ...]] = {
    "brave": ("BRAVE_API_KEY", "BRAVE_SEARCH_API_KEY", "FREESEARCH_BRAVE_SEARCH_API_KEY"),
    "exa": ("EXA_API_KEY", "FREESEARCH_EXA_API_KEY"),
    "firecrawl": ("FIRECRAWL_API_KEY", "FREESEARCH_FIRECRAWL_API_KEY"),
    "keenable": ("KEENABLE_API_KEY", "FREESEARCH_KEENABLE_API_KEY"),
    "parallel": ("PARALLEL_API_KEY", "FREESEARCH_PARALLEL_API_KEY"),
    "tavily": ("TAVILY_API_KEY", "FREESEARCH_TAVILY_API_KEY"),
    "tinyfish": ("TINYFISH_API_KEY", "FREESEARCH_TINYFISH_API_KEY"),
    "you": ("YOU_API_KEY", "YOUCOM_API_KEY", "YDC_API_KEY", "FREESEARCH_YOU_API_KEY"),
}


class SearchAdapter(Protocol):
    """Adapter contract consumed by the direct-search runner."""

    async def search(self, query: str, transport: SearchTransport) -> SearchResponse: ...


def create_adapter(config: SearchConfig, key: str | None = None) -> SearchAdapter:
    """Construct one provider adapter and resolve its key from the process environment."""
    api_key = _resolve_key(config.provider, key)
    if config.provider == "brave":
        return BraveAdapter(config, api_key)
    if config.provider == "exa":
        return ExaAdapter(config, api_key)
    if config.provider == "firecrawl":
        return FirecrawlAdapter(config, api_key)
    if config.provider == "keenable":
        return KeenableAdapter(config, api_key)
    if config.provider == "parallel":
        return ParallelAdapter(config, api_key)
    if config.provider == "tavily":
        return TavilyAdapter(config, api_key)
    if config.provider == "tinyfish":
        return TinyfishAdapter(config, api_key)
    if config.provider == "you":
        return YouAdapter(config, api_key)
    raise ValueError("unsupported search provider")


def _resolve_key(provider: str, explicit: str | None) -> str | None:
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    for name in _API_KEY_ENV[provider]:
        value = os.environ.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
