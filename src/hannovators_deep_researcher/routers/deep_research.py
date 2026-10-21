"""Tavily deep research API. Owned by lane `research-quality` (PLAN.md section 7.9).

Contract (PLAN.md section 5.3):
- POST /workspaces/{id}/deep-research -> 202 DeepResearchRecord (409 while one is running)
- GET  /workspaces/{id}/deep-research -> DeepResearchRecord (404 when none was started); a
  completed record without a report source gets one here (idempotent backfill)
"""

from fastapi import APIRouter, FastAPI, HTTPException, Request, status

from hannovators_deep_researcher.adapters.tavily_research import build_deep_research
from hannovators_deep_researcher.models.deep_research import DeepResearchRecord
from hannovators_deep_researcher.models.enums import TrajectoryActor, TrajectoryKind
from hannovators_deep_researcher.routers.dependencies import ApiContainer, Container
from hannovators_deep_researcher.routers.errors import api_error
from hannovators_deep_researcher.services.deep_research import (
    DeepResearchRunningError,
    DeepResearchService,
)

router = APIRouter(prefix="/workspaces", tags=["deep-research"])


def _service(app: FastAPI, container: ApiContainer) -> DeepResearchService:
    """One service per app (it tracks the running task per workspace), built on first use."""

    service = getattr(app.state, "deep_research", None)
    if not isinstance(service, DeepResearchService):
        services = container.services
        service = DeepResearchService(
            services=services, provider=build_deep_research(services.app_settings)
        )
        app.state.deep_research = service
    return service


def deep_research_running(app: FastAPI, workspace_id: str) -> bool:
    """True while deep research runs for the workspace (False when none was ever started)."""

    service = getattr(app.state, "deep_research", None)
    return isinstance(service, DeepResearchService) and service.is_running(workspace_id)


@router.post("/{workspace_id}/deep-research", status_code=status.HTTP_202_ACCEPTED)
async def start_deep_research(
    workspace_id: str, request: Request, container: Container
) -> DeepResearchRecord:
    workspace = await container.state.require_workspace(workspace_id)
    service = _service(request.app, container)
    if service.is_running(workspace_id):
        raise _running(workspace_id)
    # Record the user action first, so it precedes the research step in the trajectory.
    await container.services.trajectory.record(
        kind=TrajectoryKind.USER_ACTION,
        name="user.deep_research.start",
        actor=TrajectoryActor.USER,
        workspace_id=workspace_id,
        target=f"/api/workspaces/{workspace_id}/deep-research",
        summary="Started Tavily deep research",
    )
    try:
        return await service.start(workspace)
    except DeepResearchRunningError as error:
        raise _running(workspace_id) from error


def _running(workspace_id: str) -> HTTPException:
    return api_error(
        status.HTTP_409_CONFLICT,
        "DEEP_RESEARCH_RUNNING",
        f"Deep research is already running for workspace {workspace_id}.",
    )


@router.get("/{workspace_id}/deep-research")
async def get_deep_research(
    workspace_id: str, request: Request, container: Container
) -> DeepResearchRecord:
    workspace = await container.state.require_workspace(workspace_id)
    service = _service(request.app, container)
    record = service.read(workspace_id)
    if record is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "DEEP_RESEARCH_NOT_FOUND",
            f"No deep research was started for workspace {workspace_id}.",
        )
    # A report finished before report sources existed becomes a source on first read.
    return await service.ensure_report(workspace, record)
