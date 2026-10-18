"""SSE trace stream (PLAN.md section 4.6): tails `trace_events` by ID and resumes on reconnect."""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from hannovators_deep_researcher.models.events import TraceEvent
from hannovators_deep_researcher.routers.dependencies import Container
from hannovators_deep_researcher.services.workspace_state import is_terminal_event

router = APIRouter(prefix="/workspaces", tags=["events"])

HEARTBEAT_SECONDS = 15.0
POLL_SECONDS = 0.25
HEARTBEAT_FRAME = ": ping\n\n"
END_FRAME = "event: end\ndata: {}\n\n"
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def trace_frame(event: TraceEvent) -> str:
    return f"id: {event.id}\nevent: trace\ndata: {event.model_dump_json()}\n\n"


def parse_last_event_id(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


async def _stream(
    container: Container, request: Request, workspace_id: str, last_id: int | None
) -> AsyncIterator[str]:
    repositories = container.services.repositories
    beat = time.monotonic()
    while not await request.is_disconnected():
        events = await repositories.events_after(workspace_id, last_id)
        for event in events:
            yield trace_frame(event)
            last_id = event.id
            if is_terminal_event(event):
                yield END_FRAME
                return
        if events:
            beat = time.monotonic()
            continue
        if await container.state.stream_finished(workspace_id, last_id):
            yield END_FRAME
            return
        if time.monotonic() - beat >= HEARTBEAT_SECONDS:
            beat = time.monotonic()
            yield HEARTBEAT_FRAME
        await asyncio.sleep(POLL_SECONDS)


@router.get("/{workspace_id}/events")
async def stream_events(
    workspace_id: str,
    request: Request,
    container: Container,
    last_event_id: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    await container.state.require_workspace(workspace_id)
    stream = _stream(container, request, workspace_id, parse_last_event_id(last_event_id))
    return StreamingResponse(stream, media_type="text/event-stream", headers=SSE_HEADERS)
