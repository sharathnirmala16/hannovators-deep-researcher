"""Async token bucket shared by every caller of one rate-limited API (PLAN.md risk "PubMed
throttling").

The bucket reserves a start slot for each request without awaiting between the read and the
write of its state, so it needs no `asyncio.Lock` and works across event loops (tests create a
new loop per test, while `shared_bucket()` instances live for the whole process). A caller that
gets HTTP 429 calls `pause()`, which pushes every later slot back, so concurrent callers back
off together instead of hammering the API.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable


class TokenBucket:
    """`rate` requests per second with bursts of up to `burst` back-to-back requests."""

    def __init__(
        self,
        rate: float,
        *,
        burst: int = 1,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if rate <= 0 or burst < 1:
            raise ValueError("rate must be positive and burst at least 1")
        self.rate = rate
        self._interval = 1.0 / rate
        self._tolerance = (burst - 1) * self._interval
        self._clock = clock
        self._sleeper = sleeper
        # Theoretical arrival time of the next request (generic cell rate algorithm).
        self._next = 0.0

    def reserve(self) -> float:
        """Reserve one slot and return how long the caller must wait before using it."""

        now = self._clock()
        start = max(now, self._next - self._tolerance)
        self._next = max(self._next, now) + self._interval
        return start - now

    async def acquire(self) -> None:
        delay = self.reserve()
        if delay > 0:
            await self._sleeper(delay)

    def pause(self, seconds: float) -> None:
        """Hold every slot for at least `seconds` from now (after a 429 or `Retry-After`)."""

        self._next = max(self._next, self._clock() + max(seconds, 0.0))


_SHARED: dict[str, TokenBucket] = {}


def shared_bucket(name: str, rate: float, *, burst: int = 1) -> TokenBucket:
    """The process-wide bucket for `name`, so separate adapter instances share one limit.

    A later call with another rate replaces the bucket (for example after the API key changes).
    """

    bucket = _SHARED.get(name)
    if bucket is None or bucket.rate != rate:
        bucket = TokenBucket(rate, burst=burst)
        _SHARED[name] = bucket
    return bucket
