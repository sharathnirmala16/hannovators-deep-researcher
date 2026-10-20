"""Re-synthesis after researcher decisions.

A revision runs `acquire`, `appraise`, `synthesize`, `highlight`, and `compose` again, but the
first two only touch sources the researcher included since the last synthesis, and appraisal
cannot undo the inclusion. Excluded sources already left the synthesis inputs through their
status. Synthesis replaces the old recommendation claim instead of adding a second one.
"""

from collections.abc import Mapping
from types import MappingProxyType

from hannovators_deep_researcher.models.enums import StageId
from hannovators_deep_researcher.persistence.queries.decisions import (
    delete_recommendation_claims,
)
from hannovators_deep_researcher.services.pipeline.context import StageContext, StageRunner
from hannovators_deep_researcher.services.pipeline.stages import compose, synthesize
from hannovators_deep_researcher.services.pipeline.stages.acquire.stage import acquire_included
from hannovators_deep_researcher.services.pipeline.stages.appraise.stage import (
    appraise_included,
)
from hannovators_deep_researcher.services.pipeline.stages.highlight.stage import (
    highlight_included,
)
from hannovators_deep_researcher.services.source_decisions import pending_includes

REVISION_STAGES: tuple[StageId, ...] = (
    StageId.ACQUIRE,
    StageId.APPRAISE,
    StageId.SYNTHESIZE,
    StageId.HIGHLIGHT,
    StageId.COMPOSE,
)


async def _acquire(ctx: StageContext) -> None:
    await acquire_included(ctx, await pending_includes(ctx.repositories, ctx.workspace_id))


async def _appraise(ctx: StageContext) -> None:
    await appraise_included(ctx, await pending_includes(ctx.repositories, ctx.workspace_id))


async def _synthesize(ctx: StageContext) -> None:
    await delete_recommendation_claims(ctx.repositories, ctx.workspace_id)
    await synthesize.run(ctx)


async def _highlight(ctx: StageContext) -> None:
    included = await pending_includes(ctx.repositories, ctx.workspace_id)
    await highlight_included(ctx, [source.id for source in included if not source.highlighted_path])


REVISION_RUNNERS: Mapping[StageId, StageRunner] = MappingProxyType(
    {
        StageId.ACQUIRE: _acquire,
        StageId.APPRAISE: _appraise,
        StageId.SYNTHESIZE: _synthesize,
        StageId.HIGHLIGHT: _highlight,
        StageId.COMPOSE: compose.run,
    }
)
