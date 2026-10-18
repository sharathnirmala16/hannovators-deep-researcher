"""Synthesize APPRAISE_PROMOTED sources into a Synthesis with GRADE and a recommendation."""

import json
from datetime import UTC, datetime
from secrets import token_hex

from hannovators_deep_researcher.configuration.settings import ProviderMode
from hannovators_deep_researcher.models.contracts import (
    PairwiseSummary,
    Provenance,
    Recommendation,
    Synthesis,
)
from hannovators_deep_researcher.models.enums import (
    ClaimKind,
    ClaimVerdict,
    ModelRole,
    RecommendationDirection,
    RecommendationStrength,
    SourceStatus,
    TraceEventKind,
)
from hannovators_deep_researcher.persistence.tables import ClaimRow, SourceRow
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.synthesize.schema import (
    SYSTEM,
    SynthesisDraft,
)

_ABSTRACT_CHARS = 2_500
INSUFFICIENT_EVIDENCE = "Insufficient evidence"


def _provenance(ctx: StageContext) -> Provenance:
    settings = ctx.app_settings
    if settings.provider_mode == ProviderMode.FAKE:
        models = {"agent": "fake", "decisions": "fake", "embeddings": "fake"}
    else:
        models = {
            "appraise": settings.model_for(ModelRole.APPRAISE),
            "synthesize": settings.model_for(ModelRole.SYNTHESIZE),
            "decisions": settings.jev_model,
            "embeddings": settings.embedding_model,
        }
    return Provenance(
        canary=f"hdr-{ctx.workspace_id[:8]}-{token_hex(6)}",
        models=models,
        generated_at=datetime.now(UTC),
    )


def insufficient_evidence(provenance: Provenance) -> Synthesis:
    return Synthesis(
        analysis=f"{INSUFFICIENT_EVIDENCE}: no source passed appraisal.",
        recommendation=Recommendation(
            direction=RecommendationDirection.NONE,
            strength=RecommendationStrength.CONDITIONAL,
            text=f"{INSUFFICIENT_EVIDENCE} to make a recommendation.",
        ),
        provenance=provenance,
    )


def _source_block(label: str, source: SourceRow, claims: list[ClaimRow]) -> str:
    rob = json.loads(source.rob2_json)["overall"] if source.rob2_json else "n/a"
    lines = [
        f"[{label}] {source.title} ({source.year or 'n.d.'})",
        f"design: {source.study_design or 'unknown'}; M: {source.m_score}; "
        f"directness: {source.directness or 'n/a'}; RoB 2 overall: {rob}",
        f"abstract: {(source.abstract or '')[:_ABSTRACT_CHARS]}",
    ]
    lines += [f"- {claim.kind} {claim.label}: {claim.text} [{claim.verdict}]" for claim in claims]
    return "\n".join(lines)


def to_synthesis(
    draft: SynthesisDraft, labels: dict[str, str], provenance: Provenance
) -> Synthesis:
    """Map source labels to IDs, dropping labels that name no promoted source."""

    pairs = [
        PairwiseSummary(
            intervention=pair.intervention,
            comparison=pair.comparison,
            outcome=pair.outcome,
            summary=pair.summary,
            source_ids=list(dict.fromkeys(labels[x] for x in pair.source_labels if x in labels)),
            grade=pair.grade,
        )
        for pair in draft.pairwise_summaries
    ]
    analysis = draft.analysis
    if draft.cost_and_preference_considerations:
        notes = "\n".join(f"- {note}" for note in draft.cost_and_preference_considerations)
        analysis = f"{analysis}\n\nCost and preference considerations (not evidence):\n{notes}"
    return Synthesis(
        pairwise_summaries=pairs,
        analysis=analysis,
        recommendation=draft.recommendation,
        provenance=provenance,
    )


async def build_synthesis(ctx: StageContext) -> Synthesis:
    provenance = _provenance(ctx)
    sources = await ctx.repositories.list_sources(
        ctx.workspace_id, [SourceStatus.APPRAISE_PROMOTED]
    )
    if not sources:
        await ctx.emit(TraceEventKind.WARNING, "no promoted sources; insufficient evidence")
        return insufficient_evidence(provenance)
    workspace = await ctx.repositories.get_workspace(ctx.workspace_id)
    claims = await ctx.repositories.list_claims(ctx.workspace_id)
    labels = {f"S{index}": source.id for index, source in enumerate(sources, start=1)}
    blocks = [
        _source_block(label, source, [claim for claim in claims if claim.source_id == source.id])
        for label, source in zip(labels, sources, strict=True)
    ]
    user = (
        f"Research question: {workspace.research_question if workspace else ''}\n\n"
        f"Decomposition:\n{workspace.decomposition_json if workspace else ''}\n\n"
        "Evidence:\n\n" + "\n\n".join(blocks)
    )
    draft = await ctx.chat.complete_json(
        role=ModelRole.SYNTHESIZE, system=SYSTEM, user=user, schema=SynthesisDraft
    )
    return to_synthesis(draft, labels, provenance)


async def run(ctx: StageContext) -> None:
    synthesis = await build_synthesis(ctx)
    await ctx.repositories.update_workspace_fields(
        ctx.workspace_id, synthesis_json=synthesis.model_dump_json()
    )
    recommendation = synthesis.recommendation
    await ctx.repositories.create_claim(
        ctx.workspace_id,
        kind=ClaimKind.RECOMMENDATION,
        label="Recommendation",
        text=recommendation.text,
        verdict=ClaimVerdict.UNVERIFIED
        if recommendation.direction == RecommendationDirection.NONE
        else ClaimVerdict.SUPPORTED,
        payload_json=json.dumps(
            {"direction": recommendation.direction, "strength": recommendation.strength}
        ),
    )
    await ctx.emit(
        TraceEventKind.DECISION,
        f"synthesis: {recommendation.direction} ({recommendation.strength})",
        {"pairs": len(synthesis.pairwise_summaries), "canary": synthesis.provenance.canary},
    )
