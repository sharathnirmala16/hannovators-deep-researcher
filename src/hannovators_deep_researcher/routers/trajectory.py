"""Trajectory (network-tab) API. Owned by lane `platform` (PLAN.md section 7.9).

Contract (PLAN.md section 5.3):
- GET  /workspaces/{id}/trajectory?after=&limit=&kind=&actor=&stage=&outcome=&q= -> TrajectoryPage
- GET  /workspaces/{id}/trajectory/stream  (SSE `event: step`, data = TrajectoryStepSummary JSON,
       `id:` = step id, honors Last-Event-ID, re-sends a step when its status changes)
- GET  /workspaces/{id}/trajectory/{step_id} -> TrajectoryStep
- POST /workspaces/{id}/trajectory/actions (UserActionRequest) -> TrajectoryStepSummary
"""

from fastapi import APIRouter, status

from hannovators_deep_researcher.models.trajectory import (
    TrajectoryPage,
    TrajectoryStep,
    TrajectoryStepSummary,
    UserActionRequest,
)
from hannovators_deep_researcher.routers.errors import api_error

router = APIRouter(prefix="/workspaces", tags=["trajectory"])

_NOT_YET = "The trajectory API is not implemented yet."


@router.get("/{workspace_id}/trajectory")
async def list_trajectory(workspace_id: str) -> TrajectoryPage:
    raise api_error(status.HTTP_501_NOT_IMPLEMENTED, "NOT_IMPLEMENTED", _NOT_YET)


@router.get("/{workspace_id}/trajectory/{step_id}")
async def get_trajectory_step(workspace_id: str, step_id: int) -> TrajectoryStep:
    raise api_error(status.HTTP_501_NOT_IMPLEMENTED, "NOT_IMPLEMENTED", _NOT_YET)


@router.post("/{workspace_id}/trajectory/actions", status_code=status.HTTP_201_CREATED)
async def record_user_action(workspace_id: str, body: UserActionRequest) -> TrajectoryStepSummary:
    raise api_error(status.HTTP_501_NOT_IMPLEMENTED, "NOT_IMPLEMENTED", _NOT_YET)
