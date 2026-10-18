"""Runs the stages in order (PLAN.md section 3) with status changes, the review checkpoint
after `decompose`, resume, and failure capture.

Every status change writes the workspace row first and then a STATUS event with
`{"status": <WorkspaceStatus>}`, so an SSE reader that sees the event can read a matching state.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from types import MappingProxyType

from sqlalchemy import update

from hannovators_deep_researcher.models.contracts import WorkspaceSettings
from hannovators_deep_researcher.models.enums import (
    StageId,
    TraceEventKind,
    TrajectoryActor,
    TrajectoryKind,
    WorkspaceStatus,
)
from hannovators_deep_researcher.persistence.tables import WorkspaceRow
from hannovators_deep_researcher.services.pipeline.context import PipelineServices, StageContext
from hannovators_deep_researcher.services.pipeline.stages import (
    acquire,
    appraise,
    compose,
    decompose,
    highlight,
    ingest,
    screen,
    search,
    synthesize,
)
from hannovators_deep_researcher.services.trajectory import bind

logger = logging.getLogger(__name__)

StageRunner = Callable[[StageContext], Awaitable[None]]

STAGE_ORDER: tuple[StageId, ...] = tuple(StageId)
REVIEW_CHECKPOINT = StageId.DECOMPOSE
RUNNABLE_STATUSES = (WorkspaceStatus.CREATED, WorkspaceStatus.AWAITING_REVIEW)

DEFAULT_STAGES: Mapping[StageId, StageRunner] = MappingProxyType(
    {
        StageId.INGEST: ingest.run,
        StageId.DECOMPOSE: decompose.run,
        StageId.SEARCH: search.run,
        StageId.SCREEN: screen.run,
        StageId.ACQUIRE: acquire.run,
        StageId.APPRAISE: appraise.run,
        StageId.SYNTHESIZE: synthesize.run,
        StageId.HIGHLIGHT: highlight.run,
        StageId.COMPOSE: compose.run,
    }
)


class RunStateError(Exception):
    """The workspace cannot start or continue a run in its current status."""

    def __init__(self, workspace_id: str, status: str) -> None:
        super().__init__(f"workspace {workspace_id} cannot run in status {status}")
        self.workspace_id = workspace_id
        self.status = status


class Orchestrator:
    """One run per call. `stages` overrides individual stage runners (tests, partial pipelines)."""

    def __init__(
        self, services: PipelineServices, stages: Mapping[StageId, StageRunner] | None = None
    ) -> None:
        self._services = services
        self._stages = {**DEFAULT_STAGES, **(stages or {})}

    async def run(self, workspace_id: str) -> WorkspaceStatus:
        """Start or continue a run and return the status it ends in."""

        return await self.run_from(workspace_id, await self.begin_run(workspace_id))

    async def begin_run(self, workspace_id: str) -> StageId:
        """Mark the workspace RUNNING and return the stage to start from.

        Only CREATED (start at `ingest`) and AWAITING_REVIEW (continue after the checkpoint) can
        run. The status check and change are one statement, so two callers cannot both start.
        Raises `LookupError` for an unknown workspace and `RunStateError` for any other status.
        """

        statement = (
            update(WorkspaceRow)
            .where(WorkspaceRow.id == workspace_id, WorkspaceRow.status.in_(RUNNABLE_STATUSES))
            .values(status=WorkspaceStatus.RUNNING, error=None)
            .returning(WorkspaceRow.current_stage)
        )
        async with self._services.repositories.transaction() as session:
            result = (await session.execute(statement)).one_or_none()
            if result is None:
                row = await session.get(WorkspaceRow, workspace_id)
                if row is None:
                    raise LookupError(f"workspace {workspace_id} not found")
                raise RunStateError(workspace_id, row.status)
        current_stage = result[0]
        if current_stage is None:
            return STAGE_ORDER[0]
        return STAGE_ORDER[STAGE_ORDER.index(StageId(current_stage)) + 1]

    async def run_from(self, workspace_id: str, start: StageId) -> WorkspaceStatus:
        """Run `start` and the stages after it for a workspace that `begin_run` marked RUNNING."""

        workspace = await self._services.repositories.get_workspace(workspace_id)
        if workspace is None:
            raise LookupError(f"workspace {workspace_id} not found")
        settings = WorkspaceSettings.model_validate_json(workspace.settings_json)
        await self._emit_status(workspace_id, start, WorkspaceStatus.RUNNING)

        for stage in STAGE_ORDER[STAGE_ORDER.index(start) :]:
            if not await self._run_stage(workspace_id, settings, stage):
                return WorkspaceStatus.FAILED
            if stage == REVIEW_CHECKPOINT and not workspace.auto_continue:
                return await self._set_status(workspace_id, stage, WorkspaceStatus.AWAITING_REVIEW)
        return await self._set_status(workspace_id, STAGE_ORDER[-1], WorkspaceStatus.COMPLETED)

    async def _run_stage(
        self, workspace_id: str, settings: WorkspaceSettings, stage: StageId
    ) -> bool:
        """Run one stage. On an exception, mark the run FAILED and return False."""

        await self._services.repositories.update_workspace_fields(workspace_id, current_stage=stage)
        await self._emit(workspace_id, stage, TraceEventKind.STAGE_STARTED, f"{stage} started")
        context = StageContext(
            **vars(self._services), workspace_id=workspace_id, settings=settings, stage=stage
        )
        try:
            with bind(workspace_id, stage):
                async with self._services.trajectory.step(
                    kind=TrajectoryKind.STAGE,
                    name=f"stage.{stage}",
                    actor=TrajectoryActor.SYSTEM,
                    summary=f"Stage {stage}",
                ):
                    await self._stages[stage](context)
        except asyncio.CancelledError:
            await self._fail(workspace_id, stage, "run cancelled")
            raise
        except Exception as error:
            logger.exception("Stage %s failed for workspace %s", stage, workspace_id)
            await self._fail(workspace_id, stage, f"{type(error).__name__}: {error}")
            return False
        await self._emit(workspace_id, stage, TraceEventKind.STAGE_COMPLETED, f"{stage} completed")
        return True

    async def _fail(self, workspace_id: str, stage: StageId, error: str) -> None:
        await self._services.repositories.update_workspace_fields(
            workspace_id, status=WorkspaceStatus.FAILED, error=f"{stage}: {error}"
        )
        await self._emit(
            workspace_id,
            stage,
            TraceEventKind.STAGE_FAILED,
            f"{stage} failed: {error}",
            {"error": error},
        )
        await self._emit_status(workspace_id, stage, WorkspaceStatus.FAILED)

    async def _set_status(
        self, workspace_id: str, stage: StageId, status: WorkspaceStatus
    ) -> WorkspaceStatus:
        await self._services.repositories.update_workspace_fields(workspace_id, status=status)
        await self._emit_status(workspace_id, stage, status)
        return status

    async def _emit_status(
        self, workspace_id: str, stage: StageId, status: WorkspaceStatus
    ) -> None:
        await self._emit(
            workspace_id, stage, TraceEventKind.STATUS, f"Workspace {status}", {"status": status}
        )

    async def _emit(
        self,
        workspace_id: str,
        stage: StageId,
        kind: TraceEventKind,
        message: str,
        payload: Mapping[str, object] | None = None,
    ) -> None:
        await self._services.events.emit(workspace_id, stage, kind, message, payload)
