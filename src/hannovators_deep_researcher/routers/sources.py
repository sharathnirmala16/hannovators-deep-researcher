"""Source detail API (PLAN.md section 5.3): `GET /workspaces/{id}/sources/{source_id}`."""

from fastapi import APIRouter, status

from hannovators_deep_researcher.models.contracts import SourceDetail
from hannovators_deep_researcher.routers.dependencies import Container
from hannovators_deep_researcher.routers.errors import api_error

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
