"""Stage `ingest`: resolve seed PDFs, PMIDs, DOIs, and URLs into sources and chunks.

Stub until lane S1 fills it in.
"""

from hannovators_deep_researcher.models.enums import TraceEventKind
from hannovators_deep_researcher.services.pipeline.context import StageContext


async def run(ctx: StageContext) -> None:
    await ctx.emit(TraceEventKind.PROGRESS, "ingest: not implemented")
