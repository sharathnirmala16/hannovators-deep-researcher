"""Tavily Research API: one cited deep-research report per call (PLAN.md card T1).

`AsyncTavilyClient.research(input, model="mini", citation_format="numbered")` starts a task;
`get_research(request_id)` is polled every `POLL_SECONDS` until it is `completed` or `failed`,
or until `TIMEOUT_SECONDS` pass. Failures never raise: they come back as a `failed` record, so
the caller can store them. `PROVIDER_MODE=fake` uses `FakeDeepResearch` (canned web pages).
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from tavily import AsyncTavilyClient  # type: ignore[import-untyped]

from hannovators_deep_researcher.adapters.fake.catalog import canned_set
from hannovators_deep_researcher.configuration.settings import ProviderMode, Settings
from hannovators_deep_researcher.infrastructure.http import create_http_client
from hannovators_deep_researcher.models.deep_research import (
    DeepResearchRecord,
    DeepResearchSource,
)
from hannovators_deep_researcher.models.enums import DomainMode, SourceOrigin

BASE_URL = "https://api.tavily.com"
RESEARCH_URL = f"{BASE_URL}/research"
MODEL = "mini"
POLL_SECONDS = 3.0
TIMEOUT_SECONDS = 180.0
REQUEST_TIMEOUT = 60.0
PROGRESS_EVERY_POLLS = 5
MAX_ERROR_CHARS = 300

ProgressFn = Callable[[str], Awaitable[None]]


def _now() -> datetime:
    return datetime.now(UTC)


def _sources(payload: dict[str, Any]) -> list[DeepResearchSource]:
    sources: list[DeepResearchSource] = []
    for item in payload.get("sources") or []:
        if isinstance(item, dict) and item.get("url"):
            url = str(item["url"])
            sources.append(DeepResearchSource(title=str(item.get("title") or url), url=url))
    return sources


def _content(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, str):
        return content
    return "" if content is None else str(content)


class TavilyDeepResearch:
    """Runs one Tavily research task to completion. The SDK client is built per run."""

    name = "tavily"

    def __init__(
        self,
        api_key: str | None,
        *,
        poll_seconds: float = POLL_SECONDS,
        timeout_seconds: float = TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._poll = poll_seconds
        self._timeout = timeout_seconds

    def is_configured(self) -> bool:
        return self._api_key is not None

    async def run(
        self, input_text: str, *, on_progress: ProgressFn | None = None
    ) -> DeepResearchRecord:
        started = _now()
        if self._api_key is None:
            return self._failed(started, "TAVILY_API_KEY is not set")
        async with create_http_client(base_url=BASE_URL, timeout=REQUEST_TIMEOUT) as http:
            client = AsyncTavilyClient(api_key=self._api_key, client=http)
            try:
                return await self._run(client, input_text, started, on_progress)
            except Exception as error:
                return self._failed(started, f"{type(error).__name__}: {error}")

    async def _run(
        self,
        client: AsyncTavilyClient,
        input_text: str,
        started: datetime,
        on_progress: ProgressFn | None,
    ) -> DeepResearchRecord:
        task = await client.research(input=input_text, model=MODEL, citation_format="numbered")
        request_id = str(task.get("request_id") or "") if isinstance(task, dict) else ""
        if not request_id:
            return self._failed(started, "the research call returned no request_id")
        deadline = time.monotonic() + self._timeout
        polls = 0
        while time.monotonic() < deadline:
            await asyncio.sleep(self._poll)
            polls += 1
            payload = await client.get_research(request_id)
            status = str(payload.get("status") or "") if isinstance(payload, dict) else ""
            if status == "completed":
                return DeepResearchRecord(
                    status="completed",
                    content=_content(payload),
                    sources=_sources(payload),
                    started_at=started,
                    finished_at=_now(),
                )
            if status == "failed":
                return self._failed(started, str(payload.get("error") or "research task failed"))
            if on_progress is not None and polls % PROGRESS_EVERY_POLLS == 0:
                await on_progress(
                    f"Tavily deep research {status or 'running'} "
                    f"({round(polls * self._poll)} s elapsed)"
                )
        return self._failed(started, f"timed out after {round(self._timeout)} s")

    @staticmethod
    def _failed(started: datetime, error: str) -> DeepResearchRecord:
        return DeepResearchRecord(
            status="failed", started_at=started, finished_at=_now(), error=error[:MAX_ERROR_CHARS]
        )


class FakeDeepResearch:
    """Offline stand-in: a short numbered report citing canned web pages."""

    name = "fake"

    def is_configured(self) -> bool:
        return True

    async def run(
        self, input_text: str, *, on_progress: ProgressFn | None = None
    ) -> DeepResearchRecord:
        started = _now()
        records = [
            record
            for domain in DomainMode
            for record in canned_set(domain).records
            if record.origin is SourceOrigin.WEB and record.url
        ][:3]
        sources = [
            DeepResearchSource(title=record.title, url=record.url or "") for record in records
        ]
        lines = [f"[{index}] {source.title}" for index, source in enumerate(sources, start=1)]
        content = (
            "Fake deep research report. The cited pages discuss the question; see the "
            "numbered sources.\n\n" + "\n".join(lines)
        )
        if on_progress is not None:
            await on_progress("Tavily deep research (fake) produced a canned report")
        return DeepResearchRecord(
            status="completed",
            content=content,
            sources=sources,
            started_at=started,
            finished_at=_now(),
        )


def build_deep_research(settings: Settings) -> TavilyDeepResearch | FakeDeepResearch:
    if settings.provider_mode is ProviderMode.FAKE:
        return FakeDeepResearch()
    key = settings.tavily_api_key.get_secret_value() if settings.tavily_api_key else None
    return TavilyDeepResearch(key)
