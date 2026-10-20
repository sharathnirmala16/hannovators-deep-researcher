"""Live platform checks through the HTTP API: a real recorded run, and seed PDF uploads.

Run with `uv run pytest -m "live and e2e" -k platform`. The run test needs NEBIUS_API_KEY,
JEV_API_KEY, and TAVILY_API_KEY and skips without them. The seed test uses the three PDFs in
`<repo parent>/data/seed_1` (or SEED_PDF_DIR) and skips when the folder is missing.
"""

import asyncio
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
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
RUN_TIMEOUT_SECONDS = 25 * 60
POLL_SECONDS = 3.0
SEED_DIR = Path(
    os.environ.get("SEED_PDF_DIR") or Path(__file__).resolve().parents[3] / "data" / "seed_1"
)


async def _app(tmp_path: Path, settings: Settings) -> FastAPI:
    database_url = URL.create("sqlite+aiosqlite", database=str(tmp_path / "live.sqlite"))
    engine = create_database_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
    return create_app(settings, database_url=database_url, files_dir=tmp_path / "workspaces")


async def _client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", timeout=120
    ) as http:
        yield http
    await app.state.container.aclose()


async def _all_steps(client: httpx.AsyncClient, base: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    after = 0
    while True:
        page = await client.get(f"{base}/trajectory", params={"after": after, "limit": 500})
        assert page.status_code == 200, page.text
        body = page.json()
        steps += body["steps"]
        if body["next_after"] is None:
            return steps
        after = body["next_after"]


async def _wait_for_end(client: httpx.AsyncClient, base: str) -> dict[str, Any]:
    deadline = time.monotonic() + RUN_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        state: dict[str, Any] = (await client.get(base)).json()
        if state["workspace"]["status"] in {"COMPLETED", "FAILED", "AWAITING_REVIEW"}:
            return state
        await asyncio.sleep(POLL_SECONDS)
    pytest.fail(f"run did not finish within {RUN_TIMEOUT_SECONDS} s")


@pytest.fixture
async def live_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(provider_mode=ProviderMode.REAL, run_budget_max_candidates=20)
    missing = [
        name
        for name, value in (
            ("NEBIUS_API_KEY", settings.nebius_api_key),
            ("JEV_API_KEY", settings.jev_api_key),
            ("TAVILY_API_KEY", settings.tavily_api_key),
        )
        if value is None
    ]
    if missing:
        pytest.skip(f"missing {', '.join(missing)}")
    async for client in _client(await _app(tmp_path, settings)):
        yield client


@pytest.fixture
async def seed_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    if not SEED_DIR.is_dir() or len(list(SEED_DIR.glob("*.pdf"))) < 3:
        pytest.skip(f"seed PDFs not found in {SEED_DIR}")
    settings = Settings(provider_mode=ProviderMode.FAKE)
    async for client in _client(await _app(tmp_path, settings)):
        yield client


async def test_live_platform_run_records_a_complete_trajectory(
    live_client: httpx.AsyncClient,
) -> None:
    created = await live_client.post(
        "/api/workspaces",
        json={
            "research_question": QUESTION,
            "domain_mode": "MEDICAL",
            "auto_continue": True,
            "settings": {"screen_top_n": 5, "appraise_top_k": 3, "search_max_rounds": 1},
        },
    )
    assert created.status_code == 201, created.text
    base = f"/api/workspaces/{created.json()['id']}"
    assert (await live_client.post(f"{base}/run")).status_code == 202

    state = await _wait_for_end(live_client, base)
    assert state["workspace"]["status"] == "COMPLETED", state["workspace"]["error"]

    steps = await _all_steps(live_client, base)
    kinds = {step["kind"] for step in steps}
    assert {"STAGE", "LLM", "DECISION", "SEARCH", "USER_ACTION"} <= kinds, kinds
    assert not [step for step in steps if step["status"] == "RUNNING"]
    names = {step["name"] for step in steps}
    assert {"user.workspace.create", "user.run.start", "jev.evaluate"} <= names

    llm = next(step for step in steps if step["kind"] == "LLM" and step["status"] == "OK")
    detail = (await live_client.get(f"{base}/trajectory/{llm['id']}")).json()
    assert detail["request"]["system"] and detail["response"]
    filtered = (await live_client.get(f"{base}/trajectory", params={"kind": "DECISION"})).json()
    assert filtered["total"] > 0
    assert {step["kind"] for step in filtered["steps"]} == {"DECISION"}

    verdicts = [step for step in steps if step["kind"] == "VERDICT"]
    assert verdicts, "the stages recorded no VERDICT steps"
    removed = {
        source_id
        for step in verdicts
        if step["outcome"] == "REMOVED"
        for source_id in step["source_ids"]
    }
    discounted = {
        source["id"] for source in state["sources"] if source["status"] == "SCREEN_DISCOUNTED"
    }
    assert discounted <= removed, discounted - removed


async def test_live_platform_seed_upload_creates_seed_sources(
    seed_client: httpx.AsyncClient, tmp_path: Path
) -> None:
    created = await seed_client.post(
        "/api/workspaces", json={"research_question": "SGLT2 inhibitors in advanced CKD"}
    )
    base = f"/api/workspaces/{created.json()['id']}"
    pdfs = sorted(SEED_DIR.glob("*.pdf"))[:3]
    files = [("files", (pdf.name, pdf.read_bytes(), "application/pdf")) for pdf in pdfs]

    uploaded = await seed_client.post(f"{base}/seeds", files=files)
    assert uploaded.status_code == 201, uploaded.text
    sources = uploaded.json()
    assert len({source["id"] for source in sources}) == 3
    for source in sources:
        assert source["origin"] == "SEED" and source["status"] == "SEED"
        assert source["title"] and source["external_id"].startswith("sha256:")
        assert (tmp_path / source["raw_url"].removeprefix("/files/")).is_file()

    again = await seed_client.post(f"{base}/seeds", files=files[:1])
    assert again.json()[0]["id"] == sources[0]["id"]
    rejected = await seed_client.post(
        f"{base}/seeds", files=[("files", ("notes.txt", b"plain text", "text/plain"))]
    )
    assert rejected.status_code == 415

    detail = (await seed_client.get(f"{base}/sources/{sources[0]['id']}")).json()
    assert detail["pdf_url"] == sources[0]["raw_url"]
    uploads = (
        await seed_client.get(
            f"{base}/trajectory", params={"kind": "USER_ACTION", "q": "user.seed.upload"}
        )
    ).json()
    assert uploads["total"] == 2
    assert {source["id"] for source in sources} <= set(uploads["steps"][0]["source_ids"])
    assert uploads["steps"][0]["id"] in detail["trajectory_step_ids"]
    listed = (await seed_client.get("/api/workspaces")).json()
    assert listed[0]["seed_count"] == 3
