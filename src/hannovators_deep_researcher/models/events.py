"""Pipeline trace events, stored in `trace_events` and streamed over SSE."""

from datetime import datetime

from pydantic import Field, JsonValue

from hannovators_deep_researcher.models.base import ContractModel
from hannovators_deep_researcher.models.enums import StageId, TraceEventKind


class TraceEvent(ContractModel):
    """`id` is the `trace_events` autoincrement key and the SSE event ID."""

    id: int
    workspace_id: str
    stage: StageId
    kind: TraceEventKind
    message: str
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: datetime
