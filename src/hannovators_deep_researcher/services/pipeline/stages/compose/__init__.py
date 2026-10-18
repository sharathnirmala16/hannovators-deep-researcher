"""Stage `compose`: choose the UI components to show.

Guard-only for now (no Jev request): see `guard.guard_components`.
"""

from hannovators_deep_researcher.models.enums import DomainMode, TraceEventKind
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.compose.guard import (
    AvailableData,
    guard_components,
)
from hannovators_deep_researcher.services.workspace_state import parse_decomposition


async def run(ctx: StageContext) -> None:
    repositories = ctx.repositories
    workspace = await repositories.get_workspace(ctx.workspace_id)
    if workspace is None:
        raise LookupError(f"workspace {ctx.workspace_id} not found")
    decomposition = parse_decomposition(workspace)
    domain = (
        decomposition.mode
        if decomposition
        else DomainMode.__members__.get(workspace.domain_mode, DomainMode.GENERAL)
    )
    components = guard_components(
        AvailableData(
            domain=domain,
            has_sources=bool(await repositories.list_sources(ctx.workspace_id)),
            has_claims=bool(await repositories.list_claims(ctx.workspace_id)),
            has_synthesis=workspace.synthesis_json is not None,
            has_highlights=bool(await repositories.list_highlights(ctx.workspace_id)),
        )
    )
    await repositories.update_workspace_fields(ctx.workspace_id, ui_components_json=components)
    await ctx.emit(
        TraceEventKind.DECISION,
        f"compose: {len(components)} UI components",
        {"ui_components": [str(component) for component in components]},
    )
