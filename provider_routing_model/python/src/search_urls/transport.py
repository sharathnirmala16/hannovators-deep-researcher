"""One-shot HTTP JSON transport, shared limits, and durable request attempts."""

from __future__ import annotations

import asyncio
import email.utils
import re
import time
from collections import deque
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, runtime_checkable

import httpx
from pydantic import JsonValue

from search_urls.models import ProviderName

_SENSITIVE_KEYS = frozenset(
    {
        "apikey",
        "accesskey",
        "accesstoken",
        "authorization",
        "credential",
        "credentials",
        "key",
        "password",
        "pi_key",
        "pikey",
        "secret",
        "signature",
        "token",
    }
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")


class SearchProviderError(Exception):
    """Safe provider error shared by adapters, transport, and the runner."""

    def __init__(
        self,
        provider: str,
        code: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
        retry_after_seconds: float | None = None,
        observation: AttemptObservation | None = None,
    ) -> None:
        self.provider = provider
        self.code = code
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.observation = observation
        super().__init__(f"{provider} search failed ({code})")


@dataclass(frozen=True, slots=True)
class AttemptObservation:
    """Allowlisted telemetry observed at the physical HTTP boundary."""

    http_status: int | None
    latency_ms: int
    reported_usd: str | None = None
    estimated_usd: str | None = None
    source: str = "unknown"
    native_usage: JsonValue | None = None
    price_snapshot: JsonValue | None = None
    request_id: str | None = None


class ObservedPayload(dict[str, object]):
    """Native JSON object with out-of-band transport observations."""

    def __init__(self, value: dict[str, object], observation: AttemptObservation) -> None:
        super().__init__(value)
        self.observation = observation


def observation_for(payload: object) -> AttemptObservation | None:
    """Return response telemetry attached by the shared HTTP transport."""
    result = getattr(payload, "observation", None)
    return result if isinstance(result, AttemptObservation) else None


@dataclass(frozen=True, slots=True)
class AttemptContext:
    """Case and retry identity attached to every physical dispatch."""

    case_id: str
    repetition: int
    retry: int
    provider: ProviderName
    request_cap: int
    deadline: float | None = None
    initial_request_count: int = 0


class AttemptJournal(Protocol):
    """Durable hooks implemented by the append-only run store."""

    def begin_attempt(
        self,
        context: AttemptContext,
        method: str,
        url: str,
        *,
        queue_latency_ms: int = 0,
    ) -> str: ...

    def finish_attempt(
        self,
        attempt_id: str,
        *,
        status: str,
        http_status: int | None = None,
        error_code: str | None = None,
        latency_ms: int | None = None,
        reported_usd: str | None = None,
        estimated_usd: str | None = None,
        source: str = "unknown",
        native_usage: object = None,
        price_snapshot: object = None,
        request_id: str | None = None,
    ) -> None: ...


@runtime_checkable
class SearchTransport(Protocol):
    """Adapter-facing one-request interface; request implementations never retry."""

    attempt_ids: list[str]

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str | int | float | bool | None] | None = None,
        json: Any = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]: ...

    def for_query(
        self,
        case_id: str,
        repetition: int,
        retry: int,
        request_cap: int,
        deadline: float | None = None,
        initial_request_count: int = 0,
    ) -> SearchTransport: ...

    def finish_query(self, status: str, error_code: str | None = None) -> None: ...


