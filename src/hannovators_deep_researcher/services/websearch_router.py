"""Web search routing over `WebSearchProvider` adapters: auto, prefer, and require modes.

Implements the `WebSearch` port. Providers are tried in order through one `ResilientRunner`
(retries and a circuit per provider). Any `ProviderFailure` moves on to the next provider;
open-circuit providers are skipped. Every try is recorded in `WebSearchResponse.attempts`.
"""

import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from enum import StrEnum
from functools import partial

from hannovators_deep_researcher.configuration.settings import AUTO_WEB_SEARCH_PROVIDER, Settings
from hannovators_deep_researcher.infrastructure.resilience import CircuitOpenError, ResilientRunner
from hannovators_deep_researcher.models.enums import ProviderAttemptStatus
from hannovators_deep_researcher.models.ports import WebSearchProvider
from hannovators_deep_researcher.models.web import (
    FetchedDocument,
    ProviderAttempt,
    ProviderError,
    ProviderFailure,
    SearchResult,
    WebSearchRequest,
    WebSearchResponse,
)
from hannovators_deep_researcher.services.urls import canonicalize_url

logger = logging.getLogger(__name__)

ROUTER_PROVIDER_NAME = "web"


class WebSearchMode(StrEnum):
    AUTO = "auto"  # configured providers in priority order
    PREFER = "prefer"  # the named provider first, then the others in priority order
    REQUIRE = "require"  # only the named provider; no fallback


class WebSearchConfigError(RuntimeError):
    """Raised at startup when the providers cannot serve the configured mode."""


class WebSearchUnavailable(ProviderFailure):
    """Every provider in the chain failed or was skipped. `attempts` holds each reason."""

    def __init__(self, operation: str, attempts: Sequence[ProviderAttempt]) -> None:
        errors = [attempt.error for attempt in attempts if attempt.error is not None]
        reasons = "; ".join(f"{e.provider}: {e.code}: {e.message}" for e in errors)
        reasons = reasons or "no configured provider supports it"
        super().__init__(
            ProviderError(
                provider=ROUTER_PROVIDER_NAME,
                code="all_providers_failed",
                message=f"web {operation} failed: {reasons}",
                retryable=any(error.retryable for error in errors),
            )
        )
        self.attempts = list(attempts)


def _key_hint(name: str) -> str:
    return f"{name.upper()}_API_KEY"


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def _dedupe(results: Sequence[SearchResult]) -> list[SearchResult]:
    seen: set[str] = set()
    unique: list[SearchResult] = []
    for result in results:
        key = canonicalize_url(result.url)
        if key not in seen:
            seen.add(key)
            unique.append(result)
    return unique


class WebSearchRouter:
    """`WebSearch` port over provider adapters. Construction validates the configuration."""

    def __init__(
        self,
        providers: Sequence[WebSearchProvider],
        *,
        mode: WebSearchMode = WebSearchMode.AUTO,
        provider: str | None = None,
        runner: ResilientRunner | None = None,
    ) -> None:
        names = [p.name for p in providers]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate web search provider names: {names}")
        self._runner = runner or ResilientRunner()
        self._chain = self._resolve_chain(providers, mode, provider)
        logger.info("Web search %s chain: %s", mode, ", ".join(p.name for p in self._chain))

    @property
    def provider_names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self._chain)

    async def search(self, request: WebSearchRequest) -> WebSearchResponse:
        response, attempts = await self._route("search", self._chain, lambda p: p.search(request))
        return WebSearchResponse(
            query=request.query,
            results=_dedupe(response.results)[: request.limit],
            provider=response.provider,
            attempts=attempts,
        )

    async def fetch(self, url: str, *, max_chars: int = 50_000) -> FetchedDocument:
        chain = tuple(p for p in self._chain if p.supports_fetch)
        document, _ = await self._route("fetch", chain, lambda p: p.fetch(url, max_chars=max_chars))
        return document

    @staticmethod
    def _resolve_chain(
        providers: Sequence[WebSearchProvider], mode: WebSearchMode, name: str | None
    ) -> tuple[WebSearchProvider, ...]:
        if mode is WebSearchMode.AUTO:
            ordered = list(providers)
        else:
            if name is None:
                raise ValueError(f"web search mode {mode} needs a provider name")
            chosen = next((p for p in providers if p.name == name), None)
            if mode is WebSearchMode.REQUIRE:
                if chosen is None:
                    registered = ", ".join(p.name for p in providers) or "none"
                    raise WebSearchConfigError(
                        f"WEB_SEARCH_PROVIDER={name!r} has no adapter (registered: {registered})."
                    )
                if not chosen.is_configured():
                    raise WebSearchConfigError(
                        f"WEB_SEARCH_PROVIDER={name!r} is pinned, but {_key_hint(name)} is not "
                        "set. Set the key, or use WEB_SEARCH_PROVIDER=auto."
                    )
                return (chosen,)
            if chosen is None or not chosen.is_configured():
                logger.warning("Preferred web search provider %r is not available", name)
            ordered = [p for p in providers if p is chosen] + [
                p for p in providers if p is not chosen
            ]
        chain = tuple(p for p in ordered if p.is_configured())
        if not chain:
            hints = ", ".join(_key_hint(p.name) for p in providers) or "no adapter is registered"
            raise WebSearchConfigError(
                f"No web search provider is configured. Set one of: {hints}."
            )
        return chain

    async def _route[T](
        self,
        operation: str,
        chain: Sequence[WebSearchProvider],
        call: Callable[[WebSearchProvider], Awaitable[T]],
    ) -> tuple[T, list[ProviderAttempt]]:
        attempts: list[ProviderAttempt] = []
        for provider in chain:
            if self._runner.is_open(provider.name):
                skipped = CircuitOpenError(provider.name).error
                attempts.append(
                    ProviderAttempt(
                        provider=provider.name, status=ProviderAttemptStatus.SKIPPED, error=skipped
                    )
                )
                continue
            started = time.perf_counter()
            try:
                result = await self._runner.run(provider.name, partial(call, provider))
            except ProviderFailure as exc:
                logger.warning("Web %s via %s failed: %s", operation, provider.name, exc.error.code)
                attempts.append(
                    ProviderAttempt(
                        provider=provider.name,
                        status=ProviderAttemptStatus.FAILED,
                        latency_ms=_elapsed_ms(started),
                        error=exc.error,
                    )
                )
                continue
            attempts.append(
                ProviderAttempt(
                    provider=provider.name,
                    status=ProviderAttemptStatus.OK,
                    latency_ms=_elapsed_ms(started),
                )
            )
            return result, attempts
        raise WebSearchUnavailable(operation, attempts)


def create_web_search_router(
    settings: Settings,
    providers: Sequence[WebSearchProvider],
    *,
    runner: ResilientRunner | None = None,
) -> WebSearchRouter:
    """Map WEB_SEARCH_PROVIDER to a mode: `auto`, or one provider name pinned with REQUIRE."""

    if settings.web_search_provider == AUTO_WEB_SEARCH_PROVIDER:
        return WebSearchRouter(providers, runner=runner)
    return WebSearchRouter(
        providers,
        mode=WebSearchMode.REQUIRE,
        provider=settings.web_search_provider,
        runner=runner,
    )
