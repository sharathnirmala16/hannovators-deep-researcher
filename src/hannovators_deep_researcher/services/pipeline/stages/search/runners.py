"""Run one query spec against PubMed or the web router, with persistent zero-hit rewrites.

Each attempt writes one `search_queries` row (its intent and filter variant are in
`applied_filters`) and one QUERY event. A NEGATIVE or ALTERNATIVE query that finds nothing is
rewritten and retried up to `search_max_rounds`, so disconfirming searches do not give up
after one empty result.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from time import perf_counter

from hannovators_deep_researcher.infrastructure.resilience import RateLimited
from hannovators_deep_researcher.models.enums import (
    ModelRole,
    ProviderAttemptStatus,
    SearchIntent,
    SourceStatus,
    TraceEventKind,
)
from hannovators_deep_researcher.models.literature import CandidateRecord, SourceLinkRecord
from hannovators_deep_researcher.models.web import (
    ProviderFailure,
    WebSearchRequest,
    WebSearchResponse,
)
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.search import general, medical
from hannovators_deep_researcher.services.pipeline.stages.search.candidates import web_candidate
from hannovators_deep_researcher.services.pipeline.stages.search.intents import (
    QuerySpec,
    plain_query,
)
from hannovators_deep_researcher.services.pipeline.stages.search.medical import Variant
from hannovators_deep_researcher.services.pipeline.stages.search.refine import (
    CountAttempt,
    refine_query,
)
from hannovators_deep_researcher.services.pipeline.stages.search.schemas import QueryRewrite

PERSISTENT_INTENTS = frozenset({SearchIntent.NEGATIVE, SearchIntent.ALTERNATIVE})
MAX_SEEDS = 5
RELATED_LIMIT = 40
MIN_BROAD_WORDS = 2
# The PubMed adapter already retries throttling; this outer retry covers other providers.
RETRY_ATTEMPTS = 2
RETRY_BASE_SECONDS = 1.0
RETRY_MAX_SECONDS = 10.0


@dataclass
class Group:
    """What one spec found: records tagged with the `search_queries` row that found them."""

    spec: QuerySpec
    hits: list[tuple[CandidateRecord, str]] = field(default_factory=list)
    raw_hits: int = 0
    attempts: int = 0
    links: list[SourceLinkRecord] = field(default_factory=list)


def broaden(query: str) -> str | None:
    """Deterministic fallback rewrite: drop the last AND clause, else the last word."""

    if " AND " in query:
        return query.rsplit(" AND ", 1)[0].strip()
    words = query.split()
    return " ".join(words[:-1]) if len(words) > MIN_BROAD_WORDS else None


async def _rewrite(
    ctx: StageContext, spec: QuerySpec, query: str, hits: int, *, web: bool
) -> tuple[str, str] | None:
    hint = medical.INTENT_REWRITE_HINT.get(spec.intent, "")
    system = general.REWRITE_SYSTEM if web else medical.REWRITE_SYSTEM
    window = ctx.settings
    try:
        result = await ctx.chat.complete_json(
            role=ModelRole.QUERY,
            system=f"{system}\n{hint}".strip(),
            user=(
                f"Intent: {spec.intent}\nQuery: {query}\nHits: {hits}\n"
                f"Target window: {window.search_hits_min} to {window.search_hits_max}"
            ),
            schema=QueryRewrite,
        )
        if result.query.strip() and result.query.strip() != query:
            return result.query.strip(), f"{hits} hits: {result.note}"
    except Exception:
        pass
    broader = broaden(query)
    return (broader, f"{hits} hits: dropped the last concept to broaden") if broader else None


async def _log(
    ctx: StageContext,
    spec: QuerySpec,
    *,
    tool: str,
    query: str,
    filters: str,
    hits: int,
    iteration: int,
    latency_ms: int,
    note: str | None,
) -> str:
    row = await ctx.repositories.create_search_query(
        ctx.workspace_id,
        iteration=iteration,
        tool=tool,
        core_query=query,
        applied_filters=f"{spec.label} {filters}".strip(),
        raw_hit_count=hits,
        latency_ms=latency_ms,
        refinement_note=note,
    )
    await ctx.emit(
        TraceEventKind.QUERY,
        f"{tool} [{spec.intent}]: {query} -> {hits} hits",
        {
            "tool": tool,
            "query_id": row.id,
            "iteration": iteration,
            "hits": hits,
            "note": note,
            "intent": spec.intent,
            "variant": spec.variant,
        },
    )
    return row.id


async def run_spec(
    ctx: StageContext, spec: QuerySpec, pubmed_slots: asyncio.Semaphore | None = None
) -> Group:
    """Run one spec. `pubmed_slots` caps concurrent PubMed specs (NCBI rate limits)."""

    try:
        if spec.tool == "pubmed":
            if pubmed_slots is None:
                return await _pubmed(ctx, spec)
            async with pubmed_slots:
                return await _pubmed(ctx, spec)
        return await _web(ctx, spec)
    except Exception as error:
        await ctx.emit(
            TraceEventKind.WARNING,
            f"{spec.tool} failed for [{spec.intent}] '{spec.query[:120]}': {_describe(error)}",
            {"tool": spec.tool, "query": spec.query, "intent": spec.intent},
        )
        return Group(spec)


def _describe(error: Exception) -> str:
    if isinstance(error, ProviderFailure):
        return f"{error.error.code} ({error.error.message})"
    return type(error).__name__


async def _retrying[T](call: Callable[[], Awaitable[T]]) -> T:
    """Retry a retryable provider failure (429, timeouts) with backoff, honoring Retry-After."""

    for attempt in range(RETRY_ATTEMPTS):
        try:
            return await call()
        except ProviderFailure as failure:
            if not failure.error.retryable or attempt == RETRY_ATTEMPTS - 1:
                raise
            hint = failure.retry_after if isinstance(failure, RateLimited) else None
            await asyncio.sleep(min(hint or RETRY_BASE_SECONDS * 2**attempt, RETRY_MAX_SECONDS))
    raise AssertionError("unreachable")


async def _pubmed(ctx: StageContext, spec: QuerySpec) -> Group:
    settings = ctx.settings

    async def count(query: str) -> int:
        filtered = medical.with_filters(query, spec.variant)
        return await _retrying(lambda: ctx.literature.count(filtered))

    async def rewrite(query: str, hits: int) -> tuple[str, str] | None:
        return await _rewrite(ctx, spec, query, hits, web=False)

    attempts = await refine_query(
        spec.query,
        count=count,
        rewrite=rewrite,
        max_rounds=settings.search_max_rounds,
        hits_min=settings.search_hits_min,
        hits_max=settings.search_hits_max,
    )
    query_id = await _log_attempts(ctx, spec, attempts)
    final = attempts[-1]
    group = Group(spec, raw_hits=final.hits, attempts=len(attempts))
    if final.hits == 0:
        return group
    limit = min(spec.limit, ctx.app_settings.run_budget_max_candidates)
    filtered = medical.with_filters(final.query, spec.variant)
    records: list[CandidateRecord] = await _retrying(
        lambda: ctx.literature.search(filtered, limit=limit)
    )
    group.hits = [(record, query_id) for record in records]
    return group


async def _log_attempts(ctx: StageContext, spec: QuerySpec, attempts: list[CountAttempt]) -> str:
    row_id = ""
    for attempt in attempts:
        row_id = await _log(
            ctx,
            spec,
            tool="pubmed",
            query=attempt.query,
            filters=medical.FILTERS[spec.variant],
            hits=attempt.hits,
            iteration=attempt.iteration,
            latency_ms=attempt.latency_ms,
            note=attempt.note,
        )
    return row_id


async def _web(ctx: StageContext, spec: QuerySpec) -> Group:
    group = Group(spec)
    query, note = spec.query, None
    rounds = ctx.settings.search_max_rounds if spec.intent in PERSISTENT_INTENTS else 1
    for iteration in range(rounds):
        started = perf_counter()
        response = await ctx.web.search(
            WebSearchRequest(query=query, limit=spec.limit, include_domains=list(spec.domains))
        )
        await _warn_failed_providers(ctx, response)
        tool = f"web:{response.provider}"
        query_id = await _log(
            ctx,
            spec,
            tool=tool,
            query=query,
            filters=" ".join(f"site:{domain}" for domain in spec.domains),
            hits=len(response.results),
            iteration=iteration,
            latency_ms=round((perf_counter() - started) * 1000),
            note=note,
        )
        group.attempts += 1
        group.raw_hits = len(response.results)
        if response.results or iteration == rounds - 1:
            candidates = (web_candidate(result) for result in response.results)
            group.hits = [(record, query_id) for record in candidates if record is not None]
            return group
        rewritten = await _rewrite(ctx, spec, query, 0, web=True)
        if rewritten is None:
            return group
        query, note = plain_query(rewritten[0]), rewritten[1]
    return group


async def _warn_failed_providers(ctx: StageContext, response: WebSearchResponse) -> None:
    for attempt in response.attempts:
        if attempt.status is ProviderAttemptStatus.FAILED and attempt.error is not None:
            await ctx.emit(
                TraceEventKind.WARNING,
                f"Web provider {attempt.provider} failed: {attempt.error.message}",
                {"tool": f"web:{attempt.provider}", "code": attempt.error.code},
            )


# --- Seed citations ------------------------------------------------------------------


def _seed_ids(external_id: str, extra_json: str | None) -> tuple[str | None, str | None]:
    try:
        extra = json.loads(extra_json) if extra_json else {}
    except ValueError:
        extra = {}
    extra = extra if isinstance(extra, dict) else {}
    pmid = extra.get("pmid") or (external_id if external_id.isdigit() else None)
    doi = extra.get("doi") or (external_id if external_id.startswith("10.") else None)
    return (str(pmid) if pmid else None), (str(doi) if doi else None)


def _title_query(title: str) -> str | None:
    """A seed title as a keyword query; file names and one-word titles are skipped."""

    words = plain_query(title, max_words=12).split()
    if len(words) < 3 or title.lower().endswith(".pdf"):
        return None
    return " ".join(words)


async def seed_citation_groups(
    ctx: StageContext, pubmed_slots: asyncio.Semaphore | None = None
) -> tuple[list[Group], dict[str, str]]:
    """Related and cited records of the seeds (PubMed elink), plus seed-title look-alikes.

    Returns the groups and a map of seed PMID -> seed source ID for the citation links.
    """

    seeds = (await ctx.repositories.list_sources(ctx.workspace_id, [SourceStatus.SEED]))[:MAX_SEEDS]
    pmid_to_seed: dict[str, str] = {}
    title_specs: list[QuerySpec] = []
    for seed in seeds:
        pmid, doi = _seed_ids(seed.external_id, seed.extra_json)
        if pmid is None and doi is not None:
            pmid = await _pmid_for_doi(ctx, doi)
        if pmid is not None:
            pmid_to_seed[pmid] = seed.id
        query = _title_query(seed.title)
        if query is not None:
            title_specs.append(
                QuerySpec(SearchIntent.SEED_CITATION, query, "pubmed", Variant.HIERARCHY, 10)
            )
    groups = [await _related(ctx, pmid_to_seed)] if pmid_to_seed else []
    groups += [await run_spec(ctx, spec, pubmed_slots) for spec in title_specs]
    return [group for group in groups if group.attempts], pmid_to_seed


async def _pmid_for_doi(ctx: StageContext, doi: str) -> str | None:
    try:
        records = await ctx.literature.search(f"{doi}[doi]", limit=1)
    except Exception:
        return None
    return records[0].pmid if records and records[0].pmid else None


async def _related(ctx: StageContext, pmid_to_seed: dict[str, str]) -> Group:
    spec = QuerySpec(SearchIntent.SEED_CITATION, "", "elink", Variant.NONE, RELATED_LIMIT)
    started = perf_counter()
    group = Group(spec, attempts=1)
    try:
        links = await ctx.literature.related(list(pmid_to_seed), limit=RELATED_LIMIT)
        others = list(
            dict.fromkeys(
                link.to_external_id
                if link.from_external_id in pmid_to_seed
                else link.from_external_id
                for link in links
            )
        )
        others = [item for item in others if item not in pmid_to_seed][:RELATED_LIMIT]
        records = (
            await ctx.literature.search(
                " OR ".join(f"{item}[uid]" for item in others), limit=RELATED_LIMIT
            )
            if others
            else []
        )
    except Exception as error:
        await ctx.emit(
            TraceEventKind.WARNING,
            f"Seed citation lookup failed: {type(error).__name__}",
            {"tool": "elink", "seeds": list(pmid_to_seed)},
        )
        return group
    query_id = await _log(
        ctx,
        spec,
        tool="elink",
        query="related:" + ",".join(pmid_to_seed),
        filters="",
        hits=len(records),
        iteration=0,
        latency_ms=round((perf_counter() - started) * 1000),
        note=None,
    )
    group.raw_hits = len(records)
    group.hits = [(record, query_id) for record in records]
    group.links = links
    return group
