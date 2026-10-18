"""The critical path through the HTTP API in fake mode: create, run, review, continue, complete."""

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import URL

from hannovators_deep_researcher.configuration.settings import ProviderMode, Settings
from hannovators_deep_researcher.infrastructure.database import create_database_engine
from hannovators_deep_researcher.main import create_app
from hannovators_deep_researcher.models.contracts import GraphView, WorkspaceState
from hannovators_deep_researcher.persistence.base import Base
from tests.e2e.sse import Frame, read_sse

PICOTS = {
    "mode": "MEDICAL",
    "population": "Adults with heart failure",
    "interventions": ["SGLT2 inhibitors"],
    "comparisons": ["placebo"],
    "outcomes": ["mortality"],
}


@pytest.fixture
async def app(tmp_path: Path) -> AsyncIterator[FastAPI]:
    database_url = URL.create("sqlite+aiosqlite", database=str(tmp_path / "e2e.sqlite"))
    engine = create_database_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
    application = create_app(
        Settings(provider_mode=ProviderMode.FAKE),
        database_url=database_url,
        files_dir=tmp_path / "workspaces",
    )
    yield application
    await application.state.container.aclose()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


def _status(frame: Frame) -> object:
    if frame.event != "trace" or frame.data is None:
        return None
    event = json.loads(frame.data)
    return event["payload"].get("status") if event["kind"] == "STATUS" else None


def _trace_ids(frames: list[Frame]) -> list[int]:
    return [frame.id for frame in frames if frame.event == "trace" and frame.id is not None]


@pytest.mark.e2e
async def test_offline_run_pauses_for_review_and_completes(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    created = await client.post(
        "/api/workspaces",
        json={"research_question": "Do SGLT2 inhibitors reduce mortality?", "domain_mode": "AUTO"},
    )
    assert created.status_code == 201, created.text
    workspace_id = created.json()["id"]
    base = f"/api/workspaces/{workspace_id}"

    early_edit = await client.put(f"{base}/decomposition", json=PICOTS)
    assert early_edit.status_code == 409
    assert early_edit.json()["detail"]["code"] == "WORKSPACE_NOT_AWAITING_REVIEW"

    assert (await client.post(f"{base}/run")).status_code == 202
    first = await read_sse(
        app, f"{base}/events", until=lambda fs: any(_status(f) == "AWAITING_REVIEW" for f in fs)
    )
    first_ids = _trace_ids(first)
    assert first_ids == sorted(set(first_ids))
    assert (await client.get(base)).json()["workspace"]["status"] == "AWAITING_REVIEW"

    edited = await client.put(f"{base}/decomposition", json=PICOTS)
    assert edited.status_code == 200, edited.text
    assert edited.json()["decomposition"]["population"] == PICOTS["population"]

    assert (await client.post(f"{base}/run")).status_code == 202
    resumed = await read_sse(
        app,
        f"{base}/events",
        headers={"Last-Event-ID": str(first_ids[-1])},
        until=lambda fs: any(f.event == "end" for f in fs),
    )
    resumed_ids = _trace_ids(resumed)
    assert resumed_ids and resumed_ids[0] > first_ids[-1]
    assert resumed_ids == sorted(set(resumed_ids))
    assert [_status(f) for f in resumed if _status(f)] == ["RUNNING", "COMPLETED"]
    assert resumed[-1].event == "end"

    state = WorkspaceState.model_validate((await client.get(base)).json())
    assert state.workspace.status == "COMPLETED"
    assert state.last_event_id == resumed_ids[-1]
    assert state.ui_components[:2] == ["scope_builder", "screening_funnel"]
    assert "evidence_profile_table" not in state.ui_components  # no claims yet

    rerun = await client.post(f"{base}/run")
    assert rerun.status_code == 409
    assert rerun.json()["detail"]["code"] == "WORKSPACE_NOT_RUNNABLE"

    graph = GraphView.model_validate((await client.get(f"{base}/graph")).json())
    assert graph.edges == []

    health = (await client.get("/api/health/providers")).json()
    assert {port["implementation"] for port in health["ports"].values()} == {"fake"}
