"""Search: core queries, PubMed hit-count refinement, and concurrent PubMed + web retrieval.

GENERAL mode searches the web only; PubMed and its design filters apply to MEDICAL.
"""

import asyncio
import json
from time import perf_counter

from hannovators_deep_researcher.models.contracts import (
    DECOMPOSITION_ADAPTER,
    PicotsDecomposition,
    ScopeDecomposition,
)
from hannovators_deep_researcher.models.enums import (
    ModelRole,
    ProviderAttemptStatus,
    SourceStatus,
    TraceEventKind,
)
from hannovators_deep_researcher.models.literature import CandidateRecord
from hannovators_deep_researcher.models.web import WebSearchRequest
from hannovators_deep_researcher.persistence.tables import SourceRow
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.search import general, medical
from hannovators_deep_researcher.services.pipeline.stages.search.candidates import (
    dedupe_keys,
    merge_candidates,
    web_candidate,
)
from hannovators_deep_researcher.services.pipeline.stages.search.refine import (
    CountAttempt,
    refine_query,
)
from hannovators_deep_researcher.services.pipeline.stages.search.schemas import (
    GeneralQueryPlan,
    MedicalQueryPlan,
    QueryRewrite,
)

MIN_QUERIES = 3
MAX_QUERIES = 5
PUBMED_LIMIT = 40
WEB_LIMIT = 10

Found = list[tuple[CandidateRecord, str]]


async def run(ctx: StageContext) -> None:
    workspace = await ctx.repositories.get_workspace(ctx.workspace_id)
    if workspace is None or workspace.decomposition_json is None:
        raise LookupError(f"workspace {ctx.workspace_id} has no decomposition")
    decomposition = DECOMPOSITION_ADAPTER.validate_json(workspace.decomposition_json)
    queries = await _core_queries(ctx, workspace.research_question, decomposition)
    await ctx.emit(
        TraceEventKind.PROGRESS, f"Generated {len(queries)} core queries", {"queries": queries}
    )

    is_medical = isinstance(decomposition, PicotsDecomposition)
    tasks = [_pubmed(ctx, query) for query in queries] if is_medical else []
    tasks += [_web(ctx, request) for request in _web_requests(queries, is_medical=is_medical)]
    found = [item for group in await asyncio.gather(*tasks) for item in group]
    await _store(ctx, found)


async def _core_queries(
    ctx: StageContext, question: str, decomposition: PicotsDecomposition | ScopeDecomposition
) -> list[str]:
    user = f"Question: {question}\n\nDecomposition:\n{decomposition.model_dump_json()}"
    try:
        if isinstance(decomposition, PicotsDecomposition):
            plan: MedicalQueryPlan | GeneralQueryPlan = await ctx.chat.complete_json(
                role=ModelRole.QUERY,
                system=medical.QUERY_SYSTEM,
                user=user,
                schema=MedicalQueryPlan,
            )
        else:
            plan = await ctx.chat.complete_json(
                role=ModelRole.QUERY,
                system=general.QUERY_SYSTEM,
                user=user,
                schema=GeneralQueryPlan,
            )
        queries = _unique(plan.queries)
    except Exception as error:
        await ctx.emit(
            TraceEventKind.WARNING,
            f"Query generation failed ({type(error).__name__}); used decomposition queries",
        )
        queries = []
    if len(queries) < MIN_QUERIES:
        queries = _unique([*queries, *fallback_queries(decomposition, question)])
    return queries[:MAX_QUERIES]


def fallback_queries(
    decomposition: PicotsDecomposition | ScopeDecomposition, question: str
) -> list[str]:
    if isinstance(decomposition, PicotsDecomposition):
        terms = [f"{decomposition.population} {item}" for item in decomposition.interventions]
    else:
        lead = decomposition.entities[0] if decomposition.entities else ""
        terms = [f"{lead} {claim}".strip() for claim in decomposition.claims]
    return [*terms, question]


def _unique(queries: list[str]) -> list[str]:
    return list(dict.fromkeys(query.strip() for query in queries if query.strip()))


def _web_requests(queries: list[str], *, is_medical: bool) -> list[WebSearchRequest]:
    """One open web search per query; MEDICAL adds a trial-registry search for the first."""

    requests = [WebSearchRequest(query=query, limit=WEB_LIMIT) for query in queries]
    if is_medical and queries:
        requests.append(
            WebSearchRequest(
                query=queries[0], limit=WEB_LIMIT, include_domains=medical.REGISTRY_DOMAINS
            )
        )
    return requests


