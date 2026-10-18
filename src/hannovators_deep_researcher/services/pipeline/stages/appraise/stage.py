"""Appraise SCREEN_PROMOTED sources from their abstracts and keep the top K.

Eligible sources (M >= threshold, or credible enough in GENERAL) rank by evidence level first,
then by the M-score / RoB 2 (or credibility) rank. A share of K is reserved for opposing, null,
mixed, or alternative evidence, and eligible OPPOSES / NULL_RESULT sources beyond K are kept
too (up to `MAX_EXTRA_OPPOSING`), so disconfirming evidence that meets M is never discarded
for ranking alone. Every decision records one `appraise.verdict` trajectory step.
"""

import asyncio
import json
from dataclasses import dataclass

from hannovators_deep_researcher.models.contracts import (
    DECOMPOSITION_ADAPTER,
    PicotsDecomposition,
    ScopeDecomposition,
)
from hannovators_deep_researcher.models.enums import (
    ClaimVerdict,
    EvidenceLevel,
    EvidenceStance,
    ModelRole,
    RejectionCode,
    SourceStatus,
    TraceEventKind,
    TrajectoryKind,
    VerdictOutcome,
)
from hannovators_deep_researcher.persistence.tables import SourceRow
from hannovators_deep_researcher.services.evidence import (
    evidence_rank,
    is_contrarian,
    is_opposing,
    level_counts,
    level_from_design_text,
    parse_level,
    parse_stance,
)
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.appraise import general, medical
from hannovators_deep_researcher.services.pipeline.stages.appraise.common import SourceAppraisal

CONCURRENCY = 4
_MAX_TEXT_CHARS = 12_000
RESERVE_SHARE = 0.3
MAX_EXTRA_OPPOSING = 3


@dataclass(frozen=True, slots=True)
class Ranked:
    """One appraisal with the final evidence level and stance (screen + appraisal)."""

    result: SourceAppraisal
    level: EvidenceLevel | None
    stance: EvidenceStance | None

    @property
    def order(self) -> tuple[int, float]:
        return evidence_rank(self.level), -self.result.rank


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


def _final_level(source: SourceRow, result: SourceAppraisal) -> EvidenceLevel | None:
    """The screen level, unless it is missing or OTHER and the appraisal knows better."""

    screened = parse_level(source.evidence_level)
    if screened not in (None, EvidenceLevel.OTHER):
        return screened
    appraised = result.evidence_level
    if appraised not in (None, EvidenceLevel.OTHER):
        return appraised
    return level_from_design_text(result.study_design) or screened or appraised


def _final_stance(source: SourceRow, result: SourceAppraisal) -> EvidenceStance | None:
    """The appraisal model reads the whole abstract with reasoning, so its stance wins unless
    it is UNCLEAR."""

    if result.stance not in (None, EvidenceStance.UNCLEAR):
        return result.stance
    return parse_stance(source.stance) or result.stance


def select(items: list[Ranked], top_k: int) -> tuple[list[Ranked], set[str]]:
    """Return the promoted items in rank order and the IDs kept by an opposing-evidence rule."""

    eligible = sorted((item for item in items if item.result.eligible), key=lambda item: item.order)
    reserve = max(1, round(top_k * RESERVE_SHARE)) if top_k >= 2 else 0
    contrarian = sorted(
        (item for item in eligible if is_contrarian(item.stance)),
        key=lambda item: (0 if is_opposing(item.stance) else 1, *item.order),
    )[:reserve]
    chosen_ids = {item.result.source_id for item in contrarian}
    for item in eligible:
        if len(chosen_ids) >= top_k:
            break
        chosen_ids.add(item.result.source_id)
    plain_top = {item.result.source_id for item in eligible[:top_k]}
    extra = [
        item
        for item in eligible
        if is_opposing(item.stance) and item.result.source_id not in chosen_ids
    ][:MAX_EXTRA_OPPOSING]
    chosen_ids |= {item.result.source_id for item in extra}
    promoted = [item for item in eligible if item.result.source_id in chosen_ids]
    return promoted, chosen_ids - plain_top


