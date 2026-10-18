"""Database-backed `EventSink`: every trace event becomes a `trace_events` row."""

from collections.abc import Mapping

from hannovators_deep_researcher.models.enums import StageId, TraceEventKind
from hannovators_deep_researcher.persistence.repositories import Repositories


class DatabaseEventSink:
    """Stores events so the SSE stream can tail them by ID and survive reconnects."""

    def __init__(self, repositories: Repositories) -> None:
        self._repositories = repositories

    async def emit(
        self,
        workspace_id: str,
        stage: StageId,
        kind: TraceEventKind,
        message: str,
        payload: Mapping[str, object] | None = None,
    ) -> None:
        await self._repositories.append_event(workspace_id, stage, kind, message, payload)