class HttpxJsonTransport:
    """Caller-owned HTTPX client with retries/redirects disabled and shared limits."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        provider: ProviderName,
        *,
        journal: AttemptJournal | None = None,
        request_timeout_ms: int = 30_000,
        rate_limits: Sequence[tuple[int, int]] = ((10, 60_000),),
        max_concurrency: int = 1,
    ) -> None:
        if request_timeout_ms < 1 or max_concurrency < 1:
            raise ValueError("transport limits must be positive")
        if any(requests < 1 or window_ms < 1 for requests, window_ms in rate_limits):
            raise ValueError("rate limits must be positive")
        self._client = client
        self.provider = provider
        self._journal = journal
        self._request_timeout_ms = request_timeout_ms
        self._rate_limits = tuple(
            (requests, window_ms / 1000) for requests, window_ms in rate_limits
        )
        self._rate_events = [deque[float]() for _ in self._rate_limits]
        self._rate_lock = asyncio.Lock()
        self._cooldown_until = 0.0
        self._concurrency = asyncio.Semaphore(max_concurrency)
        self._budgets: dict[tuple[str, int], _RequestBudget] = {}

    def for_query(
        self,
        case_id: str,
        repetition: int,
        retry: int,
        request_cap: int,
        deadline: float | None = None,
        initial_request_count: int = 0,
    ) -> SearchTransport:
        if self._journal is None:
            raise RuntimeError("attempt journal is required for a query-scoped transport")
        if request_cap < 0 or initial_request_count < 0:
            raise ValueError("request counts must not be negative")
        key = (case_id, repetition)
        budget = self._budgets.get(key)
        if budget is None:
            budget = _RequestBudget(used=initial_request_count, cap=request_cap)
            self._budgets[key] = budget
        else:
            budget.cap = min(budget.cap, request_cap)
            budget.used = max(budget.used, initial_request_count)
        context = AttemptContext(
            case_id=case_id,
            repetition=repetition,
            retry=retry,
            provider=self.provider,
            request_cap=request_cap,
            deadline=deadline,
            initial_request_count=initial_request_count,
        )
        return _ScopedTransport(self, self._journal, context, budget)

    async def _admit(self, deadline: float | None) -> None:
        try:
            if deadline is None:
                await self._concurrency.acquire()
            else:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                await asyncio.wait_for(self._concurrency.acquire(), timeout=remaining)
        except TimeoutError:
            raise SearchProviderError(self.provider, "query_timeout", retryable=True) from None
        try:
            async with self._rate_lock:
                while True:
                    now = time.monotonic()
                    if deadline is not None and now >= deadline:
                        raise SearchProviderError(self.provider, "query_timeout", retryable=True)
                    wait_seconds = 0.0
                    for (requests, window), events in zip(
                        self._rate_limits, self._rate_events, strict=True
                    ):
                        while events and events[0] <= now - window:
                            events.popleft()
                        if len(events) >= requests:
                            wait_seconds = max(wait_seconds, events[0] + window - now)
                    wait_seconds = max(wait_seconds, self._cooldown_until - now)
                    if wait_seconds <= 0:
                        admission_time = time.monotonic()
                        for events in self._rate_events:
                            events.append(admission_time)
                        return
                    if deadline is not None and now + wait_seconds >= deadline:
                        raise SearchProviderError(self.provider, "query_timeout", retryable=True)
                    await asyncio.sleep(wait_seconds)
        except BaseException:
            self._concurrency.release()
            raise

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str | int | float | bool | None] | None = None,
        json: Any = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        """Dispatch exactly once and return only native JSON object payloads."""
        started = time.perf_counter()
        try:
            response = await self._client.request(
                method,
                url,
                headers=dict(headers or {}),
                params=dict(params or {}),
                json=json,
                timeout=(
                    timeout_seconds
                    if timeout_seconds is not None
                    else self._request_timeout_ms / 1000
                ),
                follow_redirects=False,
                auth=None,
            )
        except httpx.TimeoutException:
            latency_ms = max(0, round((time.perf_counter() - started) * 1000))
            raise SearchProviderError(
                self.provider,
                "timeout",
                retryable=True,
                observation=AttemptObservation(None, latency_ms),
            ) from None
        except httpx.TransportError:
            latency_ms = max(0, round((time.perf_counter() - started) * 1000))
            raise SearchProviderError(
                self.provider,
                "network_error",
                retryable=True,
                observation=AttemptObservation(None, latency_ms),
            ) from None

        latency_ms = max(0, round((time.perf_counter() - started) * 1000))
        raw_payload: object = None
        with suppress(ValueError, UnicodeDecodeError):
            raw_payload = response.json()
        observation = _extract_observation(
            raw_payload,
            status=response.status_code,
            latency_ms=latency_ms,
            headers=response.headers,
        )
        if not 200 <= response.status_code < 300:
            retryable = response.status_code in {408, 425, 429} or response.status_code >= 500
            code = "rate_limited" if response.status_code == 429 else "http_error"
            raise SearchProviderError(
                self.provider,
                code,
                status_code=response.status_code,
                retryable=retryable,
                retry_after_seconds=_retry_after_seconds(response.headers.get("retry-after")),
                observation=observation,
            )
        if not isinstance(raw_payload, dict):
            raise SearchProviderError(
                self.provider,
                "invalid_response",
                status_code=response.status_code,
                observation=observation,
            )
        return ObservedPayload(raw_payload, observation)


@dataclass(slots=True)
class _RequestBudget:
    used: int
    cap: int
    pending: int = 0
    lock: asyncio.Lock | None = None

    def __post_init__(self) -> None:
        self.lock = asyncio.Lock()


class _ScopedTransport:
    def __init__(
        self,
        inner: HttpxJsonTransport,
        journal: AttemptJournal,
        context: AttemptContext,
        budget: _RequestBudget,
    ) -> None:
        self._inner = inner
        self._journal = journal
        self.context = context
        self._budget = budget
        self.attempt_ids: list[str] = []
        self._pending: dict[str, AttemptObservation | None] = {}

    def for_query(
        self,
        case_id: str,
        repetition: int,
        retry: int,
        request_cap: int,
        deadline: float | None = None,
        initial_request_count: int = 0,
    ) -> SearchTransport:
        return self._inner.for_query(
            case_id,
            repetition,
            retry,
            request_cap,
            deadline,
            initial_request_count,
        )

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str | int | float | bool | None] | None = None,
        json: Any = None,
        timeout_seconds: float | None = None,
    ) -> dict[str, object]:
        queued_at = time.monotonic()
        assert self._budget.lock is not None
        async with self._budget.lock:
            if self._budget.used + self._budget.pending >= self._budget.cap:
                raise SearchProviderError(self.context.provider, "request_limit", retryable=False)
            self._budget.pending += 1
        reserved = True
        try:
            await self._inner._admit(self.context.deadline)
        except BaseException:
            async with self._budget.lock:
                self._budget.pending -= 1
            raise
        try:
            remaining = (
                self.context.deadline - time.monotonic()
                if self.context.deadline is not None
                else None
            )
            if remaining is not None and remaining <= 0:
                raise SearchProviderError(self.context.provider, "query_timeout", retryable=True)
            async with self._budget.lock:
                self._budget.pending -= 1
                reserved = False
                self._budget.used += 1
            queue_latency_ms = max(0, round((time.monotonic() - queued_at) * 1000))
            attempt_id = self._journal.begin_attempt(
                self.context, method, url, queue_latency_ms=queue_latency_ms
            )
            self.attempt_ids.append(attempt_id)
            request_timeout = timeout_seconds or self._inner._request_timeout_ms / 1000
            if remaining is not None:
                request_timeout = min(request_timeout, remaining)
            request_started = time.perf_counter()
            try:
                payload = await self._inner.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                    timeout_seconds=request_timeout,
                )
            except SearchProviderError as error:
                observation = error.observation
                latency_ms = (
                    observation.latency_ms
                    if observation is not None
                    else max(0, round((time.perf_counter() - request_started) * 1000))
                )
                self._finish(
                    attempt_id,
                    status="error",
                    http_status=error.status_code
                    if error.status_code is not None
                    else observation.http_status
                    if observation is not None
                    else None,
                    error_code=error.code,
                    observation=observation,
                    latency_ms=latency_ms,
                )
                if error.retry_after_seconds is not None:
                    self._inner._cooldown_until = max(
                        self._inner._cooldown_until,
                        time.monotonic() + error.retry_after_seconds,
                    )
                raise
            except asyncio.CancelledError:
                self._finish(
                    attempt_id,
                    status="cancelled",
                    error_code="cancelled",
                    latency_ms=max(0, round((time.perf_counter() - request_started) * 1000)),
                )
                raise
            except BaseException:
                self._finish(
                    attempt_id,
                    status="error",
                    error_code="internal_error",
                    latency_ms=max(0, round((time.perf_counter() - request_started) * 1000)),
                )
                raise
            self._pending[attempt_id] = observation_for(payload)
            return payload
        finally:
            if reserved:
                async with self._budget.lock:
                    self._budget.pending -= 1
            self._inner._concurrency.release()

    def finish_query(self, status: str, error_code: str | None = None) -> None:
        """Finalize successful HTTP responses after adapter-level validation."""
        if status not in {"success", "error", "cancelled"}:
            raise ValueError("invalid query outcome")
        for attempt_id, observation in list(self._pending.items()):
            self._finish(
                attempt_id,
                status=status,
                http_status=observation.http_status if observation is not None else None,
                error_code=error_code,
                observation=observation,
                latency_ms=observation.latency_ms if observation is not None else None,
            )
            del self._pending[attempt_id]

    def _finish(
        self,
        attempt_id: str,
        *,
        status: str,
        http_status: int | None = None,
        error_code: str | None = None,
        observation: AttemptObservation | None = None,
        latency_ms: int | None = None,
    ) -> None:
        self._journal.finish_attempt(
            attempt_id,
            status=status,
            http_status=http_status,
            error_code=error_code,
            latency_ms=latency_ms,
            reported_usd=observation.reported_usd if observation is not None else None,
            estimated_usd=observation.estimated_usd if observation is not None else None,
            source=observation.source if observation is not None else "unknown",
            native_usage=observation.native_usage if observation is not None else None,
            price_snapshot=observation.price_snapshot if observation is not None else None,
            request_id=observation.request_id if observation is not None else None,
        )


def _extract_observation(
    payload: object,
    *,
    status: int,
    latency_ms: int,
    headers: httpx.Headers,
) -> AttemptObservation:
    data = payload if isinstance(payload, dict) else {}
    usage_fields = {
        key: data[key]
        for key in (
            "usage",
            "costDollars",
            "cost_dollars",
            "credits_used",
            "creditsUsed",
            "units_used",
            "unitsUsed",
        )
        if key in data
    }
    metadata = data.get("_meta")
    if isinstance(metadata, dict) and "keenable/usage" in metadata:
        usage_fields["keenable/usage"] = metadata["keenable/usage"]
    native_usage = _safe_json(usage_fields) if usage_fields else None

    price_raw = data.get("priceSnapshot", data.get("price_snapshot", data.get("pricing")))
    price_snapshot = _safe_json(price_raw) if price_raw is not None else None
    reported = _usd_value(
        data.get("reportedUsd", data.get("reported_usd", data.get("costUsd", data.get("cost_usd"))))
    )
    estimated = _usd_value(data.get("estimatedUsd", data.get("estimated_usd")))
    if price_raw is None:
        estimated = None
    cost_dollars = data.get("costDollars", data.get("cost_dollars"))
    if reported is None and isinstance(cost_dollars, dict):
        reported = _usd_value(cost_dollars.get("total"))
    if reported is not None:
        source = "reported"
    elif estimated is not None:
        source = "estimated"
    else:
        source = "unknown"
    request_id = data.get("requestId", data.get("request_id"))
    if not isinstance(request_id, str) or not _SAFE_ID.fullmatch(request_id):
        request_id = next(
            (
                headers.get(key)
                for key in ("x-request-id", "request-id", "x-correlation-id")
                if headers.get(key) and _SAFE_ID.fullmatch(headers[key] or "")
            ),
            None,
        )
    return AttemptObservation(
        http_status=status,
        latency_ms=latency_ms,
        reported_usd=reported,
        estimated_usd=estimated,
        source=source,
        native_usage=native_usage,
        price_snapshot=price_snapshot,
        request_id=request_id,
    )


def _usd_value(value: object) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0:
        return None
    return str(parsed)


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            retry_at = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        seconds = (retry_at.astimezone(UTC) - datetime.now(UTC)).total_seconds()
    return max(0.0, seconds) if seconds >= 0 else 0.0


def _safe_json(value: object, *, depth: int = 0) -> JsonValue:
    if depth >= 12:
        return "[truncated]"
    if isinstance(value, dict):
        return {
            str(key): _safe_json(item, depth=depth + 1)
            for key, item in value.items()
            if not _sensitive_key(str(key))
        }
    if isinstance(value, list):
        return [_safe_json(item, depth=depth + 1) for item in value]
    if isinstance(value, str):
        safe = re.sub(
            r"(?i)(api[_-]?key|access[_-]?token|authorization|credential|password|secret|signature|pi[_-]?key|token)\s*[:=]\s*[^&\s,;]+",
            r"\1=[REDACTED]",
            value[:20_000],
        )
        if safe.startswith(("http://", "https://")):
            from urllib.parse import parse_qsl, urlsplit

            try:
                parsed = urlsplit(safe)
                if (
                    parsed.username is not None
                    or parsed.password is not None
                    or any(_sensitive_key(key) for key, _ in parse_qsl(parsed.query))
                    or any(_sensitive_key(key) for key, _ in parse_qsl(parsed.fragment))
                ):
                    return "[redacted-url]"
            except ValueError:
                return "[redacted-url]"
        return safe
    if value is None or isinstance(value, (int, float, bool)):
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            return "[non-finite]"
        return value
    if isinstance(value, Decimal):
        return str(value) if value.is_finite() else "[non-finite]"
    return str(value)[:20_000]


def _sensitive_key(key: str) -> bool:
    normalized = key.casefold().replace("_", "").replace("-", "")
    sensitive_suffixes = (
        "apikey",
        "accesskey",
        "accesstoken",
        "authorization",
        "credential",
        "password",
        "secret",
        "signature",
        "token",
    )
    return normalized in _SENSITIVE_KEYS or normalized.endswith(sensitive_suffixes)


def utc_now_iso() -> str:
    """Return a UTC timestamp suitable for JSONL records."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
