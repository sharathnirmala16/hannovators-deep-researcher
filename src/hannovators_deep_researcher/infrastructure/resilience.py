"""Retry, Retry-After, and per-provider circuit breaking for provider operations.

Slim port of the freesearch `ResilientRunner`. Operations raise `ProviderFailure`; the runner
retries the retryable ones and `httpx.TransportError`, and fails fast while a provider's circuit
is open. No provider, routing, or configuration logic lives here.
"""

import asyncio
import email.utils
import math
import random
import time
from collections.abc import Awaitable, Callable
from typing import Literal

import httpx

from hannovators_deep_researcher.models.web import ProviderError, ProviderFailure

RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


class RateLimited(ProviderFailure):
    """A retryable failure that carries the provider's `Retry-After` delay in seconds."""

    def __init__(self, error: ProviderError, *, retry_after: float | None) -> None:
        super().__init__(error)
        self.retry_after = retry_after


class CircuitOpenError(ProviderFailure):
    """Raised without calling the provider while its circuit is open."""

    def __init__(self, provider: str) -> None:
        super().__init__(
            ProviderError(
                provider=provider,
                code="circuit_open",
                message="circuit is open; operation not attempted",
            )
        )


def parse_retry_after(
    value: str | None, *, wall_clock: Callable[[], float] = time.time
) -> float | None:
    """Parse `Retry-After` (seconds or HTTP-date) into seconds; malformed values give None."""

    raw = (value or "").strip()
    if not raw:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        pass
    else:
        return seconds if math.isfinite(seconds) and seconds >= 0 else None
    try:
        retry_at = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return max(0.0, retry_at.timestamp() - wall_clock())


class _CircuitBreaker:
    """Closed -> open after `threshold` failed runs -> one half-open probe after `cooldown`.

    Methods never await, so asyncio needs no lock around the state.
    """

    def __init__(self, *, threshold: int, cooldown: float) -> None:
        self._threshold = threshold
        self._cooldown = cooldown
        self._state: Literal["closed", "open", "half_open"] = "closed"
        self._failures = 0
        self._opened_at = 0.0
        self._probe_in_flight = False

    def is_open(self, now: float) -> bool:
        if self._state == "open":
            return now < self._opened_at + self._cooldown
        return self._state == "half_open" and self._probe_in_flight

    def admit(self, provider: str, now: float) -> bool:
        """Allow a run or raise `CircuitOpenError`. Returns True when the run is the probe."""

        if self._state == "open":
            if now < self._opened_at + self._cooldown:
                raise CircuitOpenError(provider)
            self._state = "half_open"
        if self._state == "half_open":
            if self._probe_in_flight:
                raise CircuitOpenError(provider)
            self._probe_in_flight = True
            return True
        return False

    def record(self, *, healthy: bool, now: float) -> None:
        """A success or a definitive answer closes the circuit; failures count toward opening."""

        if healthy:
            self._state, self._failures = "closed", 0
            return
        self._failures += 1
        if self._state == "half_open" or self._failures >= self._threshold:
            self._state, self._failures, self._opened_at = "open", 0, now

    def release(self, holds_probe: bool) -> None:
        if holds_probe:
            self._probe_in_flight = False


class ResilientRunner:
    """Run provider operations with retries, `Retry-After`, and a circuit per provider.

    Usage: `await runner.run("tavily", lambda: provider.search(request))`.

    A `Retry-After` longer than `max_delay` stops the retries at once, so a router can fail
    over instead of stalling. `clock`, `sleeper`, and `random_source` are test seams.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
        backoff_factor: float = 2.0,
        circuit_failure_threshold: int = 5,
        circuit_cooldown: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random_source: Callable[[], float] = random.random,
    ) -> None:
        if max_attempts < 1 or circuit_failure_threshold < 1:
            raise ValueError("max_attempts and circuit_failure_threshold must be at least 1")
        if min(base_delay, max_delay, circuit_cooldown) < 0 or backoff_factor < 1:
            raise ValueError("delays must be non-negative and backoff_factor at least 1")
        self._max_attempts = max_attempts
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._backoff_factor = backoff_factor
        self._threshold = circuit_failure_threshold
        self._cooldown = circuit_cooldown
        self._clock = clock
        self._sleeper = sleeper
        self._random_source = random_source
        self._breakers: dict[str, _CircuitBreaker] = {}

    def is_open(self, provider: str) -> bool:
        """True while the provider's circuit rejects calls."""

        return self._breaker(provider).is_open(self._clock())

    async def run[T](self, provider: str, operation: Callable[[], Awaitable[T]]) -> T:
        breaker = self._breaker(provider)
        holds_probe = breaker.admit(provider, self._clock())
        try:
            result = await self._attempt(provider, operation)
        except ProviderFailure as exc:
            breaker.record(healthy=not exc.error.retryable, now=self._clock())
            raise
        except BaseException:
            # Bugs and cancellation say nothing about provider health, unless this run was the
            # half-open probe: then the circuit must not stay admitted.
            if holds_probe:
                breaker.record(healthy=False, now=self._clock())
            raise
        else:
            breaker.record(healthy=True, now=self._clock())
            return result
        finally:
            breaker.release(holds_probe)

    def _breaker(self, provider: str) -> _CircuitBreaker:
        breaker = self._breakers.get(provider)
        if breaker is None:
            breaker = _CircuitBreaker(threshold=self._threshold, cooldown=self._cooldown)
            self._breakers[provider] = breaker
        return breaker

    async def _attempt[T](self, provider: str, operation: Callable[[], Awaitable[T]]) -> T:
        attempt = 0
        while True:
            cause: BaseException | None = None
            try:
                return await operation()
            except httpx.TransportError as exc:
                failure = ProviderFailure(
                    ProviderError(
                        provider=provider,
                        code="transport_error",
                        message=type(exc).__name__,
                        retryable=True,
                    )
                )
                cause = exc
            except ProviderFailure as exc:
                failure = exc
            delay = self._next_delay(failure, attempt)
            if delay is None:
                if cause is None:
                    raise failure
                raise failure from cause
            await self._sleeper(delay)
            attempt += 1

    def _next_delay(self, failure: ProviderFailure, attempt: int) -> float | None:
        if not failure.error.retryable or attempt + 1 >= self._max_attempts:
            return None
        retry_after = failure.retry_after if isinstance(failure, RateLimited) else None
        if retry_after is not None:
            return retry_after if retry_after <= self._max_delay else None
        try:
            ceiling = min(self._max_delay, self._base_delay * self._backoff_factor**attempt)
        except OverflowError:
            ceiling = self._max_delay
        return ceiling * self._random_source()
