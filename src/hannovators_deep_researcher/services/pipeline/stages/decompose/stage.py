"""Decompose: resolve the domain, draft the decomposition, then one critique-and-revise pass.

The orchestrator handles the AWAITING_REVIEW checkpoint after this stage.
"""

import json
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
from hannovators_deep_researcher.persistence.tables import SourceRow
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
    """Seed titles plus their summary (from ingest) or abstract, as decomposition context."""

    seeds = await ctx.repositories.list_sources(ctx.workspace_id, [SourceStatus.SEED])
    parts = [seed_line(seed) for seed in seeds[:MAX_SEEDS_IN_CONTEXT]]
    if not parts:
        return ""
    await ctx.emit(
        TraceEventKind.PROGRESS,
        f"Using {len(parts)} seed document(s) as decomposition context",
        {"seed_ids": [seed.id for seed in seeds[:MAX_SEEDS_IN_CONTEXT]]},
    )
    return (
        "\n\nSeed documents the user supplied (use them to pick precise population, "
        "intervention, comparator, and outcome terms; they may also report harms or null "
        "results worth adding as outcomes):\n" + "\n".join(parts)
    )


def seed_line(seed: SourceRow) -> str:
    extra = _extra(seed.extra_json)
    summary = extra.get("seed_summary")
    body = summary if isinstance(summary, str) and summary.strip() else seed.abstract or ""
    design = f" [{seed.study_design}]" if seed.study_design else ""
    return f"- {seed.title}{design}: {body.strip()[:MAX_SEED_CHARS]}"


def _extra(raw: str | None) -> dict[str, object]:
    try:
        value = json.loads(raw) if raw else {}
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


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
    """Keep the model's pairs and pair every comparison no pair covers with each intervention,
    so alternative comparators added by the decomposition are searched and synthesized too."""

    if not decomposition.interventions:
        return decomposition
    covered = {pair.comparison.casefold() for pair in decomposition.ic_pairs}
    missing = [item for item in decomposition.comparisons if item.casefold() not in covered]
    if not missing:
        return decomposition
    pairs = [
        *decomposition.ic_pairs,
        *(
            InterventionComparisonPair(intervention=intervention, comparison=comparison)
            for intervention, comparison in product(decomposition.interventions, missing)
        ),
    ]
    return decomposition.model_copy(update={"ic_pairs": pairs})
