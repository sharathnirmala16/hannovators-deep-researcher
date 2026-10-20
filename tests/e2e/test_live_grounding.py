"""Live grounding checks through the HTTP API: a seeded run, then cited chat on it.

Run with `uv run pytest -m live tests/e2e/test_live_grounding.py`. Needs NEBIUS_API_KEY,
JEV_API_KEY, and TAVILY_API_KEY, and the three PDFs plus `question.txt` in
`<repo parent>/data/seed_1` (or SEED_PDF_DIR); skips without them. Both tests share one small
run (5 screened, 3 appraised, 1 search round, 25 candidates) to keep the cost low.
"""

import asyncio
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import URL

from hannovators_deep_researcher.configuration.settings import ProviderMode, Settings
from hannovators_deep_researcher.infrastructure.database import create_database_engine
from hannovators_deep_researcher.main import create_app
from hannovators_deep_researcher.persistence.base import Base

pytestmark = [pytest.mark.live, pytest.mark.e2e, pytest.mark.asyncio(loop_scope="module")]

SEED_DIR = Path(
    os.environ.get("SEED_PDF_DIR") or Path(__file__).resolve().parents[3] / "data" / "seed_1"
)
RUN_TIMEOUT_SECONDS = 25 * 60
POLL_SECONDS = 3.0
RUN_SETTINGS = {"screen_top_n": 5, "appraise_top_k": 3, "search_max_rounds": 1}
CHAT_QUESTION = "Does dapagliflozin slow eGFR decline in patients with stage 4 CKD?"


@dataclass(frozen=True)
class SeededRun:
    client: httpx.AsyncClient
    base: str
    state: dict[str, Any]
    seed_ids: set[str]


async def _all_steps(client: httpx.AsyncClient, base: str, **params: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    after = 0
    while True:
        query: dict[str, str | int] = {**params, "after": after, "limit": 500}
        page = await client.get(f"{base}/trajectory", params=query)
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


def _live_settings() -> Settings:
    settings = Settings(provider_mode=ProviderMode.REAL, run_budget_max_candidates=25)
    keys = (
        ("NEBIUS_API_KEY", settings.nebius_api_key),
        ("JEV_API_KEY", settings.jev_api_key),
        ("TAVILY_API_KEY", settings.tavily_api_key),
    )
    missing = [name for name, value in keys if value is None]
    if missing:
        pytest.skip(f"missing {', '.join(missing)}")
    if len(list(SEED_DIR.glob("*.pdf"))) < 3 or not (SEED_DIR / "question.txt").is_file():
        pytest.skip(f"seed PDFs and question.txt not found in {SEED_DIR}")
    return settings


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def seeded_run(tmp_path_factory: pytest.TempPathFactory) -> AsyncIterator[SeededRun]:
    settings = _live_settings()
    tmp_path = tmp_path_factory.mktemp("grounding")
    database_url = URL.create("sqlite+aiosqlite", database=str(tmp_path / "live.sqlite"))
    engine = create_database_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
    app = create_app(settings, database_url=database_url, files_dir=tmp_path / "workspaces")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", timeout=600
    ) as client:
        question = (SEED_DIR / "question.txt").read_text(encoding="utf-8").strip()
        created = await client.post(
            "/api/workspaces",
            json={
                "research_question": question,
                "domain_mode": "MEDICAL",
                "auto_continue": True,
                "settings": RUN_SETTINGS,
            },
        )
        assert created.status_code == 201, created.text
        base = f"/api/workspaces/{created.json()['id']}"
        pdfs = sorted(SEED_DIR.glob("*.pdf"))[:3]
        files = [("files", (pdf.name, pdf.read_bytes(), "application/pdf")) for pdf in pdfs]
        uploaded = await client.post(f"{base}/seeds", files=files)
        assert uploaded.status_code == 201, uploaded.text
        seed_ids = {source["id"] for source in uploaded.json()}
        assert (await client.post(f"{base}/run")).status_code == 202
        state = await _wait_for_end(client, base)
        yield SeededRun(client, base, state, seed_ids)
    await app.state.container.aclose()


