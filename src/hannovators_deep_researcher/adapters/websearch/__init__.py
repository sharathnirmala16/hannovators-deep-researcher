"""Web search provider adapters and the registry that builds them from settings."""

import logging
from collections.abc import Callable

from hannovators_deep_researcher.adapters.websearch.tavily import TavilyProvider
from hannovators_deep_researcher.configuration.settings import AUTO_WEB_SEARCH_PROVIDER, Settings
from hannovators_deep_researcher.models.ports import WebSearchProvider

logger = logging.getLogger(__name__)

PROVIDER_FACTORIES: dict[str, Callable[[Settings], WebSearchProvider]] = {
    TavilyProvider.name: TavilyProvider.from_settings,
}


def build_providers(settings: Settings) -> list[WebSearchProvider]:
    """Build every registered provider in WEB_SEARCH_PRIORITY order, with or without a key.

    A pinned WEB_SEARCH_PROVIDER outside the priority list is added last. Names without an
    adapter are skipped with a warning. The router decides what missing keys mean.
    """

    names = list(dict.fromkeys(settings.web_search_priority))
    pinned = settings.web_search_provider
    if pinned != AUTO_WEB_SEARCH_PROVIDER and pinned not in names:
        names.append(pinned)
    providers: list[WebSearchProvider] = []
    for name in names:
        factory = PROVIDER_FACTORIES.get(name)
        if factory is None:
            logger.warning("Web search provider %r has no adapter; skipping it", name)
            continue
        providers.append(factory(settings))
    return providers