async def _persist(
    ctx: StageContext, source: SourceRow, item: Ranked, position: int | None, protected: bool
) -> None:
    result = item.result
    promoted = position is not None
    code = result.rejection_code
    explanation = result.explanation
    if not promoted and code is None:
        code = RejectionCode.LOW_RELEVANCE
        explanation = (
            f"Eligible but ranked below the top {ctx.settings.appraise_top_k} "
            f"(evidence level first, then M-score/RoB). {explanation}"
        )
    elif promoted:
        why = " Kept by the opposing-evidence rule." if protected else ""
        explanation = f"Promoted #{position} ({item.level or 'unknown design'}).{why} {explanation}"
    appraisal = json.loads(result.appraisal_json or "{}")
    appraisal |= {
        "appraised_evidence_level": result.evidence_level,
        "appraised_stance": result.stance,
        "screen_evidence_level": source.evidence_level,
        "screen_stance": source.stance,
    }
    await ctx.repositories.update_source_fields(
        result.source_id,
        status=SourceStatus.APPRAISE_PROMOTED if promoted else SourceStatus.APPRAISE_DISCOUNTED,
        m_score=result.m_score,
        directness=result.directness,
        study_design=result.study_design,
        rob2_json=result.rob2_json,
        appraisal_json=appraisal,
        evidence_level=item.level,
        stance=item.stance,
        rejection_code=None if promoted else code,
        decision_explanation=explanation,
    )
    await _verdict(ctx, source, item, promoted, code, explanation, position, protected)
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


async def _verdict(
    ctx: StageContext,
    source: SourceRow,
    item: Ranked,
    promoted: bool,
    code: RejectionCode | None,
    explanation: str,
    position: int | None,
    protected: bool,
) -> None:
    result = item.result
    outcome = VerdictOutcome.KEPT if promoted else VerdictOutcome.REMOVED
    rob = json.loads(result.rob2_json)["overall"] if result.rob2_json else None
    verified = sum(claim.verdict != ClaimVerdict.UNVERIFIED for claim in result.claims)
    await ctx.trajectory.record(
        kind=TrajectoryKind.VERDICT,
        name="appraise.verdict",
        target=source.url or source.external_id,
        summary=f"{outcome}: {source.title[:90]} - {explanation}"[:400],
        request={"title": source.title, "search_intent": source.search_intent},
        response={
            "eligible": result.eligible,
            "m_score": result.m_score,
            "m_threshold": ctx.settings.appraise_m,
            "directness": result.directness,
            "rob2_overall": rob,
            "rank_score": result.rank,
            "evidence_level": item.level,
            "evidence_rank": evidence_rank(item.level),
            "stance": item.stance,
            "position": position,
            "kept_by_opposing_rule": protected,
            "claims": len(result.claims),
            "verified_quotes": verified,
            "rejection_code": None if promoted else code,
            "explanation": explanation,
        },
        source_ids=[source.id],
        outcome=outcome,
        confidence=round(verified / len(result.claims), 3) if result.claims else None,
    )


async def _record_failure(ctx: StageContext, source: SourceRow) -> None:
    explanation = "Appraisal failed; the model gave no usable answer."
    await ctx.repositories.update_source_fields(
        source.id, status=SourceStatus.APPRAISE_DISCOUNTED, decision_explanation=explanation
    )
    await ctx.trajectory.record(
        kind=TrajectoryKind.VERDICT,
        name="appraise.verdict",
        target=source.url or source.external_id,
        summary=f"REMOVED: {source.title[:90]} - {explanation}",
        response={"explanation": explanation, "evidence_level": source.evidence_level},
        source_ids=[source.id],
        outcome=VerdictOutcome.REMOVED,
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
    by_id = {source.id: source for source in sources}
    items = [
        Ranked(
            result,
            _final_level(by_id[result.source_id], result),
            _final_stance(by_id[result.source_id], result),
        )
        for result in replies
        if result is not None
    ]
    promoted, protected = select(items, ctx.settings.appraise_top_k)
    positions = {item.result.source_id: index for index, item in enumerate(promoted, start=1)}
    for item in items:
        source_id = item.result.source_id
        await _persist(
            ctx, by_id[source_id], item, positions.get(source_id), source_id in protected
        )
    for source in sources:
        if all(item.result.source_id != source.id for item in items):
            await _record_failure(ctx, source)
    await ctx.emit(
        TraceEventKind.DECISION,
        f"appraise kept {len(promoted)} of {len(sources)} sources "
        f"({sum(is_contrarian(item.stance) for item in promoted)} opposing, null, mixed, or "
        "alternative)",
        {
            "promoted": len(promoted),
            "discounted": len(sources) - len(promoted),
            "kept_by_opposing_rule": len(protected),
            "promoted_levels": level_counts(item.level for item in promoted),
        },
    )
