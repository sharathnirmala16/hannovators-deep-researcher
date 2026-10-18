"""Stage `synthesize`: write the staged synthesis with GRADE and provenance.

Stub until lane S7 fills it in.
"""

from hannovators_deep_researcher.models.enums import TraceEventKind
from hannovators_deep_researcher.services.pipeline.context import StageContext


async def run(ctx: StageContext) -> None:
    await ctx.emit(TraceEventKind.PROGRESS, "synthesize: not implemented")
