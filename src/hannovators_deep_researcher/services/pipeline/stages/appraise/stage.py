"""Appraise SCREEN_PROMOTED sources from their abstracts and keep the top K."""

import asyncio
import json

from hannovators_deep_researcher.models.contracts import (
    DECOMPOSITION_ADAPTER,
    PicotsDecomposition,
    ScopeDecomposition,
)
from hannovators_deep_researcher.models.enums import (
    ModelRole,
    RejectionCode,
    SourceStatus,
    TraceEventKind,
)
from hannovators_deep_researcher.persistence.tables import SourceRow
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.appraise import general, medical
from hannovators_deep_researcher.services.pipeline.stages.appraise.common import SourceAppraisal

CONCURRENCY = 4
_MAX_TEXT_CHARS = 12_000


async def _load_decomposition(
    ctx: StageContext,
) -> PicotsDecomposition | ScopeDecomposition | None:
    workspace = await ctx.repositories.get_workspace(ctx.workspace_id)
    if workspace is None or not workspace.decomposition_json:
        return None
    return DECOMPOSITION_ADAPTER.validate_json(workspace.decomposition_json)


async def _appraise_one(
    ctx: StageContext,
    decomposition: PicotsDecomposition | ScopeDecomposition,
    source: SourceRow,
) -> SourceAppraisal:
    text = (source.abstract or "")[:_MAX_TEXT_CHARS]
    if isinstance(decomposition, PicotsDecomposition):
        medical_reply = await ctx.chat.complete_json(
            role=ModelRole.APPRAISE,
            system=medical.SYSTEM,
            user=medical.user_prompt(decomposition, source.title, text),
            schema=medical.MedicalAppraisal,
        )
        return medical.evaluate(source.id, text, medical_reply, ctx.settings.appraise_m)
    general_reply = await ctx.chat.complete_json(
        role=ModelRole.APPRAISE,
        system=general.SYSTEM,
        user=general.user_prompt(decomposition, source.title, text),
        schema=general.GeneralAppraisal,
    )
    return general.evaluate(source.id, text, general_reply)


async def _guarded(
    ctx: StageContext,
    limit: asyncio.Semaphore,
    decomposition: PicotsDecomposition | ScopeDecomposition,
    source: SourceRow,
) -> SourceAppraisal | None:
    async with limit:
        try:
            return await _appraise_one(ctx, decomposition, source)
        except Exception as exc:
            await ctx.emit(
                TraceEventKind.WARNING,
                f"appraise failed for {source.title[:80]!r}: {type(exc).__name__}",
                {"source_id": source.id},
            )
            return None


def _select(results: list[SourceAppraisal], top_k: int) -> set[str]:
    eligible = sorted((item for item in results if item.eligible), key=lambda item: -item.rank)
    return {item.source_id for item in eligible[:top_k]}


async def _persist(ctx: StageContext, result: SourceAppraisal, promoted: bool) -> None:
    code = result.rejection_code
    explanation = result.explanation
    if not promoted and code is None:
        code = RejectionCode.LOW_RELEVANCE
        explanation = (
            f"Eligible but ranked below the top {ctx.settings.appraise_top_k}. {explanation}"
        )
    await ctx.repositories.update_source_fields(
        result.source_id,
        status=SourceStatus.APPRAISE_PROMOTED if promoted else SourceStatus.APPRAISE_DISCOUNTED,
        m_score=result.m_score,
        directness=result.directness,
        study_design=result.study_design,
        rob2_json=result.rob2_json,
        appraisal_json=result.appraisal_json,
        rejection_code=None if promoted else code,
        decision_explanation=explanation,
    )
    if not promoted:
        return
    for claim in result.claims:
        await ctx.repositories.create_claim(
            ctx.workspace_id,
            kind=claim.kind,
            label=claim.label,
            text=claim.text,
            verdict=claim.verdict,
            source_id=result.source_id,
            quote=claim.quote,
            confidence=claim.confidence,
            payload_json=json.dumps({"outcome": claim.outcome, "arm": claim.arm}),
        )


async def run(ctx: StageContext) -> None:
    decomposition = await _load_decomposition(ctx)
    if decomposition is None:
        await ctx.emit(TraceEventKind.WARNING, "appraise skipped: no decomposition")
        return
    sources = await ctx.repositories.list_sources(ctx.workspace_id, [SourceStatus.SCREEN_PROMOTED])
    await ctx.emit(TraceEventKind.PROGRESS, f"appraising {len(sources)} sources from abstracts")
    limit = asyncio.Semaphore(CONCURRENCY)
    replies = await asyncio.gather(*(_guarded(ctx, limit, decomposition, s) for s in sources))
    results = [result for result in replies if result is not None]
    promoted = _select(results, ctx.settings.appraise_top_k)
    for result in results:
        await _persist(ctx, result, result.source_id in promoted)
    failed = {source.id for source in sources} - {result.source_id for result in results}
    for source_id in failed:
        await ctx.repositories.update_source_fields(
            source_id,
            status=SourceStatus.APPRAISE_DISCOUNTED,
            decision_explanation="Appraisal failed; the model gave no usable answer.",
        )
    await ctx.emit(
        TraceEventKind.DECISION,
        f"appraise kept {len(promoted)} of {len(sources)} sources",
        {"promoted": len(promoted), "discounted": len(sources) - len(promoted)},
    )
