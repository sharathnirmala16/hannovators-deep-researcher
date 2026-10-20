"""Live check of researcher decisions: include and exclude sources by hand, then re-synthesize.

Run with `uv run pytest -m "live and e2e" -k source_decisions`. Needs NEBIUS_API_KEY,
JEV_API_KEY, and TAVILY_API_KEY and skips without them.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
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
TIMEOUT_SECONDS = 25 * 60
POLL_SECONDS = 3.0
INCLUDE_REASON = "Relevant trial population; the ranking cut-off is too strict here."
EXCLUDE_REASON = "Outcome does not match the review question."


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
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
    database_url = URL.create("sqlite+aiosqlite", database=str(tmp_path / "live.sqlite"))
    engine = create_database_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
    app = create_app(settings, database_url=database_url, files_dir=tmp_path / "workspaces")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", timeout=120
    ) as http:
        yield http
    await app.state.container.aclose()


async def _completed(client: httpx.AsyncClient, base: str) -> dict[str, Any]:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        state: dict[str, Any] = (await client.get(base)).json()
        if state["workspace"]["status"] in {"COMPLETED", "FAILED"}:
            assert state["workspace"]["status"] == "COMPLETED", state["workspace"]["error"]
            return state
        await asyncio.sleep(POLL_SECONDS)
    pytest.fail(f"the run did not finish within {TIMEOUT_SECONDS} s")


async def _user_steps(client: httpx.AsyncClient, base: str) -> list[dict[str, Any]]:
    page = await client.get(f"{base}/trajectory", params={"actor": "USER", "limit": 500})
    assert page.status_code == 200, page.text
    steps: list[dict[str, Any]] = page.json()["steps"]
    return steps


async def test_live_source_decisions_reach_the_synthesis(client: httpx.AsyncClient) -> None:
    created = await client.post(
        "/api/workspaces",
        json={
            "research_question": QUESTION,
            "domain_mode": "MEDICAL",
            "auto_continue": True,
            "settings": {"screen_top_n": 5, "appraise_top_k": 2, "search_max_rounds": 1},
        },
    )
    assert created.status_code == 201, created.text
    base = f"/api/workspaces/{created.json()['id']}"
    assert (await client.post(f"{base}/run")).status_code == 202
    state = await _completed(client, base)

    sources = state["sources"]
    dropped = next(
        s for s in sources if s["status"] in {"APPRAISE_DISCOUNTED", "SCREEN_DISCOUNTED"}
    )
    kept = next(s for s in sources if s["status"] == "APPRAISE_PROMOTED")
    included = await client.post(
        f"{base}/sources/{dropped['id']}/decision",
        json={"decision": "INCLUDE", "reason": INCLUDE_REASON},
    )
    assert included.status_code == 200, included.text
    excluded = await client.post(
        f"{base}/sources/{kept['id']}/decision",
        json={"decision": "EXCLUDE", "reason": EXCLUDE_REASON},
    )
    assert excluded.status_code == 200, excluded.text
    unchanged = await client.post(
        f"{base}/sources/{kept['id']}/decision", json={"decision": "EXCLUDE"}
    )
    assert unchanged.status_code == 409

    steps = {step["name"]: step for step in await _user_steps(client, base)}
    assert steps["user.source.include"]["outcome"] == "KEPT"
    assert steps["user.source.include"]["source_ids"] == [dropped["id"]]
    assert INCLUDE_REASON in steps["user.source.include"]["summary"]
    assert steps["user.source.exclude"]["outcome"] == "REMOVED"
    detail = (await client.get(f"{base}/trajectory/{steps['user.source.exclude']['id']}")).json()
    assert detail["request"]["reason"] == EXCLUDE_REASON
    assert detail["request"]["from_status"] == "APPRAISE_PROMOTED"

    assert (await client.post(f"{base}/resynthesize")).status_code == 202
    await asyncio.sleep(POLL_SECONDS)
    state = await _completed(client, base)

    by_id = {source["id"]: source for source in state["sources"]}
    assert by_id[dropped["id"]]["status"] == "APPRAISE_PROMOTED"
    assert by_id[dropped["id"]]["decision"]["applied"] is True
    assert by_id[dropped["id"]]["decision"]["reason"] == INCLUDE_REASON
    assert by_id[kept["id"]]["status"] == "APPRAISE_DISCOUNTED"
    assert by_id[kept["id"]]["decision"]["applied"] is True
    assert all(claim["source_id"] != kept["id"] for claim in state["claims"])
    assert sum(claim["kind"] == "RECOMMENDATION" for claim in state["claims"]) == 1
    assert state["synthesis"] is not None
    assert "user.run.resynthesize" in {step["name"] for step in await _user_steps(client, base)}
