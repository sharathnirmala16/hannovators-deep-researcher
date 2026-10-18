"""Trajectory (network-tab) API (PLAN.md section 5.3).

- GET  /workspaces/{id}/trajectory?after=&limit=&kind=&actor=&stage=&outcome=&q= -> TrajectoryPage
- GET  /workspaces/{id}/trajectory/stream -> SSE `event: step` frames of TrajectoryStepSummary
- GET  /workspaces/{id}/trajectory/{step_id} -> TrajectoryStep
- POST /workspaces/{id}/trajectory/actions (UserActionRequest) -> 201 TrajectoryStepSummary

Stream frames for new steps carry `id: <step id>`, so `Last-Event-ID` resumes after it (the
`after` query parameter does the same for the first connection). When a step that was sent as
RUNNING closes, it is sent again as `event: step` without an `id:` line, so the resume cursor
never moves backwards; the step ID is always in the data. A `: ping` comment goes out every 15 s.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import StreamingResponse

from hannovators_deep_researcher.models.enums import (
    StageId,
    TrajectoryActor,
    TrajectoryKind,
    TrajectoryStatus,
    VerdictOutcome,
)
from hannovators_deep_researcher.models.trajectory import (
    TrajectoryPage,
    TrajectoryStep,
    TrajectoryStepSummary,
    UserActionRequest,
)
from hannovators_deep_researcher.routers.dependencies import Container
from hannovators_deep_researcher.routers.errors import api_error
from hannovators_deep_researcher.routers.events import (
    HEARTBEAT_FRAME,
    HEARTBEAT_SECONDS,
    SSE_HEADERS,
    parse_last_event_id,
)
from hannovators_deep_researcher.services.trajectory_wrappers import record_user_action
from hannovators_deep_researcher.services.workspace_state import STREAM_PAGE, TrajectoryFilter

router = APIRouter(prefix="/workspaces", tags=["trajectory"])

DEFAULT_PAGE = 200
MAX_PAGE = 500
STREAM_POLL_SECONDS = 0.5


def step_frame(step: TrajectoryStepSummary, *, with_id: bool) -> str:
    head = f"id: {step.id}\n" if with_id else ""
    return f"{head}event: step\ndata: {step.model_dump_json()}\n\n"


@router.get("/{workspace_id}/trajectory")
async def list_trajectory(
    workspace_id: str,
    container: Container,
    after: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = DEFAULT_PAGE,
    kind: TrajectoryKind | None = None,
    actor: TrajectoryActor | None = None,
    stage: StageId | None = None,
    outcome: VerdictOutcome | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> TrajectoryPage:
    """Steps with `id > after`, oldest first. `total` counts every step matching the filter."""

    filters = TrajectoryFilter(kind=kind, actor=actor, stage=stage, outcome=outcome, q=q or None)
    return await container.state.trajectory_page(workspace_id, filters, after=after, limit=limit)


async def _stream(
    container: Container, request: Request, workspace_id: str, last_id: int | None
) -> AsyncIterator[str]:
    state = container.state
    watching = await state.running_step_ids(workspace_id, last_id) if last_id else set()
    beat = time.monotonic()
    while not await request.is_disconnected():
        steps = await state.steps_after(workspace_id, last_id)
        for step in steps:
            yield step_frame(step, with_id=True)
            last_id = step.id
            if step.status == TrajectoryStatus.RUNNING:
                watching.add(step.id)
        closed = await state.closed_steps(workspace_id, watching)
        for step in closed:
            watching.discard(step.id)
            yield step_frame(step, with_id=False)
        if steps or closed:
            beat = time.monotonic()
            if len(steps) == STREAM_PAGE:
                continue
        elif time.monotonic() - beat >= HEARTBEAT_SECONDS:
            beat = time.monotonic()
            yield HEARTBEAT_FRAME
        await asyncio.sleep(STREAM_POLL_SECONDS)


@router.get("/{workspace_id}/trajectory/stream")
async def stream_trajectory(
    workspace_id: str,
    request: Request,
    container: Container,
    after: Annotated[int | None, Query(ge=0)] = None,
    last_event_id: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    await container.state.require_workspace(workspace_id)
    cursor = parse_last_event_id(last_event_id)
    stream = _stream(container, request, workspace_id, after if cursor is None else cursor)
    return StreamingResponse(stream, media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/{workspace_id}/trajectory/{step_id}")
async def get_trajectory_step(
    workspace_id: str, step_id: int, container: Container
) -> TrajectoryStep:
    step = await container.state.trajectory_step(workspace_id, step_id)
    if step is None:
        raise api_error(
            status.HTTP_404_NOT_FOUND,
            "TRAJECTORY_STEP_NOT_FOUND",
            f"trajectory step {step_id} not found in workspace {workspace_id}",
        )
    return step


@router.post("/{workspace_id}/trajectory/actions", status_code=status.HTTP_201_CREATED)
async def record_action(
    workspace_id: str, body: UserActionRequest, container: Container
) -> TrajectoryStepSummary:
    """Record a UI action the server cannot see (opening a source, following a citation)."""

    await container.state.require_workspace(workspace_id)
    step_id = await record_user_action(
        container.services.trajectory,
        workspace_id,
        body.name,
        summary=body.summary,
        target=body.target,
        request=body.details,
        source_ids=body.source_ids,
    )
    summary = (
        None if step_id is None else await container.state.trajectory_summary(workspace_id, step_id)
    )
    if summary is None:
        raise api_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "TRAJECTORY_RECORD_FAILED",
            "The user action could not be recorded; see the server log.",
        )
    return summary
