"""Live research-quality checks through the HTTP API: one small real run and one Tavily deep
research report.

Run with `uv run pytest -m live tests/e2e/test_live_research_quality.py`. The run needs
NEBIUS_API_KEY, JEV_API_KEY, and TAVILY_API_KEY; deep research needs TAVILY_API_KEY. Each test
skips when a key is missing.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy import URL

from hannovators_deep_researcher.configuration.settings import ProviderMode, Settings
from hannovators_deep_researcher.infrastructure.database import create_database_engine
from hannovators_deep_researcher.main import create_app
from hannovators_deep_researcher.persistence.base import Base

pytestmark = [pytest.mark.live, pytest.mark.e2e]

QUESTION = (
    "In adults with heart failure with reduced ejection fraction, do SGLT2 inhibitors "
    "reduce hospitalization for heart failure compared with placebo?"
)
SMALL_RUN = {"screen_top_n": 5, "appraise_top_k": 3, "search_max_rounds": 1}
RUN_TIMEOUT_SECONDS = 20 * 60
DEEP_RESEARCH_TIMEOUT_SECONDS = 6 * 60
POLL_SECONDS = 3.0
DISCONFIRMING = {"NEGATIVE", "ALTERNATIVE", "SAFETY"}


def _require(settings: Settings, *names: str) -> None:
    missing = [
        name
        for name in names
        if not isinstance(getattr(settings, name.lower()), SecretStr)
        or not getattr(settings, name.lower()).get_secret_value()
    ]
    if missing:
        pytest.skip(f"missing {', '.join(missing)}")


async def _client(tmp_path: Path, settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    database_url = URL.create("sqlite+aiosqlite", database=str(tmp_path / "live.sqlite"))
    engine = create_database_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
    app: FastAPI = create_app(settings, database_url=database_url, files_dir=tmp_path / "ws")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", timeout=120
    ) as http:
        yield http
    await app.state.container.aclose()


@pytest.fixture
async def run_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(provider_mode=ProviderMode.REAL, run_budget_max_candidates=25)
    _require(settings, "NEBIUS_API_KEY", "JEV_API_KEY", "TAVILY_API_KEY")
    async for client in _client(tmp_path, settings):
        yield client


@pytest.fixture
async def research_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(provider_mode=ProviderMode.REAL)
    _require(settings, "TAVILY_API_KEY")
    async for client in _client(tmp_path, settings):
        yield client


async def _steps(client: httpx.AsyncClient, base: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    after = 0
    while True:
        body = (
            await client.get(f"{base}/trajectory", params={"after": after, "limit": 500})
        ).json()
        steps += body["steps"]
        if body["next_after"] is None:
            return steps
        after = body["next_after"]


async def _finished_state(client: httpx.AsyncClient, base: str) -> dict[str, Any]:
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        state: dict[str, Any] = (await client.get(base)).json()
        if state["workspace"]["status"] in {"COMPLETED", "FAILED", "AWAITING_REVIEW"}:
            return state
        await asyncio.sleep(POLL_SECONDS)
    pytest.fail(f"run did not finish within {RUN_TIMEOUT_SECONDS} s")


async def test_live_run_searches_every_intent_and_grades_the_evidence(
    run_client: httpx.AsyncClient,
) -> None:
    created = await run_client.post(
        "/api/workspaces",
        json={
            "research_question": QUESTION,
            "domain_mode": "MEDICAL",
            "auto_continue": True,
            "settings": SMALL_RUN,
        },
    )
    assert created.status_code == 201, created.text
    base = f"/api/workspaces/{created.json()['id']}"
    assert (await run_client.post(f"{base}/run")).status_code == 202

    state = await _finished_state(run_client, base)
    assert state["workspace"]["status"] == "COMPLETED", state["workspace"]["error"]

    searched = [source for source in state["sources"] if source["status"] != "SEED"]
    assert searched
    assert [s["title"] for s in searched if not s["search_intent"]] == []
    ran = {
        query["applied_filters"].split()[0].removeprefix("intent:") for query in state["queries"]
    }
    assert "CORE" in ran and ran & DISCONFIRMING, ran
    screened = [source for source in searched if source["status"] != "RAW"]
    assert all(source["evidence_level"] and source["stance"] for source in screened)

    steps = await _steps(run_client, base)
    screen_verdicts = {
        source_id
        for step in steps
        if step["kind"] == "VERDICT" and step["name"] == "screen.verdict"
        for source_id in step["source_ids"]
    }
    assert {source["id"] for source in screened} <= screen_verdicts
    removed = {
        source_id
        for step in steps
        if step["kind"] == "VERDICT" and step["outcome"] == "REMOVED"
        for source_id in step["source_ids"]
    }
    assert {s["id"] for s in screened if s["status"] == "SCREEN_DISCOUNTED"} <= removed

    evidence_claims = [claim for claim in state["claims"] if claim["kind"] in {"METRIC", "CLAIM"}]
    assert evidence_claims, "appraise produced no METRIC or CLAIM rows"
    assert state["synthesis"] and state["synthesis"]["pairwise_summaries"]

    throttled = [
        step
        for step in steps
        if step["name"].startswith("pubmed.")
        and step["status"] == "ERROR"
        and "429" in (step["error"] or "")
    ]
    assert throttled == []


async def test_live_deep_research_adds_cited_urls_as_web_sources(
    research_client: httpx.AsyncClient,
) -> None:
    created = await research_client.post(
        "/api/workspaces", json={"research_question": QUESTION, "domain_mode": "MEDICAL"}
    )
    base = f"/api/workspaces/{created.json()['id']}"
    assert (await research_client.get(f"{base}/deep-research")).status_code == 404

    started = await research_client.post(f"{base}/deep-research")
    assert started.status_code == 202, started.text
    assert started.json()["status"] == "running"
    again = await research_client.post(f"{base}/deep-research")
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "DEEP_RESEARCH_RUNNING"

    deadline = time.monotonic() + DEEP_RESEARCH_TIMEOUT_SECONDS
    record: dict[str, Any] = started.json()
    while record["status"] in {"pending", "running"} and time.monotonic() < deadline:
        await asyncio.sleep(POLL_SECONDS)
        record = (await research_client.get(f"{base}/deep-research")).json()

    assert record["status"] == "completed", record.get("error")
    assert record["content"] and record["sources"]
    web = {
        source["id"]: source
        for source in (await research_client.get(base)).json()["sources"]
        if source["origin"] == "WEB"
    }
    cited = [source["source_id"] for source in record["sources"] if source["source_id"]]
    assert cited and set(cited) <= set(web)
    assert {web[source_id]["search_intent"] for source_id in cited} == {"DEEP_RESEARCH"}
