"""Stage `search`: run core queries with refinement and store RAW sources.

Stub until lane S3 fills it in.
"""

from hannovators_deep_researcher.models.enums import TraceEventKind
from hannovators_deep_researcher.services.pipeline.context import StageContext


async def run(ctx: StageContext) -> None:
    await ctx.emit(TraceEventKind.PROGRESS, "search: not implemented")
