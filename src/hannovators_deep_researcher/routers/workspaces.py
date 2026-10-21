"""Workspace lifecycle: list, create, run or continue, review the decomposition, read the state,
delete.

Server-visible user actions record USER_ACTION trajectory steps (PLAN.md section 5.3); a deleted
workspace has no trajectory left, so its deletion is logged instead.
"""

from fastapi import APIRouter, Request, status

from hannovators_deep_researcher.models.contracts import (
    CreateWorkspaceRequest,
    Decomposition,
    WorkspaceSettings,
    WorkspaceState,
    WorkspaceSummary,
    WorkspaceView,
)
from hannovators_deep_researcher.models.enums import StageId, WorkspaceStatus
from hannovators_deep_researcher.routers.deep_research import deep_research_running
from hannovators_deep_researcher.routers.dependencies import Container
from hannovators_deep_researcher.services.source_decisions import pending_decisions
from hannovators_deep_researcher.services.trajectory_wrappers import record_user_action
from hannovators_deep_researcher.services.workspace_deletion import (
    delete_workspace as remove_workspace,
)
from hannovators_deep_researcher.services.workspace_state import (
    parse_decomposition,
    workspace_view,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("")
async def list_workspaces(container: Container) -> list[WorkspaceSummary]:
    """Every workspace, newest first."""

    return await container.state.list_summaries()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_workspace(body: CreateWorkspaceRequest, container: Container) -> WorkspaceView:
    embedder = container.services.embedder
    settings = (body.settings or WorkspaceSettings()).model_copy(
        update={"embedding_model": embedder.model, "embedding_dimensions": embedder.dimensions}
    )
    row = await container.services.repositories.create_workspace(
        research_question=body.research_question,
        domain_mode=body.domain_mode,
        settings=settings,
        auto_continue=body.auto_continue,
    )
    await record_user_action(
        container.services.trajectory,
        row.id,
        "user.workspace.create",
        summary=f"Created workspace ({body.domain_mode})",
        request={**body.model_dump(mode="json"), "settings": settings.model_dump(mode="json")},
    )
    return workspace_view(row)


@router.post("/{workspace_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_workspace(workspace_id: str, container: Container) -> WorkspaceView:
    """Start, or continue from AWAITING_REVIEW. 409 when it is running or finished."""

    before = await container.state.require_workspace(workspace_id)
    start = await container.orchestrator.begin_run(workspace_id)
    continuing = before.status == WorkspaceStatus.AWAITING_REVIEW
    await record_user_action(
        container.services.trajectory,
        workspace_id,
        "user.run.continue" if continuing else "user.run.start",
        summary=f"{'Continued' if continuing else 'Started'} the run at {start}",
        request={"previous_status": before.status, "start_stage": start},
        stage=start,
    )
    container.start_run(workspace_id, start)
    return workspace_view(await container.state.require_workspace(workspace_id))


@router.post("/{workspace_id}/resynthesize", status_code=status.HTTP_202_ACCEPTED)
async def resynthesize(workspace_id: str, container: Container) -> WorkspaceView:
    """Bring researcher decisions into the synthesis: acquire and appraise newly included
    sources, then synthesize, highlight, and compose again. 409 unless the run is COMPLETED."""

    await container.state.require_workspace(workspace_id)
    pending = await pending_decisions(container.services.repositories, workspace_id)
    await container.orchestrator.begin_revision(workspace_id)
    await record_user_action(
        container.services.trajectory,
        workspace_id,
        "user.run.resynthesize",
        summary=f"Re-synthesized with {len(pending)} researcher decision(s)",
        request={
            "decisions": [
                {
                    "source_id": source.id,
                    "title": source.title,
                    "decision": decision.decision,
                    "reason": decision.reason,
                }
                for source, decision in pending
            ]
        },
        source_ids=[source.id for source, _ in pending],
        stage=StageId.SYNTHESIZE,
    )
    container.start_revision(workspace_id)
    return workspace_view(await container.state.require_workspace(workspace_id))


@router.put("/{workspace_id}/decomposition")
async def replace_decomposition(
    workspace_id: str, decomposition: Decomposition, container: Container
) -> WorkspaceState:
    before = parse_decomposition(await container.state.require_workspace(workspace_id))
    state = await container.state.replace_decomposition(workspace_id, decomposition)
    await record_user_action(
        container.services.trajectory,
        workspace_id,
        "user.decomposition.edit",
        summary=f"Edited the {decomposition.mode} decomposition",
        request={
            "before": None if before is None else before.model_dump(mode="json"),
            "after": decomposition.model_dump(mode="json"),
        },
        stage=StageId.DECOMPOSE,
    )
    return state


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str, container: Container) -> WorkspaceState:
    return await container.state.build_state(workspace_id)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace_id: str, request: Request, container: Container) -> None:
    """Delete the workspace, its rows, and its files. 409 while a run or deep research is active."""

    busy = container.run_active(workspace_id) or deep_research_running(request.app, workspace_id)
    await remove_workspace(
        container.services.repositories, workspace_id, busy=busy, root=container.state.data_dir
    )
