"""Screen: one Jev request per RAW candidate (relevance, votes, exclusion, stance, and the study
design when the heuristics are not decisive), embedding fallback, evidence-ranked top-N, and one
auditable VERDICT trajectory step per candidate."""

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from hannovators_deep_researcher.models.contracts import DECOMPOSITION_ADAPTER, PicotsDecomposition
from hannovators_deep_researcher.models.decisions import DecisionAnswer, DecisionQuestion
from hannovators_deep_researcher.models.enums import (
    DomainMode,
    SourceStatus,
    TraceEventKind,
    TrajectoryKind,
    VerdictOutcome,
)
from hannovators_deep_researcher.persistence.tables import SourceRow
from hannovators_deep_researcher.services.evidence import (
    EVIDENCE_KEY,
    EVIDENCE_QUESTION,
    STANCE_KEY,
    LevelGuess,
    classify_evidence,
    classify_stance,
    heuristic_level,
    is_contrarian,
    keyword_stance,
    level_counts,
    level_from_answer,
    stance_from_answer,
    stance_question,
)
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


@dataclass(frozen=True, slots=True)
class Scope:
    mode: DomainMode
    summary: str
    questions: Mapping[str, DecisionQuestion]
    vote_keys: Sequence[str]


async def run(ctx: StageContext) -> None:
    workspace = await ctx.repositories.get_workspace(ctx.workspace_id)
    if workspace is None or workspace.decomposition_json is None:
        raise LookupError(f"workspace {ctx.workspace_id} has no decomposition")
    decomposition = DECOMPOSITION_ADAPTER.validate_json(workspace.decomposition_json)
    if isinstance(decomposition, PicotsDecomposition):
        scope = Scope(
            DomainMode.MEDICAL,
            medical.summarize(decomposition),
            medical.QUESTIONS,
            medical.VOTE_KEYS,
        )
    else:
        scope = Scope(
            DomainMode.GENERAL,
            general.summarize(decomposition),
            general.QUESTIONS,
            general.VOTE_KEYS,
        )
    await _classify_seeds(ctx, scope)
    candidates = await ctx.repositories.list_sources(ctx.workspace_id, [SourceStatus.RAW])
    if not candidates:
        await ctx.emit(TraceEventKind.PROGRESS, "No candidates to screen")
        return

    jev_results = await _screen_with_jev(ctx, scope, candidates)
    pairs = list(zip(candidates, jev_results, strict=True))
    failed = [source for source, result in pairs if result is None]
    fallback = await _screen_with_embeddings(ctx, scope.summary, failed) if failed else {}
    results = [fallback[source.id] if result is None else result for source, result in pairs]
    decisions = select(
        results, votes_t=ctx.settings.screen_votes_t, top_n=ctx.settings.screen_top_n
    )
    for source, decision in zip(candidates, decisions, strict=True):
        await _save(ctx, source, decision)
    await _summarize(ctx, decisions, len(failed))


def _state(summary: str, source: SourceRow) -> str:
    abstract = (source.abstract or "No abstract available.")[:MAX_ABSTRACT_CHARS]
    types = _publication_types(source)
    type_line = f"\n\nPublication types: {', '.join(types)}" if types else ""
    return (
        f"Research scope:\n{summary}\n\nRecord title: {source.title}{type_line}\n\n"
        f"Abstract:\n{abstract}"
    )


def _extra(source: SourceRow) -> dict[str, object]:
    try:
        value = json.loads(source.extra_json) if source.extra_json else {}
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _publication_types(source: SourceRow) -> list[str]:
    types = _extra(source).get("publication_types")
    return [str(item) for item in types] if isinstance(types, list) else []


def _guess(source: SourceRow) -> LevelGuess:
    return heuristic_level(
        title=source.title,
        abstract=source.abstract,
        publication_types=_publication_types(source),
        origin=source.origin,
    )


