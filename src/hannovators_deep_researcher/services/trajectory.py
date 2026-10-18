"""Trajectory recorder: one auditable row per agent or user action (the network-tab view).

The orchestrator binds the workspace and stage with `bind()`. Port wrappers, stages, routers,
and services then call `record()` (a finished action) or `async with step(...)` (an action
with a duration; nested steps get it as their parent). Recording never breaks the caller:
database errors are logged and swallowed. Without a bound or explicit workspace, nothing is
recorded.
"""

import json
import logging
import time
from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic_core import to_jsonable_python

from hannovators_deep_researcher.models.enums import (
    StageId,
    TrajectoryActor,
    TrajectoryKind,
    TrajectoryStatus,
    VerdictOutcome,
)
from hannovators_deep_researcher.models.trajectory import TrajectoryStep, TrajectoryStepSummary
from hannovators_deep_researcher.persistence.repositories import Repositories
from hannovators_deep_researcher.persistence.tables import TrajectoryStepRow

logger = logging.getLogger(__name__)

MAX_TEXT = 20_000
"""Longest string kept in a request or response body; longer strings are truncated."""

_workspace: ContextVar[str | None] = ContextVar("trajectory_workspace", default=None)
_stage: ContextVar[StageId | None] = ContextVar("trajectory_stage", default=None)
_parent: ContextVar[int | None] = ContextVar("trajectory_parent", default=None)


@contextmanager
def bind(workspace_id: str, stage: StageId | None = None) -> Iterator[None]:
    """Attribute every step recorded inside this block to `workspace_id` and `stage`."""

    tokens = (_workspace.set(workspace_id), _stage.set(stage), _parent.set(None))
    try:
        yield
    finally:
        _parent.reset(tokens[2])
        _stage.reset(tokens[1])
        _workspace.reset(tokens[0])


def current_workspace() -> str | None:
    return _workspace.get()


def current_stage() -> StageId | None:
    return _stage.get()


def compact(value: object) -> object:
    """JSON-safe copy of `value` with long strings truncated to `MAX_TEXT` characters."""

    plain = to_jsonable_python(value, fallback=str)
    return _truncate(plain)


def _truncate(value: object) -> object:
    if isinstance(value, str) and len(value) > MAX_TEXT:
        return f"{value[:MAX_TEXT]}... [truncated {len(value) - MAX_TEXT} chars]"
    if isinstance(value, list):
        return [_truncate(item) for item in value]
    if isinstance(value, dict):
        return {key: _truncate(item) for key, item in value.items()}
    return value


def _dump(value: Mapping[str, object] | None) -> str | None:
    return None if value is None else json.dumps(compact(dict(value)))


@dataclass
class StepHandle:
    """Mutable result of an open `step()`. Set fields before the block ends."""

    id: int | None
    response: dict[str, object] = field(default_factory=dict)
    summary: str | None = None
    source_ids: list[str] | None = None
    outcome: VerdictOutcome | None = None
    confidence: float | None = None
    status: TrajectoryStatus | None = None


def to_summary(row: TrajectoryStepRow) -> TrajectoryStepSummary:
    return TrajectoryStepSummary.model_validate(_summary_fields(row))


def to_step(row: TrajectoryStepRow) -> TrajectoryStep:
    return TrajectoryStep.model_validate(
        {
            **_summary_fields(row),
            "request": json.loads(row.request_json) if row.request_json else {},
            "response": json.loads(row.response_json) if row.response_json else {},
        }
    )


def _summary_fields(row: TrajectoryStepRow) -> dict[str, object]:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "parent_id": row.parent_id,
        "actor": row.actor,
        "kind": row.kind,
        "stage": row.stage,
        "name": row.name,
        "target": row.target,
        "status": row.status,
        "started_at": row.started_at,
        "ended_at": row.ended_at,
        "duration_ms": row.duration_ms,
        "summary": row.summary,
        "source_ids": json.loads(row.source_ids_json or "[]"),
        "outcome": row.outcome,
        "confidence": row.confidence,
        "error": row.error,
    }


