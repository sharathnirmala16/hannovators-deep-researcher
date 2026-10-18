"""Citation graph of a workspace: sources as nodes, source links as edges."""

from fastapi import APIRouter

from hannovators_deep_researcher.models.contracts import GraphView
from hannovators_deep_researcher.routers.dependencies import Container

router = APIRouter(prefix="/workspaces", tags=["graph"])


@router.get("/{workspace_id}/graph")
async def get_graph(workspace_id: str, container: Container) -> GraphView:
    return await container.state.build_graph(workspace_id)
