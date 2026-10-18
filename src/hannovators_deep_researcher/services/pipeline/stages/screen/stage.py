"""Screen: one Jev request per RAW candidate, embedding fallback, T-threshold and top-N."""

import asyncio
from collections.abc import Mapping, Sequence

from hannovators_deep_researcher.models.contracts import DECOMPOSITION_ADAPTER, PicotsDecomposition
from hannovators_deep_researcher.models.decisions import DecisionAnswer, DecisionQuestion
from hannovators_deep_researcher.models.enums import SourceStatus, TraceEventKind
from hannovators_deep_researcher.persistence.tables import SourceRow
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.screen import general, medical
from hannovators_deep_researcher.services.pipeline.stages.screen.questions import (
    EXCLUSION_KEY,
    MAX_RELEVANCE,
    RELEVANCE_KEY,
)
from hannovators_deep_researcher.services.pipeline.stages.screen.selection import (
    ScreenDecision,
    ScreenResult,
    count_votes,
    select,
)

MAX_ABSTRACT_CHARS = 6_000
PROGRESS_EVERY = 10
SCREEN_INSTRUCTION = "Given a research scope, retrieve records that are relevant to it"


async def run(ctx: StageContext) -> None:
    workspace = await ctx.repositories.get_workspace(ctx.workspace_id)
    if workspace is None or workspace.decomposition_json is None:
        raise LookupError(f"workspace {ctx.workspace_id} has no decomposition")
    decomposition = DECOMPOSITION_ADAPTER.validate_json(workspace.decomposition_json)
    candidates = await ctx.repositories.list_sources(ctx.workspace_id, [SourceStatus.RAW])
    if not candidates:
        await ctx.emit(TraceEventKind.PROGRESS, "No candidates to screen")
        return

    if isinstance(decomposition, PicotsDecomposition):
        summary = medical.summarize(decomposition)
        questions, vote_keys = medical.QUESTIONS, medical.VOTE_KEYS
    else:
        summary = general.summarize(decomposition)
        questions, vote_keys = general.QUESTIONS, general.VOTE_KEYS

    jev_results = await _screen_with_jev(ctx, summary, candidates, questions, vote_keys)
    pairs = list(zip(candidates, jev_results, strict=True))
    failed = [source for source, result in pairs if result is None]
    fallback = await _screen_with_embeddings(ctx, summary, failed) if failed else {}
    results = [fallback[source.id] if result is None else result for source, result in pairs]
    decisions = select(
        results, votes_t=ctx.settings.screen_votes_t, top_n=ctx.settings.screen_top_n
    )
    for decision in decisions:
        await _save(ctx, decision)
    promoted = sum(decision.promoted for decision in decisions)
    await ctx.emit(
        TraceEventKind.DECISION,
        f"Screening done: {promoted} promoted, {len(decisions) - promoted} discounted",
        {
            "screened": len(decisions),
            "promoted": promoted,
            "discounted": len(decisions) - promoted,
            "fallback": len(failed),
        },
    )


def _state(summary: str, source: SourceRow) -> str:
    abstract = (source.abstract or "No abstract available.")[:MAX_ABSTRACT_CHARS]
    return f"Research scope:\n{summary}\n\nRecord title: {source.title}\n\nAbstract:\n{abstract}"


async def _screen_with_jev(
    ctx: StageContext,
    summary: str,
    candidates: Sequence[SourceRow],
    questions: Mapping[str, DecisionQuestion],
    vote_keys: Sequence[str],
) -> list[ScreenResult | None]:
    """Jev results in candidate order; None where Jev failed for that candidate."""

    total = len(candidates)
    done = 0

    async def screen_one(source: SourceRow) -> ScreenResult | None:
        nonlocal done
        try:
            answers = await ctx.decisions.evaluate(_state(summary, source), questions)
            result: ScreenResult | None = _from_answers(source.id, answers, vote_keys)
        except Exception:
            result = None
        done += 1
        if done % PROGRESS_EVERY == 0 or done == total:
            await ctx.emit(
                TraceEventKind.DECISION,
                f"Screened {done}/{total} candidates",
                {"screened": done, "total": total},
            )
        return result

    return list(await asyncio.gather(*(screen_one(source) for source in candidates)))


def _from_answers(
    source_id: str, answers: Mapping[str, DecisionAnswer], vote_keys: Sequence[str]
) -> ScreenResult:
    relevance = answers[RELEVANCE_KEY]
    if relevance.score is None:
        raise ValueError("relevance answer has no score")
    noul = {key: answers[key].noul for key in vote_keys}
    return ScreenResult(
        source_id=source_id,
        relevance=min(max(relevance.score, 0.0), MAX_RELEVANCE),
        confidence=1.0 if relevance.confidence is None else relevance.confidence,
        votes=count_votes(list(noul.values())),
        exclusion=answers[EXCLUSION_KEY].choice,
        details={"votes": noul},
    )


async def _screen_with_embeddings(
    ctx: StageContext, summary: str, sources: Sequence[SourceRow]
) -> dict[str, ScreenResult]:
    """Cosine of each record against the scope, scaled to the 0..4 relevance range."""

    await ctx.emit(
        TraceEventKind.WARNING,
        f"Jev failed for {len(sources)} candidate(s); used the embedding fallback",
        {"fallback": len(sources)},
    )
    [scope] = await ctx.embedder.embed([summary], instruction=SCREEN_INSTRUCTION)
    vectors = await ctx.embedder.embed(
        [f"{source.title}\n{(source.abstract or '')[:MAX_ABSTRACT_CHARS]}" for source in sources]
    )
    results: dict[str, ScreenResult] = {}
    for source, vector in zip(sources, vectors, strict=True):
        cosine = sum(a * b for a, b in zip(scope, vector, strict=True))
        results[source.id] = ScreenResult(
            source_id=source.id,
            relevance=MAX_RELEVANCE * max(cosine, 0.0),
            confidence=1.0,
            votes=None,
            method="embedding",
            details={"cosine": round(cosine, 4)},
        )
    return results


async def _save(ctx: StageContext, decision: ScreenDecision) -> None:
    result = decision.result
    await ctx.repositories.update_source_fields(
        result.source_id,
        status=SourceStatus.SCREEN_PROMOTED
        if decision.promoted
        else SourceStatus.SCREEN_DISCOUNTED,
        screen_score=round(result.strength, 4),
        screen_z=round(decision.z, 4),
        screen_votes=result.votes,
        screen_json={
            "method": result.method,
            "relevance": result.relevance,
            "confidence": result.confidence,
            "exclusion": result.exclusion,
            **result.details,
        },
        rejection_code=decision.rejection_code,
        decision_explanation=decision.explanation,
    )
