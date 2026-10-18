"""Orchestrator checkpoint, resume, and failure capture against a real SQLite database."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import URL

from hannovators_deep_researcher.adapters.fake.chat import FakeChatModel
from hannovators_deep_researcher.adapters.fake.decisions import FakeDecisionModel
from hannovators_deep_researcher.adapters.fake.embeddings import FakeEmbedder
from hannovators_deep_researcher.adapters.fake.literature import FakeLiteratureSearch
from hannovators_deep_researcher.adapters.fake.web import FakeWebSearch
from hannovators_deep_researcher.configuration.settings import Settings
from hannovators_deep_researcher.infrastructure.database import create_database_engine
from hannovators_deep_researcher.models.contracts import WorkspaceSettings
from hannovators_deep_researcher.models.enums import (
    RequestedDomainMode,
    StageId,
    TraceEventKind,
    WorkspaceStatus,
)
from hannovators_deep_researcher.models.events import TraceEvent
from hannovators_deep_researcher.persistence.base import Base
from hannovators_deep_researcher.persistence.repositories import (
    Repositories,
    create_session_factory,
)
from hannovators_deep_researcher.services.events import DatabaseEventSink
from hannovators_deep_researcher.services.pipeline.context import PipelineServices, StageContext
from hannovators_deep_researcher.services.pipeline.orchestrator import Orchestrator


@pytest.fixture
async def services(tmp_path: Path) -> AsyncIterator[PipelineServices]:
    engine = create_database_engine(
        URL.create("sqlite+aiosqlite", database=str(tmp_path / "pipeline.sqlite"))
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    repositories = Repositories(session_factory)
    try:
        yield PipelineServices(
            app_settings=Settings(),
            session_factory=session_factory,
            repositories=repositories,
            chat=FakeChatModel(),
            embedder=FakeEmbedder(),
            decisions=FakeDecisionModel(),
            web=FakeWebSearch(),
            literature=FakeLiteratureSearch(),
            events=DatabaseEventSink(repositories),
        )
    finally:
        await engine.dispose()


async def _create_workspace(services: PipelineServices, *, auto_continue: bool) -> str:
    workspace = await services.repositories.create_workspace(
        research_question="Does drug A reduce mortality?",
        domain_mode=RequestedDomainMode.MEDICAL,
        settings=WorkspaceSettings(),
        auto_continue=auto_continue,
    )
    return workspace.id


def _stages_with(events: list[TraceEvent], kind: TraceEventKind) -> list[StageId]:
    return [event.stage for event in events if event.kind == kind]


@pytest.mark.integration
async def test_run_stops_at_review_checkpoint_and_resumes(services: PipelineServices) -> None:
    """Without auto_continue the run pauses after decompose; the next run continues at search."""

    repositories = services.repositories
    orchestrator = Orchestrator(services)
    workspace_id = await _create_workspace(services, auto_continue=False)

    assert await orchestrator.run(workspace_id) == WorkspaceStatus.AWAITING_REVIEW
    first_pass = await repositories.events_after(workspace_id, None)
    assert _stages_with(first_pass, TraceEventKind.STAGE_STARTED) == [
        StageId.INGEST,
        StageId.DECOMPOSE,
    ]
    workspace = await repositories.get_workspace(workspace_id)
    assert workspace is not None
    assert (workspace.status, workspace.current_stage) == ("AWAITING_REVIEW", "decompose")

    assert await orchestrator.run(workspace_id) == WorkspaceStatus.COMPLETED
    events = await repositories.events_after(workspace_id, None)
    assert events[: len(first_pass)] == first_pass
    assert _stages_with(events, TraceEventKind.STAGE_STARTED) == list(StageId)
    assert _stages_with(events, TraceEventKind.STAGE_COMPLETED) == list(StageId)
    assert [event.payload["status"] for event in events if event.kind == "STATUS"] == [
        "RUNNING",
        "AWAITING_REVIEW",
        "RUNNING",
        "COMPLETED",
    ]

    auto_id = await _create_workspace(services, auto_continue=True)
    assert await orchestrator.run(auto_id) == WorkspaceStatus.COMPLETED
    auto_events = await repositories.events_after(auto_id, None)
    assert _stages_with(auto_events, TraceEventKind.STAGE_COMPLETED) == list(StageId)


@pytest.mark.integration
async def test_stage_exception_fails_run_and_keeps_earlier_events(
    services: PipelineServices,
) -> None:
    """A raising stage sets FAILED, records STAGE_FAILED with the error, and stops the run."""

    async def broken_search(ctx: StageContext) -> None:
        await ctx.emit(TraceEventKind.PROGRESS, "querying")
        raise RuntimeError("provider exploded")

    orchestrator = Orchestrator(services, {StageId.SEARCH: broken_search})
    workspace_id = await _create_workspace(services, auto_continue=True)

    assert await orchestrator.run(workspace_id) == WorkspaceStatus.FAILED

    workspace = await services.repositories.get_workspace(workspace_id)
    assert workspace is not None
    assert workspace.status == WorkspaceStatus.FAILED
    assert workspace.error == "search: RuntimeError: provider exploded"

    events = await services.repositories.events_after(workspace_id, None)
    assert _stages_with(events, TraceEventKind.STAGE_COMPLETED) == [
        StageId.INGEST,
        StageId.DECOMPOSE,
    ]
    assert [(event.stage, event.kind) for event in events[-3:]] == [
        (StageId.SEARCH, TraceEventKind.PROGRESS),
        (StageId.SEARCH, TraceEventKind.STAGE_FAILED),
        (StageId.SEARCH, TraceEventKind.STATUS),
    ]
    assert events[-2].payload == {"error": "RuntimeError: provider exploded"}
    assert events[-1].payload == {"status": "FAILED"}
