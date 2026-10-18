"""What a pipeline stage receives: shared services plus the workspace it works on."""

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from hannovators_deep_researcher.configuration.settings import Settings
from hannovators_deep_researcher.models.contracts import WorkspaceSettings
from hannovators_deep_researcher.models.enums import StageId, TraceEventKind
from hannovators_deep_researcher.models.ports import (
    ChatModel,
    DecisionModel,
    Embedder,
    EventSink,
    LiteratureSearch,
    WebSearch,
)
from hannovators_deep_researcher.persistence.repositories import Repositories


@dataclass(frozen=True)
class PipelineServices:
    """Process-wide dependencies. `main.py` builds one and passes it to the orchestrator."""

    app_settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    repositories: Repositories
    chat: ChatModel
    embedder: Embedder
    decisions: DecisionModel
    web: WebSearch
    literature: LiteratureSearch
    events: EventSink


@dataclass(frozen=True)
class StageContext(PipelineServices):
    """Services plus the workspace, its run settings, and the running stage.

    The orchestrator emits STAGE_STARTED, STAGE_COMPLETED, and STAGE_FAILED. Stages emit only
    PROGRESS, QUERY, DECISION, and WARNING events, through `emit`.
    """

    workspace_id: str
    settings: WorkspaceSettings
    stage: StageId

    async def emit(
        self, kind: TraceEventKind, message: str, payload: Mapping[str, object] | None = None
    ) -> None:
        await self.events.emit(self.workspace_id, self.stage, kind, message, payload)
