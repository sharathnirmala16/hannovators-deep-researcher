"""Search: CORE plus NEGATIVE, ALTERNATIVE, SAFETY, and seed-citation queries, concurrently.

MEDICAL runs each core query against PubMed twice (systematic reviews / meta-analyses first,
then randomized trials) and adds a few web searches (registries, regulators); GENERAL searches
the web only. Every source records the `search_intent` of the query that found it first.
"""

import asyncio
import json
from collections import Counter

from sqlalchemy.exc import IntegrityError

from hannovators_deep_researcher.models.contracts import (
    DECOMPOSITION_ADAPTER,
    PicotsDecomposition,
    ScopeDecomposition,
)
from hannovators_deep_researcher.models.enums import (
    ModelRole,
    SearchIntent,
    SourceLinkKind,
    SourceStatus,
    TraceEventKind,
)
from hannovators_deep_researcher.models.literature import CandidateRecord
from hannovators_deep_researcher.persistence.tables import SourceRow
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.search import general, medical
from hannovators_deep_researcher.services.pipeline.stages.search.candidates import (
    dedupe_keys,
    merge_candidates,
    round_robin,
)
from hannovators_deep_researcher.services.pipeline.stages.search.intents import (
    complete_plan,
    general_fallbacks,
    general_specs,
    medical_fallbacks,
    medical_specs,
)
from hannovators_deep_researcher.services.pipeline.stages.search.runners import (
    Group,
    run_spec,
    seed_citation_groups,
)
from hannovators_deep_researcher.services.pipeline.stages.search.schemas import (
    GeneralQueryPlan,
    IntentQueryPlan,
    MedicalQueryPlan,
)

INTENT_ORDER = (
    SearchIntent.SEED_CITATION,
    SearchIntent.CORE,
    SearchIntent.NEGATIVE,
    SearchIntent.ALTERNATIVE,
    SearchIntent.SAFETY,
)
Tagged = tuple[CandidateRecord, tuple[str, Group]]
PUBMED_CONCURRENCY = 3


async def run(ctx: StageContext) -> None:
    workspace = await ctx.repositories.get_workspace(ctx.workspace_id)
    if workspace is None or workspace.decomposition_json is None:
        raise LookupError(f"workspace {ctx.workspace_id} has no decomposition")
    decomposition = DECOMPOSITION_ADAPTER.validate_json(workspace.decomposition_json)
    plan = await _plan(ctx, workspace.research_question, decomposition)
    await ctx.emit(
        TraceEventKind.PROGRESS,
        "Planned queries: "
        + ", ".join(f"{len(queries)} {intent}" for intent, queries in plan.items()),
        {"queries": {str(intent): queries for intent, queries in plan.items()}},
    )

    is_medical = isinstance(decomposition, PicotsDecomposition)
    specs = medical_specs(plan) if is_medical else general_specs(plan)
    # PubMed specs share NCBI's rate limit (the adapter's token bucket); a few at a time keeps
    # each spec's count -> search -> fetch chain short instead of queueing every request.
    pubmed_slots = asyncio.Semaphore(PUBMED_CONCURRENCY)
    seeds_task = asyncio.create_task(
        seed_citation_groups(ctx, pubmed_slots) if is_medical else _no_seeds()
    )
    spec_groups = await asyncio.gather(*(run_spec(ctx, spec, pubmed_slots) for spec in specs))
    seed_groups, pmid_to_seed = await seeds_task
    groups: list[Group] = [*seed_groups, *spec_groups]
    added = await _store(ctx, groups)
    await _link_seeds(ctx, seed_groups, pmid_to_seed)
    await _report_intents(ctx, groups, added)


async def _no_seeds() -> tuple[list[Group], dict[str, str]]:
    return [], {}


async def _plan(
    ctx: StageContext, question: str, decomposition: PicotsDecomposition | ScopeDecomposition
) -> dict[SearchIntent, list[str]]:
    user = f"Question: {question}\n\nDecomposition:\n{decomposition.model_dump_json()}"
    planned: dict[SearchIntent, list[str]] = {}
    try:
        if isinstance(decomposition, PicotsDecomposition):
            reply: IntentQueryPlan = await ctx.chat.complete_json(
                role=ModelRole.QUERY,
                system=medical.QUERY_SYSTEM,
                user=user,
                schema=MedicalQueryPlan,
            )
        else:
            reply = await ctx.chat.complete_json(
                role=ModelRole.QUERY,
                system=general.QUERY_SYSTEM,
                user=user,
                schema=GeneralQueryPlan,
            )
        planned = reply.by_intent()
    except Exception as error:
        await ctx.emit(
            TraceEventKind.WARNING,
            f"Query generation failed ({type(error).__name__}); used decomposition templates",
        )
    fallbacks = (
        medical_fallbacks(decomposition, question)
        if isinstance(decomposition, PicotsDecomposition)
        else general_fallbacks(decomposition, question)
    )
    return complete_plan(planned, fallbacks)