async def _screen_with_jev(
    ctx: StageContext, scope: Scope, candidates: Sequence[SourceRow]
) -> list[ScreenResult | None]:
    """Jev results in candidate order; None where Jev failed for that candidate."""

    total = len(candidates)
    done = 0
    stance = stance_question(scope.mode)

    async def screen_one(source: SourceRow) -> ScreenResult | None:
        nonlocal done
        guess = _guess(source)
        questions = {**scope.questions, STANCE_KEY: stance}
        if not guess.decisive:
            questions[EVIDENCE_KEY] = EVIDENCE_QUESTION
        try:
            answers = await ctx.decisions.evaluate(_state(scope.summary, source), questions)
            result: ScreenResult | None = _from_answers(source, answers, scope.vote_keys, guess)
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
    source: SourceRow,
    answers: Mapping[str, DecisionAnswer],
    vote_keys: Sequence[str],
    guess: LevelGuess,
) -> ScreenResult:
    relevance = answers[RELEVANCE_KEY]
    if relevance.score is None:
        raise ValueError("relevance answer has no score")
    noul = {key: answers[key].noul for key in vote_keys}
    level, level_method = (
        (guess.level, guess.method)
        if guess.decisive and guess.level is not None
        else level_from_answer(answers.get(EVIDENCE_KEY), guess)
    )
    stance_answer = answers.get(STANCE_KEY)
    stance, stance_method = stance_from_answer(
        stance_answer, f"{source.title}\n{source.abstract or ''}"
    )
    return ScreenResult(
        source_id=source.id,
        relevance=min(max(relevance.score, 0.0), MAX_RELEVANCE),
        confidence=1.0 if relevance.confidence is None else relevance.confidence,
        votes=count_votes(list(noul.values())),
        exclusion=answers[EXCLUSION_KEY].choice,
        details={
            "votes": noul,
            "evidence_method": level_method,
            "stance_method": stance_method,
            "stance_confidence": stance_answer.confidence if stance_answer else None,
            "stance_probabilities": stance_answer.probabilities if stance_answer else {},
        },
        evidence_level=level,
        stance=stance,
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
        guess = _guess(source)
        results[source.id] = ScreenResult(
            source_id=source.id,
            relevance=MAX_RELEVANCE * max(cosine, 0.0),
            confidence=1.0,
            votes=None,
            method="embedding",
            details={
                "cosine": round(cosine, 4),
                "evidence_method": guess.method,
                "stance_method": "keywords",
            },
            evidence_level=guess.level,
            stance=keyword_stance(f"{source.title}\n{source.abstract or ''}"),
        )
    return results


async def _save(ctx: StageContext, source: SourceRow, decision: ScreenDecision) -> None:
    result = decision.result
    screen = {
        "method": result.method,
        "relevance": result.relevance,
        "confidence": result.confidence,
        "exclusion": result.exclusion,
        "evidence_rank": result.evidence_rank,
        "reserved_slot": decision.reserved,
        "position": decision.position,
        **result.details,
    }
    await ctx.repositories.update_source_fields(
        result.source_id,
        status=SourceStatus.SCREEN_PROMOTED
        if decision.promoted
        else SourceStatus.SCREEN_DISCOUNTED,
        screen_score=round(result.strength, 4),
        screen_z=round(decision.z, 4),
        screen_votes=result.votes,
        screen_json=screen,
        evidence_level=result.evidence_level,
        stance=result.stance,
        rejection_code=decision.rejection_code,
        decision_explanation=decision.explanation,
    )
    outcome = VerdictOutcome.KEPT if decision.promoted else VerdictOutcome.REMOVED
    await ctx.trajectory.record(
        kind=TrajectoryKind.VERDICT,
        name="screen.verdict",
        target=source.url or source.external_id,
        summary=f"{outcome}: {source.title[:90]} - {decision.explanation}"[:400],
        request={
            "title": source.title,
            "origin": source.origin,
            "external_id": source.external_id,
            "search_intent": source.search_intent,
        },
        response={
            **screen,
            "votes": result.votes,
            "z": round(decision.z, 4),
            "strength": round(result.strength, 4),
            "evidence_level": result.evidence_level,
            "stance": result.stance,
            "search_intent": source.search_intent,
            "rejection_code": decision.rejection_code,
            "explanation": decision.explanation,
        },
        source_ids=[source.id],
        outcome=outcome,
        confidence=min(max(result.confidence, 0.0), 1.0),
    )


async def _summarize(ctx: StageContext, decisions: Sequence[ScreenDecision], fallback: int) -> None:
    promoted = [decision for decision in decisions if decision.promoted]
    contrarian = [decision for decision in promoted if is_contrarian(decision.result.stance)]
    await ctx.emit(
        TraceEventKind.DECISION,
        f"Screening done: {len(promoted)} promoted ({len(contrarian)} opposing, null, mixed, or "
        f"alternative), {len(decisions) - len(promoted)} discounted",
        {
            "screened": len(decisions),
            "promoted": len(promoted),
            "discounted": len(decisions) - len(promoted),
            "fallback": fallback,
            "reserved_slots_used": sum(decision.reserved for decision in promoted),
            "promoted_levels": level_counts(d.result.evidence_level for d in promoted),
            "promoted_stances": _stance_counts(promoted),
        },
    )


def _stance_counts(decisions: Sequence[ScreenDecision]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for decision in decisions:
        key = str(decision.result.stance or "UNKNOWN")
        counts[key] = counts.get(key, 0) + 1
    return counts


async def _classify_seeds(ctx: StageContext, scope: Scope) -> None:
    """Seeds are not screened, but they still get an evidence level and a stance."""

    seeds = await ctx.repositories.list_sources(ctx.workspace_id, [SourceStatus.SEED])
    for seed in seeds:
        if seed.evidence_level and seed.stance:
            continue
        summary = _extra(seed).get("seed_summary")
        text = seed.abstract or (summary if isinstance(summary, str) else None)
        level, _ = await classify_evidence(
            ctx.decisions,
            title=seed.title,
            abstract=text,
            publication_types=_publication_types(seed),
            origin=seed.origin,
        )
        stance, _ = await classify_stance(
            ctx.decisions, mode=scope.mode, scope=scope.summary, title=seed.title, abstract=text
        )
        await ctx.repositories.update_source_fields(
            seed.id,
            evidence_level=seed.evidence_level or level,
            stance=seed.stance or stance,
        )
