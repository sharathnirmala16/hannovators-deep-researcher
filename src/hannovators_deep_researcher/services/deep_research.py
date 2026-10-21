"""Tavily deep research per workspace: one background task, a JSON record, and WEB sources.

`start()` writes a `running` record to `data/workspaces/<ws>/deep_research.json` and runs the
research in an asyncio task (one per workspace). The task records one SEARCH trajectory step
(`tavily.research`) with the report and its sources, emits PROGRESS events on stage `search`
("Tavily deep research ..."), inserts each cited URL as a RAW `WEB` source with search intent
DEEP_RESEARCH (deduplicated by canonical URL), adds the report itself as one more source
(`services/deep_research_report.py`), and writes the final record. Records that completed
before report sources existed get theirs when they are read (`ensure_report`).
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy.exc import IntegrityError

from hannovators_deep_researcher.models.contracts import (
    DECOMPOSITION_ADAPTER,
    PicotsDecomposition,
    ScopeDecomposition,
)
from hannovators_deep_researcher.models.deep_research import (
    DeepResearchRecord,
    DeepResearchSource,
)
from hannovators_deep_researcher.models.enums import (
    SearchIntent,
    SourceOrigin,
    SourceStatus,
    StageId,
    TraceEventKind,
    TrajectoryKind,
    TrajectoryStatus,
)
from hannovators_deep_researcher.persistence.tables import WorkspaceRow
from hannovators_deep_researcher.services.deep_research_report import ensure_report_source
from hannovators_deep_researcher.services.documents.files import (
    WORKSPACES_DIR,
    resolve_data_path,
    write_bytes,
)
from hannovators_deep_researcher.services.evidence import heuristic_level, keyword_stance
from hannovators_deep_researcher.services.pipeline.context import PipelineServices
from hannovators_deep_researcher.services.trajectory import bind
from hannovators_deep_researcher.services.urls import canonicalize_url

logger = logging.getLogger(__name__)

RECORD_FILE = "deep_research.json"
FOUND_BY = "tavily_research"
RESEARCH_TARGET = "https://api.tavily.com/research"
MEDICAL_DOMAINS = ("clinicaltrials.gov", "fda.gov", "ema.europa.eu", "who.int", "kdigo.org")
MAX_INPUT_CHARS = 4_000
PREFIX = "Tavily deep research"

ProgressFn = Callable[[str], Awaitable[None]]


class DeepResearchProvider(Protocol):
    name: str

    async def run(
        self, input_text: str, *, on_progress: ProgressFn | None = None
    ) -> DeepResearchRecord: ...


class DeepResearchRunningError(Exception):
    """A deep research task is already running for this workspace."""


def record_path(workspace_id: str) -> str:
    return f"{WORKSPACES_DIR}/{workspace_id}/{RECORD_FILE}"


def _summary(decomposition: PicotsDecomposition | ScopeDecomposition) -> str:
    if isinstance(decomposition, PicotsDecomposition):
        pairs = "; ".join(f"{p.intervention} vs {p.comparison}" for p in decomposition.ic_pairs)
        return "\n".join(
            [
                f"Population: {decomposition.population}",
                f"Interventions: {'; '.join(decomposition.interventions)}",
                f"Comparisons: {'; '.join(decomposition.comparisons) or 'any'}",
                f"Comparisons to cover: {pairs or 'n/a'}",
                f"Outcomes (benefits and harms): {'; '.join(decomposition.outcomes)}",
                f"Timing: {decomposition.timing or 'any'}",
            ]
        )
    return "\n".join(
        [
            f"Entities: {'; '.join(decomposition.entities)}",
            f"Claims to verify: {'; '.join(decomposition.claims)}",
            f"Metrics: {'; '.join(decomposition.metrics)}",
            f"Counter-hypotheses: {'; '.join(decomposition.counter_hypotheses)}",
        ]
    )


def research_input(workspace: WorkspaceRow) -> str:
    """The question, the decomposition summary, and a request for disconfirming evidence."""

    parts = [f"Research question: {workspace.research_question}"]
    decomposition = (
        DECOMPOSITION_ADAPTER.validate_json(workspace.decomposition_json)
        if workspace.decomposition_json
        else None
    )
    if decomposition is not None:
        parts.append(f"Scope:\n{_summary(decomposition)}")
    parts.append(
        "Write a cited report. Rank evidence by study design (meta-analyses and systematic "
        "reviews, then randomized trials, then observational studies). Report the strongest "
        "evidence against the intervention or claim (null, negative, harmful, or stopped "
        "trials) and the main alternatives, not only supporting evidence."
    )
    medical = isinstance(decomposition, PicotsDecomposition) or workspace.domain_mode == "MEDICAL"
    if medical:
        parts.append(
            "Prefer primary and authoritative sources: PubMed-indexed trials and reviews, and "
            f"{', '.join(MEDICAL_DOMAINS)}."
        )
    return "\n\n".join(parts)[:MAX_INPUT_CHARS]


class DeepResearchService:
    def __init__(
        self,
        *,
        services: PipelineServices,
        provider: DeepResearchProvider,
        root: Path | None = None,
    ) -> None:
        self._services = services
        self._repositories = services.repositories
        self._trajectory = services.trajectory
        self._events = services.events
        self._provider = provider
        self._root = root
        self._tasks: dict[str, asyncio.Task[DeepResearchRecord]] = {}

    def is_running(self, workspace_id: str) -> bool:
        task = self._tasks.get(workspace_id)
        return task is not None and not task.done()

    def read(self, workspace_id: str) -> DeepResearchRecord | None:
        path = resolve_data_path(record_path(workspace_id), root=self._root)
        if not path.is_file():
            return None
        return DeepResearchRecord.model_validate_json(path.read_text(encoding="utf-8"))

    async def ensure_report(
        self, workspace: WorkspaceRow, record: DeepResearchRecord
    ) -> DeepResearchRecord:
        """Give a completed record its report source (once) and store the source id."""

        if record.status != "completed" or self.is_running(workspace.id):
            return record
        updated = await ensure_report_source(self._services, workspace, record, root=self._root)
        if updated.report_source_id != record.report_source_id:
            self._write(workspace.id, updated)
        return updated

    def _write(self, workspace_id: str, record: DeepResearchRecord) -> None:
        write_bytes(
            record_path(workspace_id), record.model_dump_json(indent=2).encode(), root=self._root
        )

    async def start(self, workspace: WorkspaceRow) -> DeepResearchRecord:
        """Start a background run. Raises `DeepResearchRunningError` while one is running."""

        if self.is_running(workspace.id):
            raise DeepResearchRunningError(f"deep research is already running for {workspace.id}")
        record = DeepResearchRecord(status="running", started_at=datetime.now(UTC))
        self._write(workspace.id, record)
        task = asyncio.create_task(self._run(workspace, research_input(workspace)))
        self._tasks[workspace.id] = task
        task.add_done_callback(lambda done: self._finished(workspace.id, done))
        return record

    def _finished(self, workspace_id: str, done: asyncio.Task[DeepResearchRecord]) -> None:
        if self._tasks.get(workspace_id) is done:
            del self._tasks[workspace_id]
        if not done.cancelled() and done.exception() is not None:
            logger.error("Deep research crashed for %s", workspace_id, exc_info=done.exception())

    async def aclose(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _emit(
        self, workspace_id: str, kind: TraceEventKind, message: str, payload: dict[str, object]
    ) -> None:
        await self._events.emit(workspace_id, StageId.SEARCH, kind, message, payload)

    async def _run(self, workspace: WorkspaceRow, input_text: str) -> DeepResearchRecord:
        workspace_id = workspace.id

        async def progress(message: str) -> None:
            await self._emit(workspace_id, TraceEventKind.PROGRESS, message, {"tool": FOUND_BY})

        await progress(f"{PREFIX} started ({self._provider.name}, model mini)")
        started = datetime.now(UTC)
        inserted = 0
        try:
            with bind(workspace_id, StageId.SEARCH):
                record, inserted = await self._research(workspace, input_text, progress)
        except Exception as error:
            record = DeepResearchRecord(
                status="failed",
                started_at=started,
                finished_at=datetime.now(UTC),
                error=f"{type(error).__name__}: {error}"[:300],
            )
        self._write(workspace_id, record)
        if record.status == "completed":
            await progress(
                f"{PREFIX} completed: {len(record.sources)} cited sources, "
                f"{inserted} added as WEB sources, and the report as one source"
            )
        else:
            await self._emit(
                workspace_id,
                TraceEventKind.WARNING,
                f"{PREFIX} failed: {record.error}",
                {"tool": FOUND_BY, "error": record.error},
            )
        return record

    async def _research(
        self, workspace: WorkspaceRow, input_text: str, progress: ProgressFn
    ) -> tuple[DeepResearchRecord, int]:
        """Run the provider inside one SEARCH step; return the record and new source count."""

        workspace_id = workspace.id
        inserted = 0
        async with self._trajectory.step(
            kind=TrajectoryKind.SEARCH,
            name="tavily.research",
            target=RESEARCH_TARGET,
            summary=f"{PREFIX} (model mini)",
            request={"input": input_text, "model": "mini", "citation_format": "numbered"},
        ) as handle:
            record = await self._provider.run(input_text, on_progress=progress)
            if record.status == "completed":
                sources, inserted = await self._insert_sources(workspace_id, record.sources)
                record = record.model_copy(update={"sources": sources})
                record = await ensure_report_source(
                    self._services, workspace, record, root=self._root
                )
            else:
                handle.status = TrajectoryStatus.ERROR
            handle.source_ids = [
                source_id
                for source_id in (*(s.source_id for s in record.sources), record.report_source_id)
                if source_id
            ]
            handle.summary = (
                f"{PREFIX} {record.status}: {len(record.sources)} sources, {inserted} new"
                + (f" ({record.error})" if record.error else "")
            )
            handle.response = {
                "status": record.status,
                "provider": self._provider.name,
                "content": record.content,
                "sources": [source.model_dump() for source in record.sources],
                "new_sources": inserted,
                "report_source_id": record.report_source_id,
                "error": record.error,
            }
        return record, inserted

    async def _insert_sources(
        self, workspace_id: str, sources: list[DeepResearchSource]
    ) -> tuple[list[DeepResearchSource], int]:
        """Insert each new cited URL as a RAW WEB source; link duplicates to the existing one."""

        existing = await self._repositories.list_sources(workspace_id)
        by_url: dict[str, str] = {}
        for row in existing:
            for value in (row.external_id, row.url):
                if value and value.startswith(("http://", "https://")):
                    by_url.setdefault(canonicalize_url(value), row.id)
        linked: list[DeepResearchSource] = []
        inserted = 0
        for source in sources:
            url = canonicalize_url(source.url)
            if not url:
                linked.append(source)
                continue
            source_id = by_url.get(url)
            if source_id is None:
                source_id = await self._insert(workspace_id, source, url)
                inserted += source_id is not None
            if source_id is not None:
                by_url[url] = source_id
            linked.append(source.model_copy(update={"source_id": source_id}))
        return linked, inserted

    async def _insert(self, workspace_id: str, source: DeepResearchSource, url: str) -> str | None:
        level = heuristic_level(title=source.title, abstract=None, origin=SourceOrigin.WEB)
        try:
            row = await self._repositories.create_source(
                workspace_id,
                origin=SourceOrigin.WEB,
                external_id=url,
                title=source.title or url,
                status=SourceStatus.RAW,
                url=url,
                search_intent=SearchIntent.DEEP_RESEARCH,
                evidence_level=level.level,
                # Screening replaces this with Jev's reading when the source is screened.
                stance=keyword_stance(source.title),
                extra_json=json.dumps({"found_by": FOUND_BY}),
            )
        except IntegrityError:
            return None
        return row.id
