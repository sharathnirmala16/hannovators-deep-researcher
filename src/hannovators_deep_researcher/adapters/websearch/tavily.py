"""Tavily search and extract through the official `tavily-python` async SDK.

Slim port of the freesearch adapter: no quota, PAYGO, usage, or keyless bookkeeping. A response
hook records the HTTP status and `Retry-After` before the SDK turns the response into an
exception, because the SDK drops both.
"""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from typing import Any, Self

import httpx
from pydantic import SecretStr, ValidationError
from tavily import AsyncTavilyClient  # type: ignore[import-untyped]
from tavily.errors import (  # type: ignore[import-untyped]
    BadRequestError,
    ForbiddenError,
    InvalidAPIKeyError,
    UsageLimitExceededError,
)
from tavily.errors import TimeoutError as TavilyTimeoutError

from hannovators_deep_researcher.configuration.settings import Settings
from hannovators_deep_researcher.infrastructure.http import create_http_client
from hannovators_deep_researcher.infrastructure.resilience import (
    RETRYABLE_STATUS_CODES,
    RateLimited,
    parse_retry_after,
)
from hannovators_deep_researcher.models.web import (
    FetchedDocument,
    ProviderError,
    ProviderFailure,
    SearchResult,
    WebSearchRequest,
    WebSearchResponse,
)

_NAME = "tavily"
_BASE_URL = "https://api.tavily.com"
_MAX_RESULTS = 20
_DEFAULT_TIMEOUT = 30.0
_STATUS_CODES = {
    400: "bad_request",
    401: "invalid_api_key",
    403: "forbidden",
    432: "quota_exhausted",
    433: "quota_exhausted",
}
_EXCEPTION_STATUS: tuple[tuple[type[Exception], int], ...] = (
    (UsageLimitExceededError, 429),
    (InvalidAPIKeyError, 401),
    (ForbiddenError, 403),
    (BadRequestError, 400),
)

_last_response: ContextVar[tuple[int, float | None] | None] = ContextVar(
    "tavily_last_response", default=None
)


async def _record_response(response: httpx.Response) -> None:
    _last_response.set(
        (response.status_code, parse_retry_after(response.headers.get("retry-after")))
    )


def _error_status(exc: Exception) -> tuple[int | None, float | None]:
    recorded = _last_response.get()
    if recorded is not None and recorded[0] >= 400:
        return recorded
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code, None
    for exc_type, status in _EXCEPTION_STATUS:
        if isinstance(exc, exc_type):
            return status, None
    return None, None


def _score(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if 0 <= value <= 1 else None


def _result(item: dict[str, Any]) -> SearchResult:
    published = item.get("published_date")
    return SearchResult(
        title=str(item.get("title") or ""),
        url=str(item["url"]),
        snippet=str(item.get("content") or ""),
        published_at=str(published) if published else None,
        score=_score(item.get("score")),
        provider=_NAME,
    )


class TavilyProvider:
    """`WebSearchProvider` for Tavily. The SDK client is built on first use."""

    name: str = _NAME
    supports_fetch: bool = True

    def __init__(self, api_key: SecretStr | None, *, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._http: httpx.AsyncClient | None = None
        self._sdk: AsyncTavilyClient | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        return cls(settings.tavily_api_key)

    def is_configured(self) -> bool:
        return self._api_key is not None

    async def search(self, request: WebSearchRequest) -> WebSearchResponse:
        kwargs: dict[str, Any] = {
            "query": request.query,
            "max_results": min(request.limit, _MAX_RESULTS),
            "search_depth": "basic",
            "timeout": self._timeout,
        }
        if request.include_domains:
            kwargs["include_domains"] = request.include_domains
        if request.exclude_domains:
            kwargs["exclude_domains"] = request.exclude_domains
        if request.days is not None:
            start = datetime.now(UTC).date() - timedelta(days=request.days)
            kwargs["start_date"] = start.isoformat()
        payload = await self._call(lambda sdk: sdk.search(**kwargs))
        try:
            results = [_result(item) for item in payload.get("results") or []]
        except (AttributeError, KeyError, TypeError, ValidationError) as exc:
            raise self._failure("invalid_response", "malformed search response") from exc
        return WebSearchResponse(query=request.query, results=results, provider=self.name)

    async def fetch(self, url: str, *, max_chars: int) -> FetchedDocument:
        payload = await self._call(
            lambda sdk: sdk.extract(
                urls=[url], format="markdown", extract_depth="basic", timeout=self._timeout
            )
        )
        try:
            results = payload.get("results") or []
            if not results:
                failed = payload.get("failed_results") or [{}]
                reason = str(failed[0].get("error") or "no content returned")
                raise self._failure("fetch_failed", f"extract failed: {reason}")
            item = results[0]
            content = item["raw_content"]
            if not isinstance(content, str):
                raise TypeError("raw_content is not a string")
            return FetchedDocument(
                url=url,
                title=item.get("title") or None,
                content=content[:max_chars],
                content_type="text/markdown",
                provider=self.name,
            )
        except (AttributeError, IndexError, KeyError, TypeError, ValidationError) as exc:
            raise self._failure("invalid_response", "malformed extract response") from exc

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http, self._sdk = None, None

    def _client(self) -> AsyncTavilyClient:
        if self._api_key is None:
            raise self._failure("not_configured", "TAVILY_API_KEY is not set")
        if self._sdk is None:
            self._http = create_http_client(base_url=_BASE_URL, timeout=self._timeout)
            self._http.event_hooks = {"request": [], "response": [_record_response]}
            self._sdk = AsyncTavilyClient(
                api_key=self._api_key.get_secret_value(), client=self._http
            )
        return self._sdk

    async def _call(
        self, operation: Callable[[AsyncTavilyClient], Awaitable[Any]]
    ) -> dict[str, Any]:
        sdk = self._client()
        _last_response.set(None)
        try:
            payload = await operation(sdk)
        except Exception as exc:
            raise self._map_error(exc) from exc
        if not isinstance(payload, dict):
            raise self._failure("invalid_response", "response is not a JSON object")
        return payload

    def _map_error(self, exc: Exception) -> ProviderFailure:
        status, retry_after = _error_status(exc)
        if status == 429:
            error = self._error("rate_limited", "rate or usage limit reached", True, 429)
            return RateLimited(error, retry_after=retry_after)
        if isinstance(exc, TavilyTimeoutError | httpx.TimeoutException):
            return self._failure("timeout", "request timed out", retryable=True)
        if isinstance(exc, httpx.TransportError):
            return self._failure("transport_error", type(exc).__name__, retryable=True)
        if status is not None:
            return self._failure(
                _STATUS_CODES.get(status, "http_error"),
                f"HTTP {status}",
                retryable=status in RETRYABLE_STATUS_CODES,
                status=status,
            )
        return self._failure("tavily_error", type(exc).__name__)

    def _error(
        self, code: str, message: str, retryable: bool = False, status: int | None = None
    ) -> ProviderError:
        return ProviderError(
            provider=self.name,
            code=code,
            message=message,
            retryable=retryable,
            status_code=status,
        )

    def _failure(
        self, code: str, message: str, *, retryable: bool = False, status: int | None = None
    ) -> ProviderFailure:
        return ProviderFailure(self._error(code, message, retryable, status))