def _ordered(groups: list[Group]) -> list[Group]:
    return sorted(groups, key=lambda group: INTENT_ORDER.index(group.spec.intent))


async def _store(ctx: StageContext, groups: list[Group]) -> Counter[SearchIntent]:
    """Insert new RAW sources, interleaving groups so every intent keeps a share of the cap."""

    existing = await ctx.repositories.list_sources(ctx.workspace_id)
    known: set[str] = set()
    for source in existing:
        known |= dedupe_keys(external_id=source.external_id, url=source.url)
    # Deep research reports are a separate, user-started pool: their cited URLs do not use up
    # the search budget, so every intent still gets a share of it.
    already = sum(
        source.status != SourceStatus.SEED and source.search_intent != SearchIntent.DEEP_RESEARCH
        for source in existing
    )
    cap = max(ctx.app_settings.run_budget_max_candidates - already, 0)
    tagged: list[list[Tagged]] = [
        [(record, (query_id, group)) for record, query_id in group.hits]
        for group in _ordered(groups)
    ]
    kept = merge_candidates(round_robin(tagged), known_keys=known, cap=cap)
    await ctx.repositories.add_all(
        [
            _source_row(ctx.workspace_id, record, query_id, group)
            for record, (query_id, group) in kept
        ]
    )
    total = sum(len(group.hits) for group in groups)
    await ctx.emit(
        TraceEventKind.PROGRESS,
        f"Added {len(kept)} candidates from {total} hits",
        {"hits": total, "added": len(kept), "cap": cap},
    )
    return Counter(group.spec.intent for _, (_, group) in kept)


async def _report_intents(
    ctx: StageContext, groups: list[Group], added: Counter[SearchIntent]
) -> None:
    for intent in INTENT_ORDER:
        mine = [group for group in groups if group.spec.intent is intent]
        if not mine:
            continue
        hits = sum(len(group.hits) for group in mine)
        retries = sum(max(group.attempts - 1, 0) for group in mine)
        payload = {
            "intent": intent,
            "queries": len(mine),
            "hits": hits,
            "added": added[intent],
            "retries": retries,
        }
        await ctx.emit(
            TraceEventKind.PROGRESS,
            f"{intent} search: {len(mine)} queries, {hits} hits, {added[intent]} new candidates"
            + (f", {retries} rewrites" if retries else ""),
            payload,
        )
        if intent in (SearchIntent.NEGATIVE, SearchIntent.ALTERNATIVE) and not added[intent]:
            await ctx.emit(
                TraceEventKind.WARNING,
                f"{intent} search added no new candidates after rewrites",
                payload,
            )


async def _link_seeds(ctx: StageContext, groups: list[Group], pmid_to_seed: dict[str, str]) -> None:
    links = [link for group in groups for link in group.links]
    if not links:
        return
    by_external = {
        source.external_id: source.id
        for source in await ctx.repositories.list_sources(ctx.workspace_id)
    }
    by_external.update(pmid_to_seed)
    for link in links:
        source = by_external.get(link.from_external_id)
        target = by_external.get(link.to_external_id)
        if source is None or target is None or source == target:
            continue
        try:
            await ctx.repositories.create_source_link(
                ctx.workspace_id,
                from_source_id=source,
                to_source_id=target,
                kind=SourceLinkKind(link.kind),
            )
        except IntegrityError:
            continue


def _source_row(
    workspace_id: str, record: CandidateRecord, query_id: str, group: Group
) -> SourceRow:
    spec = group.spec
    extra = {
        "doi": record.doi,
        "pmid": record.pmid,
        "pmcid": record.pmcid,
        "publication_types": record.publication_types,
        "found_by": spec.tool,
        "query_variant": spec.variant,
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
        found_by_query_id=query_id or None,
        search_intent=spec.intent,
        extra_json=json.dumps(extra),
    )
