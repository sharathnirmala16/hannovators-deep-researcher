"""Stage `decompose`: detect the domain and build the PICOTS or scope decomposition.

Stub until lane S2 fills it in.
"""

from hannovators_deep_researcher.models.enums import TraceEventKind
from hannovators_deep_researcher.services.pipeline.context import StageContext


async def run(ctx: StageContext) -> None:
    await ctx.emit(TraceEventKind.PROGRESS, "decompose: not implemented")
