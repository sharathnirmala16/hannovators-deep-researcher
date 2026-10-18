"""Stage `appraise`: appraise promoted sources and extract claims with quotes.

Stub until lane S6 fills it in.
"""

from hannovators_deep_researcher.models.enums import TraceEventKind
from hannovators_deep_researcher.services.pipeline.context import StageContext


async def run(ctx: StageContext) -> None:
    await ctx.emit(TraceEventKind.PROGRESS, "appraise: not implemented")