class TrajectoryRecorder:
    def __init__(self, repositories: Repositories) -> None:
        self._repositories = repositories

    async def record(
        self,
        *,
        kind: TrajectoryKind,
        name: str,
        actor: TrajectoryActor = TrajectoryActor.AGENT,
        workspace_id: str | None = None,
        stage: StageId | None = None,
        target: str | None = None,
        status: TrajectoryStatus = TrajectoryStatus.OK,
        summary: str = "",
        request: Mapping[str, object] | None = None,
        response: Mapping[str, object] | None = None,
        source_ids: Sequence[str] = (),
        outcome: VerdictOutcome | None = None,
        confidence: float | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
    ) -> int | None:
        """Record a finished action and return its step ID (None when nothing was recorded)."""

        workspace = workspace_id or _workspace.get()
        if workspace is None:
            return None
        now = datetime.now(UTC)
        try:
            row = await self._repositories.add_trajectory_step(
                workspace_id=workspace,
                parent_id=_parent.get(),
                actor=actor,
                kind=kind,
                stage=stage or _stage.get(),
                name=name[:128],
                target=target,
                status=status,
                started_at=now,
                ended_at=now,
                duration_ms=duration_ms,
                summary=summary,
                request_json=_dump(request),
                response_json=_dump(response),
                source_ids_json=json.dumps(list(source_ids)),
                outcome=outcome,
                confidence=confidence,
                error=error,
            )
        except Exception:
            logger.exception("Could not record trajectory step %s", name)
            return None
        return row.id

    @asynccontextmanager
    async def step(
        self,
        *,
        kind: TrajectoryKind,
        name: str,
        actor: TrajectoryActor = TrajectoryActor.AGENT,
        workspace_id: str | None = None,
        target: str | None = None,
        summary: str = "",
        request: Mapping[str, object] | None = None,
        source_ids: Sequence[str] = (),
    ) -> AsyncIterator[StepHandle]:
        """Record a RUNNING row, run the block, then close it as OK or ERROR (and re-raise)."""

        handle = StepHandle(id=None)
        workspace = workspace_id or _workspace.get()
        started = time.perf_counter()
        if workspace is not None:
            try:
                row = await self._repositories.add_trajectory_step(
                    workspace_id=workspace,
                    parent_id=_parent.get(),
                    actor=actor,
                    kind=kind,
                    stage=_stage.get(),
                    name=name[:128],
                    target=target,
                    status=TrajectoryStatus.RUNNING,
                    started_at=datetime.now(UTC),
                    summary=summary,
                    request_json=_dump(request),
                    source_ids_json=json.dumps(list(source_ids)),
                )
                handle.id = row.id
            except Exception:
                logger.exception("Could not open trajectory step %s", name)
        token = _parent.set(handle.id) if handle.id is not None else None
        error: BaseException | None = None
        try:
            yield handle
        except BaseException as caught:
            error = caught
            raise
        finally:
            if token is not None:
                _parent.reset(token)
            await self._close(handle, summary, started, error)

    async def _close(
        self, handle: StepHandle, summary: str, started: float, error: BaseException | None
    ) -> None:
        if handle.id is None:
            return
        status = handle.status or (TrajectoryStatus.ERROR if error else TrajectoryStatus.OK)
        fields: dict[str, object] = {
            "status": status,
            "ended_at": datetime.now(UTC),
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "summary": handle.summary if handle.summary is not None else summary,
            "response_json": _dump(handle.response) if handle.response else None,
            "outcome": handle.outcome,
            "confidence": handle.confidence,
            "error": f"{type(error).__name__}: {error}" if error else None,
        }
        if handle.source_ids is not None:
            fields["source_ids_json"] = json.dumps(handle.source_ids)
        try:
            await self._repositories.update_trajectory_step(handle.id, **fields)
        except Exception:
            logger.exception("Could not close trajectory step %s", handle.id)