async def test_live_seeded_run_grounds_seeds_downloads_and_highlights(
    seeded_run: SeededRun,
) -> None:
    client, base, state = seeded_run.client, seeded_run.base, seeded_run.state
    assert state["workspace"]["status"] == "COMPLETED", state["workspace"]["error"]

    for seed_id in seeded_run.seed_ids:
        detail = (await client.get(f"{base}/sources/{seed_id}")).json()
        title = detail["source"]["title"]
        assert detail["chunk_count"] > 0, title
        assert title and not title.lower().endswith(".pdf")

    highlights = [item for item in state["highlights"] if item["rects"]]
    assert highlights, "no highlight with rects"
    first = highlights[0]
    assert first["page"] >= 1 and len(first["rects"][0]) == 4
    assert first["pdf_url"] and first["pdf_url"].startswith("/files/")
    seed_highlights = [item for item in highlights if item["source_id"] in seeded_run.seed_ids]
    assert seed_highlights, "no highlight in a seed PDF"
    pdf = await client.get(first["pdf_url"].split("#", 1)[0])
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    steps = await _all_steps(client, base)
    downloads = [step for step in steps if step["kind"] == "DOWNLOAD"]
    downloaded = {
        source["id"]
        for source in state["sources"]
        if source["origin"] != "SEED" and source["raw_url"]
    }
    if downloaded:
        ok = {sid for step in downloads if step["status"] == "OK" for sid in step["source_ids"]}
        assert downloaded <= ok, downloaded - ok
    acquire_verdicts = {
        sid
        for step in steps
        if step["kind"] == "VERDICT" and step["name"] == "acquire.verdict"
        for sid in step["source_ids"]
    }
    failed = {
        source["id"]
        for source in state["sources"]
        if source["status"] == "ACQUIRE_FAILED" or source["rejection_code"] == "NO_FULL_TEXT"
    }
    assert failed <= acquire_verdicts, failed - acquire_verdicts
    flagged = [
        step for step in steps if step["name"] == "acquire.verdict" and step["outcome"] == "FLAGGED"
    ]
    for step in flagged:
        assert step["source_ids"], step
    assert not [step for step in steps if step["status"] == "RUNNING"]


async def test_live_cited_chat_on_the_seeded_run(seeded_run: SeededRun) -> None:
    client, base, state = seeded_run.client, seeded_run.base, seeded_run.state
    if state["workspace"]["status"] != "COMPLETED":
        pytest.fail(f"seeded run did not complete: {state['workspace']['error']}")

    reply = await client.post(f"{base}/chat", json={"question": CHAT_QUESTION})
    assert reply.status_code == 200, reply.text
    answer = reply.json()
    assert answer["role"] == "ASSISTANT"
    citations = answer["citations"]
    assert citations, answer["content"]
    known = {source["id"]: source for source in state["sources"]}
    for citation in citations:
        assert citation["source_id"] in known
        assert f"[{citation['n']}]" in answer["content"]
        assert citation["quote"].strip()
        if citation["pdf_url"]:
            assert citation["page"] and citation["page"] >= 1, citation
            assert citation["rects"] and all(len(rect) == 4 for rect in citation["rects"])

    history = (await client.get(f"{base}/chat")).json()
    assert [message["role"] for message in history[-2:]] == ["USER", "ASSISTANT"]
    assert history[-1]["id"] == answer["id"]

    chat_steps = await _all_steps(client, base, kind="CHAT")
    step = next(item for item in chat_steps if item["id"] == answer["trajectory_step_id"])
    assert step["status"] == "OK"
    steps = await _all_steps(client, base)
    children = {item["kind"] for item in steps if item["parent_id"] == step["id"]}
    assert {"RETRIEVE", "LLM"} <= children, children
