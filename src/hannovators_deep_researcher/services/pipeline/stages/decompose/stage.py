"""Decompose: resolve the domain, draft the decomposition, then one critique-and-revise pass.

The orchestrator handles the AWAITING_REVIEW checkpoint after this stage.
"""

from dataclasses import dataclass
from itertools import product

from pydantic import BaseModel

from hannovators_deep_researcher.models.contracts import (
    DECOMPOSITION_ADAPTER,
    InterventionComparisonPair,
    PicotsDecomposition,
)
from hannovators_deep_researcher.models.enums import (
    DomainMode,
    ModelRole,
    RequestedDomainMode,
    SourceStatus,
    TraceEventKind,
)
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.decompose import general, medical
from hannovators_deep_researcher.services.pipeline.stages.decompose.domain import detect_domain
from hannovators_deep_researcher.services.pipeline.stages.decompose.schemas import (
    PicotsDraft,
    PicotsRevision,
    ScopeDraft,
    ScopeRevision,
)

MAX_SEEDS_IN_CONTEXT = 5
MAX_SEED_CHARS = 1_500


@dataclass(frozen=True, slots=True)
class Prompts:
    system: str
    critique: str
    few_shot: str


MEDICAL_PROMPTS = Prompts(medical.SYSTEM, medical.CRITIQUE, medical.FEW_SHOT)
GENERAL_PROMPTS = Prompts(general.SYSTEM, general.CRITIQUE, general.FEW_SHOT)


async def run(ctx: StageContext) -> None:
    workspace = await ctx.repositories.get_workspace(ctx.workspace_id)
    if workspace is None:
        raise LookupError(f"workspace {ctx.workspace_id} not found")
    question = workspace.research_question
    domain = await _resolve_domain(ctx, RequestedDomainMode(workspace.domain_mode), question)
    user = f"Question: {question}{await _seed_context(ctx)}"

    if domain is DomainMode.MEDICAL:
        draft, critique = await _draft_and_revise(
            ctx, MEDICAL_PROMPTS, user, PicotsDraft, PicotsRevision
        )
    else:
        draft, critique = await _draft_and_revise(
            ctx, GENERAL_PROMPTS, user, ScopeDraft, ScopeRevision
        )
    decomposition = DECOMPOSITION_ADAPTER.validate_python(draft.model_dump())
    if isinstance(decomposition, PicotsDecomposition):
        decomposition = complete_ic_pairs(decomposition)

    await ctx.repositories.update_workspace_fields(
        ctx.workspace_id,
        domain_mode=domain,
        decomposition_json=decomposition.model_dump_json(),
    )
    await ctx.emit(
        TraceEventKind.DECISION,
        f"{'PICOTS' if domain is DomainMode.MEDICAL else 'Scope'} decomposition ready for review",
        {"mode": domain, "critique": critique, "decomposition": decomposition.model_dump()},
    )


async def _resolve_domain(
    ctx: StageContext, requested: RequestedDomainMode, question: str
) -> DomainMode:
    if requested is not RequestedDomainMode.AUTO:
        return DomainMode(requested)
    domain, method = await detect_domain(ctx.decisions, question)
    if method != "jev":
        await ctx.emit(TraceEventKind.WARNING, "Domain detection failed; used keyword fallback")
    await ctx.emit(
        TraceEventKind.DECISION,
        f"Domain detected: {domain} (via {method})",
        {"domain": domain, "method": method},
    )
    return domain


async def _seed_context(ctx: StageContext) -> str:
    seeds = await ctx.repositories.list_sources(ctx.workspace_id, [SourceStatus.SEED])
    parts = [
        f"- {seed.title}: {(seed.abstract or '')[:MAX_SEED_CHARS]}"
        for seed in seeds[:MAX_SEEDS_IN_CONTEXT]
    ]
    return "\n\nSeed documents the user supplied:\n" + "\n".join(parts) if parts else ""


async def _draft_and_revise[D: PicotsDraft | ScopeDraft, R: PicotsRevision | ScopeRevision](
    ctx: StageContext, prompts: Prompts, user: str, schema: type[D], revision_schema: type[R]
) -> tuple[BaseModel, list[str]]:
    """Draft, then one critique-and-revise call. A failed revision keeps the draft."""

    await ctx.emit(TraceEventKind.PROGRESS, "Drafting the decomposition")
    draft: BaseModel = await ctx.chat.complete_json(
        role=ModelRole.DECOMPOSE,
        system=prompts.system,
        user=f"{prompts.few_shot}\n\n{user}",
        schema=schema,
    )
    await ctx.emit(TraceEventKind.PROGRESS, "Critiquing and revising the draft")
    try:
        revision = await ctx.chat.complete_json(
            role=ModelRole.DECOMPOSE,
            system=prompts.critique,
            user=f"{user}\n\nDraft:\n{draft.model_dump_json()}",
            schema=revision_schema,
        )
    except Exception as error:
        await ctx.emit(
            TraceEventKind.WARNING,
            f"Self-reflection failed; kept the draft ({type(error).__name__})",
        )
        return draft, []
    return revision.decomposition, revision.critique


def complete_ic_pairs(decomposition: PicotsDecomposition) -> PicotsDecomposition:
    """Pair every intervention with every comparison when the model gave no pairs."""

    if decomposition.ic_pairs or not decomposition.interventions:
        return decomposition
    pairs = [
        InterventionComparisonPair(intervention=intervention, comparison=comparison)
        for intervention, comparison in product(
            decomposition.interventions, decomposition.comparisons
        )
    ]
    return decomposition.model_copy(update={"ic_pairs": pairs})
