"""The critical path through the HTTP API in fake mode: create, run, review, continue, complete,
with the round-2 research-quality checks (search intents, evidence levels, verdicts) and Tavily
deep research on the fake provider."""

import asyncio
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


async def _assert_research_quality(
    client: httpx.AsyncClient, base: str, state: WorkspaceState
) -> None:
    """Round 2: search intents, evidence level and stance, and one verdict per decision."""

    searched = [source for source in state.sources if source.status != "SEED"]
    assert searched and all(source.search_intent for source in searched)
    queried = {query.applied_filters.split()[0] for query in state.queries}
    assert {"intent:CORE", "intent:NEGATIVE", "intent:ALTERNATIVE", "intent:SAFETY"} <= queried
    screened = [source for source in searched if source.status != "RAW"]
    assert all(source.evidence_level and source.stance for source in screened)

    page = (await client.get(f"{base}/trajectory", params={"kind": "VERDICT", "limit": 500})).json()
    verdicts: dict[str, set[str]] = {}
    for step in page["steps"]:
        for source_id in step["source_ids"]:
            verdicts.setdefault(step["name"], set()).add(f"{source_id}:{step['outcome']}")
    discounted = {s.id for s in screened if s.status == "SCREEN_DISCOUNTED"}
    assert {f"{source_id}:REMOVED" for source_id in discounted} <= verdicts["screen.verdict"]
    appraised = {s.id for s in screened if s.status.startswith("APPRAISE_")}
    assert appraised <= {item.split(":")[0] for item in verdicts["appraise.verdict"]}


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
    assert state.funnel.screen_promoted > 0
    assert state.claims
    assert state.synthesis is not None
    assert state.synthesis.pairwise_summaries
    assert "evidence_profile_table" in state.ui_components
    assert "claim_matrix" not in state.ui_components
    await _assert_research_quality(client, base, state)

    rerun = await client.post(f"{base}/run")
    assert rerun.status_code == 409
    assert rerun.json()["detail"]["code"] == "WORKSPACE_NOT_RUNNABLE"

    graph = GraphView.model_validate((await client.get(f"{base}/graph")).json())
    node_ids = {node.id for node in graph.nodes}
    assert all({edge.source, edge.target} <= node_ids for edge in graph.edges)

    health = (await client.get("/api/health/providers")).json()
    assert {port["implementation"] for port in health["ports"].values()} == {"fake"}


@pytest.mark.e2e
async def test_offline_deep_research_adds_cited_web_sources(client: httpx.AsyncClient) -> None:
    created = await client.post(
        "/api/workspaces", json={"research_question": "Do SGLT2 inhibitors reduce mortality?"}
    )
    base = f"/api/workspaces/{created.json()['id']}"
    assert (await client.get(f"{base}/deep-research")).status_code == 404

    started = await client.post(f"{base}/deep-research")
    assert started.status_code == 202, started.text
    record = started.json()
    for _ in range(100):
        if record["status"] not in {"pending", "running"}:
            break
        await asyncio.sleep(0.05)
        record = (await client.get(f"{base}/deep-research")).json()

    assert record["status"] == "completed", record
    cited = {source["source_id"] for source in record["sources"]}
    web = {
        source["id"]: source
        for source in (await client.get(base)).json()["sources"]
        if source["origin"] == "WEB"
    }
    assert cited and cited <= set(web)
    assert {web[source_id]["search_intent"] for source_id in cited} == {"DEEP_RESEARCH"}

    # The report itself is one RAW source with its markdown snapshot; reads are idempotent.
    report_id = record["report_source_id"]
    assert report_id in web and report_id not in cited
    assert web[report_id]["status"] == "RAW"
    assert web[report_id]["raw_url"].endswith("/snapshot.md")
    again = (await client.get(f"{base}/deep-research")).json()
    assert again["report_source_id"] == report_id
    sources = (await client.get(base)).json()["sources"]
    assert sum(source["id"] == report_id for source in sources) == 1
