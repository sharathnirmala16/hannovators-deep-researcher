"""The process-wide container that `main.py` builds and every router reads."""

import asyncio
import logging
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Annotated, Any, cast

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from hannovators_deep_researcher.configuration.settings import Settings
from hannovators_deep_researcher.models.enums import StageId, WorkspaceStatus
from hannovators_deep_researcher.services.pipeline.context import PipelineServices
from hannovators_deep_researcher.services.pipeline.orchestrator import Orchestrator
from hannovators_deep_researcher.services.workspace_state import WorkspaceStateService

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PortStatus:
    """How one port is wired. `key` is "configured", "missing", or "not_required"."""

    implementation: str
    provider: str
    key: str
    note: str | None = None


@dataclass
class ApiContainer:
    settings: Settings
    engine: AsyncEngine
    http: httpx.AsyncClient
    services: PipelineServices
    orchestrator: Orchestrator
    state: WorkspaceStateService
    providers: dict[str, PortStatus]
    runs: dict[str, asyncio.Task[WorkspaceStatus]] = field(default_factory=dict)

    def start_run(self, workspace_id: str, start: StageId) -> None:
        """Run the orchestrator in the background. `begin_run` must have marked it RUNNING."""

        self._track(workspace_id, self.orchestrator.run_from(workspace_id, start))

    def start_revision(self, workspace_id: str) -> None:
        """Re-synthesize in the background. `begin_revision` must have marked it RUNNING."""

        self._track(workspace_id, self.orchestrator.run_revision(workspace_id))

    def _track(self, workspace_id: str, run: Coroutine[Any, Any, WorkspaceStatus]) -> None:
        task = asyncio.create_task(run)
        self.runs[workspace_id] = task

        def finished(done: asyncio.Task[WorkspaceStatus]) -> None:
            if self.runs.get(workspace_id) is done:
                del self.runs[workspace_id]
            if not done.cancelled() and done.exception() is not None:
                logger.error(
                    "Run for workspace %s crashed", workspace_id, exc_info=done.exception()
                )

        task.add_done_callback(finished)

    async def aclose(self) -> None:
        tasks = list(self.runs.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.http.aclose()
        await self.engine.dispose()


def get_container(request: Request) -> ApiContainer:
    return cast(ApiContainer, request.app.state.container)


Container = Annotated[ApiContainer, Depends(get_container)]
