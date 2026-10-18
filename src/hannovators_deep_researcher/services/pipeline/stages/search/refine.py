"""Hit-count refinement loop: count, rewrite while outside the window, stop at max rounds."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter

CountFn = Callable[[str], Awaitable[int]]
# Returns (new query, note), or None to stop refining.
RewriteFn = Callable[[str, int], Awaitable[tuple[str, str] | None]]


@dataclass(frozen=True, slots=True)
class CountAttempt:
    iteration: int
    query: str
    hits: int
    latency_ms: int
    note: str | None = None


async def refine_query(
    core_query: str,
    *,
    count: CountFn,
    rewrite: RewriteFn,
    max_rounds: int,
    hits_min: int,
    hits_max: int,
) -> list[CountAttempt]:
    """Count up to `max_rounds` times. The last attempt holds the query to run."""

    attempts: list[CountAttempt] = []
    query, note = core_query, None
    for iteration in range(max_rounds):
        started = perf_counter()
        hits = await count(query)
        latency_ms = round((perf_counter() - started) * 1000)
        attempts.append(CountAttempt(iteration, query, hits, latency_ms, note))
        if hits_min <= hits <= hits_max or iteration == max_rounds - 1:
            break
        rewritten = await rewrite(query, hits)
        if rewritten is None:
            break
        query, note = rewritten
    return attempts
