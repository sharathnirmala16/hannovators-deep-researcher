"""Source API (PLAN.md section 5.3).

- GET  /workspaces/{id}/sources/{source_id} -> SourceDetail
- POST /workspaces/{id}/sources/{source_id}/decision (SourceDecisionRequest) -> WorkspaceState
"""

from fastapi import APIRouter, status

from hannovators_deep_researcher.models.contracts import (
    SourceDecisionRequest,
    SourceDetail,
    WorkspaceState,
)
from hannovators_deep_researcher.routers.dependencies import Container
from hannovators_deep_researcher.routers.errors import api_error
from hannovators_deep_researcher.services.source_decisions import (
    SourceDecisionError,
    decide_source,
)

router = APIRouter(prefix="/workspaces", tags=["sources"])


@router.get("/{workspace_id}/sources/{source_id}")
async def get_source(workspace_id: str, source_id: str, container: Container) -> SourceDetail:
    """The source with its abstract, screen/appraisal JSON, chunks, claims, and step IDs."""

    detail = await container.state.source_detail(workspace_id, source_id)
    if detail is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "SOURCE_NOT_FOUND",
            f"source {source_id} not found in workspace {workspace_id}",
        )
    return detail


@router.post("/{workspace_id}/sources/{source_id}/decision")
async def decide(
    workspace_id: str, source_id: str, body: SourceDecisionRequest, container: Container
) -> WorkspaceState:
    """Include or exclude a source by hand (completed runs only; not seeds). The decision is a
    USER_ACTION trajectory step and waits for `POST /resynthesize` to reach the synthesis."""

    try:
        await decide_source(
            container.services.repositories,
            container.services.trajectory,
            workspace_id=workspace_id,
            source_id=source_id,
            body=body,
        )
    except SourceDecisionError as error:
        raise api_error(error.status, error.code, error.message) from error
    return await container.state.build_state(workspace_id)