async def _pubmed(ctx: StageContext, core_query: str) -> Found:
    settings = ctx.settings

    async def count(query: str) -> int:
        return await ctx.literature.count(medical.with_filters(query))

    async def rewrite(query: str, hits: int) -> tuple[str, str] | None:
        try:
            result = await ctx.chat.complete_json(
                role=ModelRole.QUERY,
                system=medical.REWRITE_SYSTEM,
                user=(
                    f"Core query: {query}\nHits: {hits}\n"
                    f"Target window: {settings.search_hits_min} to {settings.search_hits_max}"
                ),
                schema=QueryRewrite,
            )
        except Exception:
            return None
        return result.query, f"{hits} hits: {result.note}"

    try:
        attempts = await refine_query(
            core_query,
            count=count,
            rewrite=rewrite,
            max_rounds=settings.search_max_rounds,
            hits_min=settings.search_hits_min,
            hits_max=settings.search_hits_max,
        )
        query_id = await _log_pubmed_attempts(ctx, attempts)
        final = attempts[-1]
        if final.hits == 0:
            return []
        limit = min(PUBMED_LIMIT, ctx.app_settings.run_budget_max_candidates)
        records = await ctx.literature.search(medical.with_filters(final.query), limit=limit)
    except Exception as error:
        await ctx.emit(
            TraceEventKind.WARNING,
            f"PubMed failed for '{core_query}': {type(error).__name__}: {error}",
            {"tool": "pubmed", "query": core_query},
        )
        return []
    return [(record, query_id) for record in records]


async def _log_pubmed_attempts(ctx: StageContext, attempts: list[CountAttempt]) -> str:
    """Write one `search_queries` row and QUERY event per attempt; return the last row ID."""

    row_id = ""
    for attempt in attempts:
        row = await ctx.repositories.create_search_query(
            ctx.workspace_id,
            iteration=attempt.iteration,
            tool="pubmed",
            core_query=attempt.query,
            applied_filters=medical.FILTERS,
            raw_hit_count=attempt.hits,
            latency_ms=attempt.latency_ms,
            refinement_note=attempt.note,
        )
        row_id = row.id
        await ctx.emit(
            TraceEventKind.QUERY,
            f"pubmed: {attempt.query} -> {attempt.hits} hits",
            {
                "tool": "pubmed",
                "query_id": row.id,
                "iteration": attempt.iteration,
                "hits": attempt.hits,
                "note": attempt.note,
            },
        )
    return row_id


async def _web(ctx: StageContext, request: WebSearchRequest) -> Found:
    started = perf_counter()
    try:
        response = await ctx.web.search(request)
    except Exception as error:
        await ctx.emit(
            TraceEventKind.WARNING,
            f"Web search failed for '{request.query}': {type(error).__name__}: {error}",
            {"tool": "web", "query": request.query},
        )
        return []
    for attempt in response.attempts:
        if attempt.status is ProviderAttemptStatus.FAILED and attempt.error is not None:
            await ctx.emit(
                TraceEventKind.WARNING,
                f"Web provider {attempt.provider} failed: {attempt.error.message}",
                {"tool": f"web:{attempt.provider}", "code": attempt.error.code},
            )
    tool = f"web:{response.provider}"
    row = await ctx.repositories.create_search_query(
        ctx.workspace_id,
        iteration=0,
        tool=tool,
        core_query=request.query,
        applied_filters=" ".join(f"site:{domain}" for domain in request.include_domains),
        raw_hit_count=len(response.results),
        latency_ms=round((perf_counter() - started) * 1000),
    )
    await ctx.emit(
        TraceEventKind.QUERY,
        f"{tool}: {request.query} -> {len(response.results)} hits",
        {"tool": tool, "query_id": row.id, "iteration": 0, "hits": len(response.results)},
    )
    candidates = (web_candidate(result) for result in response.results)
    return [(record, row.id) for record in candidates if record is not None]


async def _store(ctx: StageContext, found: Found) -> None:
    existing = await ctx.repositories.list_sources(ctx.workspace_id)
    known: set[str] = set()
    for source in existing:
        known |= dedupe_keys(external_id=source.external_id, url=source.url)
    already = sum(source.status != SourceStatus.SEED for source in existing)
    cap = max(ctx.app_settings.run_budget_max_candidates - already, 0)
    kept = merge_candidates(found, known_keys=known, cap=cap)
    await ctx.repositories.add_all(
        [_source_row(ctx.workspace_id, record, query_id) for record, query_id in kept]
    )
    await ctx.emit(
        TraceEventKind.PROGRESS,
        f"Added {len(kept)} candidates from {len(found)} hits",
        {"hits": len(found), "added": len(kept), "cap": cap},
    )


def _source_row(workspace_id: str, record: CandidateRecord, query_id: str) -> SourceRow:
    extra = {
        "doi": record.doi,
        "pmid": record.pmid,
        "pmcid": record.pmcid,
        "publication_types": record.publication_types,
    }
    return SourceRow(
        workspace_id=workspace_id,
        origin=record.origin,
        external_id=record.external_id,
        title=record.title,
        authors_json=json.dumps(record.authors),
        year=record.year,
        venue=record.venue,
        abstract=record.abstract,
        url=record.url,
        pdf_url=record.pdf_url,
        status=SourceStatus.RAW,
        found_by_query_id=query_id,
        extra_json=json.dumps(extra),
    )
