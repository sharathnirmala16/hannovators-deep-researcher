"""Read models and guarded writes for the HTTP API (PLAN.md sections 4.4 and 5.3).

Builds `WorkspaceState`, `GraphView`, workspace summaries, source details, and trajectory pages;
stores seed PDFs and references; and recovers runs interrupted by a restart. Stored file paths
are relative to `data/`, so a `/files/` prefix gives their public URL.
"""

import asyncio
import hashlib
import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePath

import pymupdf
from pydantic import TypeAdapter
from sqlalchemy import ColumnElement, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from hannovators_deep_researcher.models.contracts import (
    DECOMPOSITION_ADAPTER,
    ClaimView,
    Funnel,
    GraphEdge,
    GraphNode,
    GraphView,
    HighlightView,
    PicotsDecomposition,
    QueryView,
    Rob2Assessment,
    ScopeDecomposition,
    SeedReferenceRequest,
    SourceDetail,
    SourceView,
    Synthesis,
    WorkspaceSettings,
    WorkspaceState,
    WorkspaceSummary,
    WorkspaceView,
)
from hannovators_deep_researcher.models.enums import (
    EVIDENCE_RANK,
    ClaimKind,
    ClaimVerdict,
    Directness,
    EvidenceLevel,
    EvidenceStance,
    HighlightMethod,
    RejectionCode,
    RequestedDomainMode,
    SearchIntent,
    SourceLinkKind,
    SourceOrigin,
    SourceStatus,
    StageId,
    TraceEventKind,
    TrajectoryActor,
    TrajectoryKind,
    TrajectoryStatus,
    UiComponentId,
    VerdictOutcome,
    WorkspaceStatus,
)
from hannovators_deep_researcher.models.events import TraceEvent
from hannovators_deep_researcher.models.trajectory import (
    TrajectoryPage,
    TrajectoryStep,
    TrajectoryStepSummary,
)
from hannovators_deep_researcher.persistence.repositories import Repositories
from hannovators_deep_researcher.persistence.tables import (
    ChunkRow,
    ClaimRow,
    HighlightRow,
    SearchQueryRow,
    SourceRow,
    TraceEventRow,
    TrajectoryStepRow,
    WorkspaceRow,
    new_id,
    utc_now,
)
from hannovators_deep_researcher.services.documents.files import RAW_PDF, source_path, write_bytes
from hannovators_deep_researcher.services.trajectory import to_step, to_summary
from hannovators_deep_researcher.services.urls import canonicalize_url

FILES_PREFIX = "/files/"
TERMINAL_STATUSES = frozenset({WorkspaceStatus.COMPLETED, WorkspaceStatus.FAILED})
_UI_COMPONENTS = TypeAdapter(list[UiComponentId])
_PAST_SCREENING = (
    SourceStatus.SCREEN_PROMOTED,
    SourceStatus.APPRAISE_PROMOTED,
    SourceStatus.APPRAISE_DISCOUNTED,
    SourceStatus.ACQUIRE_FAILED,
)
_PROMOTED = (SourceStatus.SCREEN_PROMOTED, SourceStatus.APPRAISE_PROMOTED)
"""Statuses counted as `promoted_count`: sources currently kept by screening or appraisal."""

STREAM_PAGE = 500
SHA256_PREFIX = "sha256:"
PUBMED_URL = "https://pubmed.ncbi.nlm.nih.gov/"
DOI_URL = "https://doi.org/"
DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:")
MIN_TITLE_CHARS = 10
MIN_TITLE_WORDS = 3
MAX_TITLE_CHARS = 300
TITLE_FONT_TOLERANCE = 0.5
SUPERSCRIPT_RATIO = 0.75
_LETTER = re.compile(r"[^\W\d_]")


class WorkspaceNotFoundError(LookupError):
    def __init__(self, workspace_id: str) -> None:
        super().__init__(f"workspace {workspace_id} not found")
        self.workspace_id = workspace_id


class WorkspaceStatusError(Exception):
    """The workspace is not in the status that the operation needs."""

    def __init__(self, workspace_id: str, status: str, needed: WorkspaceStatus) -> None:
        super().__init__(f"workspace {workspace_id} is {status}; this needs {needed}")
        self.status = status


def _optional[E: StrEnum](enum: type[E], value: str | None) -> E | None:
    return None if value is None else enum(value)


def file_url(relative_path: str | None) -> str | None:
    return None if relative_path is None else f"{FILES_PREFIX}{relative_path}"


def _pdf_url(row: SourceRow) -> str | None:
    """Local highlighted or raw PDF (`/files/...`), else the remote PDF URL."""

    if row.highlighted_path:
        return file_url(row.highlighted_path)
    if row.raw_path and row.raw_path.lower().endswith(".pdf"):
        return file_url(row.raw_path)
    return row.pdf_url


def workspace_view(row: WorkspaceRow) -> WorkspaceView:
    return WorkspaceView(
        id=row.id,
        research_question=row.research_question,
        domain_mode=RequestedDomainMode(row.domain_mode),
        status=WorkspaceStatus(row.status),
        current_stage=_optional(StageId, row.current_stage),
        auto_continue=row.auto_continue,
        settings=WorkspaceSettings.model_validate_json(row.settings_json),
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def compute_funnel(statuses: Iterable[str]) -> Funnel:
    """Cumulative PRISMA-style counts from each source's final status."""

    counts = Counter(SourceStatus(status) for status in statuses)
    total = sum(counts.values())
    return Funnel(
        seeds=counts[SourceStatus.SEED],
        raw=total - counts[SourceStatus.SEED],
        screen_promoted=sum(counts[status] for status in _PAST_SCREENING),
        screen_discounted=counts[SourceStatus.SCREEN_DISCOUNTED],
        appraise_promoted=counts[SourceStatus.APPRAISE_PROMOTED],
        appraise_discounted=counts[SourceStatus.APPRAISE_DISCOUNTED],
        acquire_failed=counts[SourceStatus.ACQUIRE_FAILED],
    )


def _safe_enum[E: StrEnum](enum: type[E], value: str | None) -> E | None:
    """Like `_optional`, but an unknown stored value reads as None instead of failing."""

    try:
        return _optional(enum, value)
    except ValueError:
        return None


def _json_object(text: str | None) -> dict[str, object]:
    """Parse a `*_json` column as an object; other JSON values come back under `value`."""

    if not text:
        return {}
    try:
        value = json.loads(text)
    except ValueError:
        return {"value": text}
    return value if isinstance(value, dict) else {"value": value}


def _found_by(extra: dict[str, object]) -> str | None:
    value = extra.get("found_by")
    if value is None or value == "":
        return None
    return value if isinstance(value, str) else json.dumps(value)


def _search_intent(row: SourceRow) -> SearchIntent | None:
    """The stored intent. Rows from runs before intents existed (no `search_intent`, but a
    `found_by_query_id`) were found by the only queries the pipeline had then: CORE."""

    intent = _safe_enum(SearchIntent, row.search_intent)
    if intent is None and row.found_by_query_id and row.status != SourceStatus.SEED:
        return SearchIntent.CORE
    return intent


def source_view(row: SourceRow) -> SourceView:
    level = _safe_enum(EvidenceLevel, row.evidence_level)
    return SourceView(
        id=row.id,
        origin=SourceOrigin(row.origin),
        external_id=row.external_id,
        title=row.title,
        authors=json.loads(row.authors_json or "[]"),
        year=row.year,
        venue=row.venue,
        url=row.url,
        study_design=row.study_design,
        status=SourceStatus(row.status),
        screen_score=row.screen_score,
        screen_z=row.screen_z,
        screen_votes=row.screen_votes,
        m_score=row.m_score,
        directness=_optional(Directness, row.directness),
        rob2=Rob2Assessment.model_validate_json(row.rob2_json) if row.rob2_json else None,
        rejection_code=_optional(RejectionCode, row.rejection_code),
        decision_explanation=row.decision_explanation,
        raw_url=file_url(row.raw_path),
        highlighted_url=file_url(row.highlighted_path),
        evidence_level=level,
        evidence_rank=None if level is None else EVIDENCE_RANK.get(level),
        stance=_safe_enum(EvidenceStance, row.stance),
        search_intent=_search_intent(row),
        found_by=_found_by(_json_object(row.extra_json)),
    )


_source_view = source_view


def _query_view(row: SearchQueryRow) -> QueryView:
    return QueryView(
        id=row.id,
        workspace_id=row.workspace_id,
        iteration=row.iteration,
        tool=row.tool,
        core_query=row.core_query,
        applied_filters=row.applied_filters,
        raw_hit_count=row.raw_hit_count,
        latency_ms=row.latency_ms,
        refinement_note=row.refinement_note,
        created_at=row.created_at,
    )


def _claim_view(row: ClaimRow, highlight_ids: list[str]) -> ClaimView:
    payload = json.loads(row.payload_json) if row.payload_json else {}
    return ClaimView(
        id=row.id,
        source_id=row.source_id,
        kind=ClaimKind(row.kind),
        label=row.label,
        text=row.text,
        quote=row.quote,
        verdict=ClaimVerdict(row.verdict),
        confidence=row.confidence,
        outcome=payload.get("outcome"),
        arm=payload.get("arm"),
        highlight_ids=highlight_ids,
    )


def _highlight_view(row: HighlightRow, highlighted_path: str | None) -> HighlightView:
    pdf_url = file_url(highlighted_path)
    return HighlightView(
        id=row.id,
        source_id=row.source_id,
        claim_id=row.claim_id,
        page=row.page,
        rects=json.loads(row.rects_json or "[]"),
        method=HighlightMethod(row.method),
        score=row.score,
        color=row.color,
        pdf_url=None if pdf_url is None else f"{pdf_url}#page={row.page}",
    )


def parse_decomposition(row: WorkspaceRow) -> PicotsDecomposition | ScopeDecomposition | None:
    if not row.decomposition_json:
        return None
    return DECOMPOSITION_ADAPTER.validate_json(row.decomposition_json)


def parse_ui_components(row: WorkspaceRow) -> list[UiComponentId]:
    return _UI_COMPONENTS.validate_json(row.ui_components_json) if row.ui_components_json else []


# --- Seeds ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PdfInfo:
    title: str
    page_count: int
    author: str | None


def _metadata_title(metadata: Mapping[str, object]) -> str | None:
    title = " ".join(str(metadata.get("title") or "").split())
    lowered = title.lower()
    if (
        len(title) < MIN_TITLE_CHARS
        or lowered.startswith(("microsoft word", "untitled"))
        or lowered.endswith((".pdf", ".doc", ".docx", ".tex", ".indd"))
    ):
        return None
    return title[:MAX_TITLE_CHARS]


def _first_page_lines(page: pymupdf.Page) -> list[tuple[str, float]]:
    """Text lines of a page with their largest font size, in reading order."""

    content = page.get_text("dict", sort=True)  # type: ignore[no-untyped-call]
    lines: list[tuple[str, float]] = []
    for block in content.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            size = max(float(span.get("size", 0.0)) for span in spans)
            # Drop superscripts (footnote marks) and keep ligatures readable ("ﬂ" -> "fl").
            raw = "".join(
                str(span.get("text", ""))
                for span in spans
                if float(span.get("size", 0.0)) >= size * SUPERSCRIPT_RATIO
            )
            text = " ".join(unicodedata.normalize("NFKC", raw).split())
            if _LETTER.search(text):
                lines.append((text, size))
    return lines


def _largest_font_title(lines: list[tuple[str, float]]) -> str | None:
    """The first run of lines set in the largest font (usually the article title)."""

    sized = [(text, size) for text, size in lines if len(text.split()) >= 2]
    if not sized:
        return None
    largest = max(size for _, size in sized)
    run: list[str] = []
    for text, size in lines:
        if size >= largest - TITLE_FONT_TOLERANCE:
            run.append(text)
        elif run:
            break
    title = " ".join(run)
    return title[:MAX_TITLE_CHARS] if len(title.split()) >= MIN_TITLE_WORDS else None


def _first_line_title(lines: list[tuple[str, float]]) -> str | None:
    for text, _ in lines:
        if len(text.split()) >= MIN_TITLE_WORDS and len(text) <= MAX_TITLE_CHARS:
            return text
    return None


def read_pdf_info(data: bytes, filename: str) -> PdfInfo:
    """Title from the PDF metadata, else the first page (largest font, then first long line),
    else the file name. Raises `ValueError` when the bytes are not a readable PDF."""

    try:
        document = pymupdf.open(stream=data, filetype="pdf")  # type: ignore[no-untyped-call]
    except Exception as error:
        raise ValueError(f"not a readable PDF: {error}") from error
    with document:
        metadata: Mapping[str, object] = document.metadata or {}
        page_count = int(document.page_count)
        lines = _first_page_lines(document[0]) if page_count else []
    stem = PurePath(filename).stem.replace("_", " ").strip() or "Uploaded PDF"
    title = (
        _metadata_title(metadata)
        or _largest_font_title(lines)
        or _first_line_title(lines)
        or stem[:MAX_TITLE_CHARS]
    )
    author = " ".join(str(metadata.get("author") or "").split()) or None
    return PdfInfo(title=title, page_count=page_count, author=author)


@dataclass(frozen=True, slots=True)
class SeedReference:
    """A normalized PMID, DOI, or URL seed."""

    kind: str
    external_id: str
    title: str
    url: str


def normalize_seed_reference(body: SeedReferenceRequest) -> SeedReference:
    if body.pmid is not None:
        pmid = body.pmid.strip().upper().removeprefix("PMID:").strip()
        return SeedReference("pmid", pmid, f"PMID {pmid}", f"{PUBMED_URL}{pmid}/")
    if body.doi is not None:
        doi = body.doi.strip()
        for prefix in DOI_PREFIXES:
            if doi.lower().startswith(prefix):
                doi = doi[len(prefix) :]
                break
        doi = doi.strip().lower()
        return SeedReference("doi", doi, f"DOI {doi}", f"{DOI_URL}{doi}")
    url = (body.url or "").strip()
    canonical = canonicalize_url(url)
    return SeedReference("url", canonical, canonical, url)


# --- Trajectory queries ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TrajectoryFilter:
    """Filters of `GET /trajectory`. `q` is a case-insensitive substring of name/target/summary."""

    kind: TrajectoryKind | None = None
    actor: TrajectoryActor | None = None
    stage: StageId | None = None
    outcome: VerdictOutcome | None = None
    q: str | None = None

    def criteria(self) -> list[ColumnElement[bool]]:
        row = TrajectoryStepRow
        criteria: list[ColumnElement[bool]] = []
        for column, value in (
            (row.kind, self.kind),
            (row.actor, self.actor),
            (row.stage, self.stage),
            (row.outcome, self.outcome),
        ):
            if value is not None:
                criteria.append(column == value)
        if self.q:
            criteria.append(
                or_(
                    row.name.contains(self.q, autoescape=True),
                    row.target.contains(self.q, autoescape=True),
                    row.summary.contains(self.q, autoescape=True),
                )
            )
        return criteria


class WorkspaceStateService:
    """Read models for the HTTP API, plus the guarded decomposition update."""

    def __init__(self, repositories: Repositories, *, data_dir: Path | None = None) -> None:
        """`data_dir` is the root that holds `workspaces/` (default: the project `data/`)."""

        self._repositories = repositories
        self._data_dir = data_dir

    async def require_workspace(self, workspace_id: str) -> WorkspaceRow:
        row = await self._repositories.get_workspace(workspace_id)
        if row is None:
            raise WorkspaceNotFoundError(workspace_id)
        return row

    async def list_summaries(self) -> list[WorkspaceSummary]:
        """Every workspace, newest first, with source, promoted, and seed counts."""

        rows = await self._repositories.list_workspaces()
        statement = select(SourceRow.workspace_id, SourceRow.status, func.count()).group_by(
            SourceRow.workspace_id, SourceRow.status
        )
        async with self._repositories.transaction() as session:
            grouped = (await session.execute(statement)).all()
        counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
        for workspace_id, status, count in grouped:
            counts[workspace_id][status] += count
        summaries = [
            WorkspaceSummary(
                id=row.id,
                research_question=row.research_question,
                domain_mode=RequestedDomainMode(row.domain_mode),
                status=WorkspaceStatus(row.status),
                current_stage=_safe_enum(StageId, row.current_stage),
                created_at=row.created_at,
                updated_at=row.updated_at,
                source_count=sum(counts[row.id].values()),
                promoted_count=sum(counts[row.id][status] for status in _PROMOTED),
                seed_count=counts[row.id][SourceStatus.SEED],
            )
            for row in rows
        ]
        return sorted(summaries, key=lambda item: (item.created_at, item.id), reverse=True)

    # --- seeds ------------------------------------------------------------------------------

    async def find_source(self, workspace_id: str, external_id: str) -> SourceRow | None:
        statement = select(SourceRow).where(
            SourceRow.workspace_id == workspace_id, SourceRow.external_id == external_id
        )
        async with self._repositories.transaction() as session:
            return (await session.scalars(statement)).first()

    async def add_pdf_seed(self, workspace_id: str, *, filename: str, data: bytes) -> SourceRow:
        """Store a seed PDF at `sources/<id>/raw.pdf` and add a SEED source.

        `external_id` is `sha256:<hex>` of the bytes, so the same file twice gives one source.
        Raises `ValueError` when the bytes are not a readable PDF.
        """

        digest = hashlib.sha256(data).hexdigest()
        external_id = f"{SHA256_PREFIX}{digest}"
        existing = await self.find_source(workspace_id, external_id)
        if existing is not None:
            return existing
        info = await asyncio.to_thread(read_pdf_info, data, filename)
        source_id = new_id()
        relative = source_path(workspace_id, source_id, RAW_PDF)
        written = await asyncio.to_thread(write_bytes, relative, data, root=self._data_dir)
        extra = {
            "found_by": "seed:pdf",
            "seed": {
                "kind": "pdf",
                "filename": filename,
                "sha256": digest,
                "size_bytes": len(data),
                "page_count": info.page_count,
            },
        }
        try:
            return await self._repositories.create_source(
                workspace_id,
                id=source_id,
                origin=SourceOrigin.SEED,
                external_id=external_id,
                title=info.title,
                status=SourceStatus.SEED,
                raw_path=relative,
                authors_json=[info.author] if info.author else [],
                extra_json=extra,
            )
        except IntegrityError:
            shutil.rmtree(written.parent, ignore_errors=True)
            return await self._existing_after_race(workspace_id, external_id)

    async def add_reference_seed(self, workspace_id: str, body: SeedReferenceRequest) -> SourceRow:
        """Add a SEED source for a PMID, DOI, or URL; `ingest` resolves it during the run."""

        reference = normalize_seed_reference(body)
        existing = await self.find_source(workspace_id, reference.external_id)
        if existing is not None:
            return existing
        try:
            return await self._repositories.create_source(
                workspace_id,
                origin=SourceOrigin.SEED,
                external_id=reference.external_id,
                title=reference.title,
                status=SourceStatus.SEED,
                url=reference.url,
                extra_json={
                    "found_by": f"seed:{reference.kind}",
                    "seed": {"kind": reference.kind, "value": reference.external_id},
                },
            )
        except IntegrityError:
            return await self._existing_after_race(workspace_id, reference.external_id)

    async def _existing_after_race(self, workspace_id: str, external_id: str) -> SourceRow:
        existing = await self.find_source(workspace_id, external_id)
        if existing is None:
            raise LookupError(f"source {external_id!r} vanished after a duplicate insert")
        return existing

    # --- source detail ----------------------------------------------------------------------

    async def source_detail(self, workspace_id: str, source_id: str) -> SourceDetail | None:
        """The source with its audit record, or None when it is not in this workspace."""

        await self.require_workspace(workspace_id)
        row = await self._repositories.get_source(source_id)
        if row is None or row.workspace_id != workspace_id:
            return None
        chunks = select(func.count()).select_from(ChunkRow).where(ChunkRow.source_id == source_id)
        claims = select(ClaimRow.id).where(ClaimRow.source_id == source_id).order_by(ClaimRow.id)
        steps = (
            select(TrajectoryStepRow.id)
            .where(
                TrajectoryStepRow.workspace_id == workspace_id,
                TrajectoryStepRow.source_ids_json.contains(f'"{source_id}"', autoescape=True),
            )
            .order_by(TrajectoryStepRow.id)
        )
        async with self._repositories.transaction() as session:
            chunk_count = (await session.execute(chunks)).scalar_one()
            claim_ids = list((await session.scalars(claims)).all())
            step_ids = list((await session.scalars(steps)).all())
        return SourceDetail(
            source=source_view(row),
            abstract=row.abstract,
            pdf_url=_pdf_url(row),
            screen=_json_object(row.screen_json),
            appraisal=_json_object(row.appraisal_json),
            extra=_json_object(row.extra_json),
            chunk_count=chunk_count,
            claim_ids=claim_ids,
            trajectory_step_ids=step_ids,
        )

    # --- trajectory -------------------------------------------------------------------------

    async def trajectory_page(
        self, workspace_id: str, filters: TrajectoryFilter, *, after: int | None, limit: int
    ) -> TrajectoryPage:
        await self.require_workspace(workspace_id)
        criteria = filters.criteria()
        rows = await self._repositories.list_trajectory_steps(
            workspace_id, *criteria, after=after, limit=limit
        )
        total_statement = (
            select(func.count())
            .select_from(TrajectoryStepRow)
            .where(TrajectoryStepRow.workspace_id == workspace_id, *criteria)
        )
        async with self._repositories.transaction() as session:
            total = (await session.execute(total_statement)).scalar_one()
        return TrajectoryPage(
            steps=[to_summary(row) for row in rows],
            next_after=rows[-1].id if rows and len(rows) == limit else None,
            total=total,
        )

    async def trajectory_step(self, workspace_id: str, step_id: int) -> TrajectoryStep | None:
        await self.require_workspace(workspace_id)
        row = await self._repositories.get_trajectory_step(step_id)
        if row is None or row.workspace_id != workspace_id:
            return None
        return to_step(row)

    async def trajectory_summary(
        self, workspace_id: str, step_id: int
    ) -> TrajectoryStepSummary | None:
        row = await self._repositories.get_trajectory_step(step_id)
        if row is None or row.workspace_id != workspace_id:
            return None
        return to_summary(row)

    async def steps_after(
        self, workspace_id: str, after: int | None, *, limit: int = STREAM_PAGE
    ) -> list[TrajectoryStepSummary]:
        rows = await self._repositories.list_trajectory_steps(
            workspace_id, after=after, limit=limit
        )
        return [to_summary(row) for row in rows]

    async def closed_steps(
        self, workspace_id: str, step_ids: Collection[int]
    ) -> list[TrajectoryStepSummary]:
        """Steps among `step_ids` that are no longer RUNNING."""

        if not step_ids:
            return []
        statement = (
            select(TrajectoryStepRow)
            .where(
                TrajectoryStepRow.workspace_id == workspace_id,
                TrajectoryStepRow.id.in_(list(step_ids)),
                TrajectoryStepRow.status != TrajectoryStatus.RUNNING,
            )
            .order_by(TrajectoryStepRow.id)
        )
        async with self._repositories.transaction() as session:
            rows = (await session.scalars(statement)).all()
        return [to_summary(row) for row in rows]

    async def running_step_ids(self, workspace_id: str, up_to: int) -> set[int]:
        statement = select(TrajectoryStepRow.id).where(
            TrajectoryStepRow.workspace_id == workspace_id,
            TrajectoryStepRow.id <= up_to,
            TrajectoryStepRow.status == TrajectoryStatus.RUNNING,
        )
        async with self._repositories.transaction() as session:
            return set((await session.scalars(statement)).all())

    # --- startup recovery -------------------------------------------------------------------

    async def recover_interrupted_runs(self, error: str) -> int:
        """Mark RUNNING workspaces FAILED (with a STATUS event) and close RUNNING steps as ERROR.

        Call once at startup, before any run can start. Returns the number of workspaces.
        """

        workspaces = (
            update(WorkspaceRow)
            .where(WorkspaceRow.status == WorkspaceStatus.RUNNING)
            .values(status=WorkspaceStatus.FAILED, error=error)
            .returning(WorkspaceRow.id, WorkspaceRow.current_stage)
        )
        async with self._repositories.transaction() as session:
            interrupted = (await session.execute(workspaces)).all()
        for workspace_id, stage in interrupted:
            await self._repositories.append_event(
                workspace_id,
                _safe_enum(StageId, stage) or StageId.INGEST,
                TraceEventKind.STATUS,
                f"Workspace {WorkspaceStatus.FAILED}: {error}",
                {"status": WorkspaceStatus.FAILED, "error": error},
            )
        steps = (
            update(TrajectoryStepRow)
            .where(TrajectoryStepRow.status == TrajectoryStatus.RUNNING)
            .values(status=TrajectoryStatus.ERROR, ended_at=utc_now(), error=error)
        )
        async with self._repositories.transaction() as session:
            await session.execute(steps)
        return len(interrupted)

    async def build_state(self, workspace_id: str) -> WorkspaceState:
        row = await self.require_workspace(workspace_id)
        repositories = self._repositories
        sources = await repositories.list_sources(workspace_id)
        claims = await repositories.list_claims(workspace_id)
        highlights = await repositories.list_highlights(workspace_id)
        highlighted_paths = {source.id: source.highlighted_path for source in sources}
        highlight_ids: defaultdict[str, list[str]] = defaultdict(list)
        for highlight in highlights:
            highlight_ids[highlight.claim_id].append(highlight.id)
        return WorkspaceState(
            workspace=workspace_view(row),
            decomposition=parse_decomposition(row),
            queries=[_query_view(q) for q in await repositories.list_search_queries(workspace_id)],
            sources=[_source_view(source) for source in sources],
            funnel=compute_funnel(source.status for source in sources),
            claims=[_claim_view(claim, highlight_ids[claim.id]) for claim in claims],
            highlights=[_highlight_view(h, highlighted_paths.get(h.source_id)) for h in highlights],
            synthesis=Synthesis.model_validate_json(row.synthesis_json)
            if row.synthesis_json
            else None,
            ui_components=parse_ui_components(row),
            last_event_id=await self.last_event_id(workspace_id),
        )

    async def build_graph(self, workspace_id: str) -> GraphView:
        await self.require_workspace(workspace_id)
        sources = await self._repositories.list_sources(workspace_id)
        links = await self._repositories.list_source_links(workspace_id)
        return GraphView(
            nodes=[
                GraphNode(
                    id=s.id,
                    label=s.title,
                    status=SourceStatus(s.status),
                    origin=SourceOrigin(s.origin),
                )
                for s in sources
            ],
            edges=[
                GraphEdge(
                    source=link.from_source_id,
                    target=link.to_source_id,
                    kind=SourceLinkKind(link.kind),
                )
                for link in links
            ],
        )

    async def last_event_id(self, workspace_id: str) -> int | None:
        statement = select(func.max(TraceEventRow.id)).where(
            TraceEventRow.workspace_id == workspace_id
        )
        async with self._repositories.transaction() as session:
            return (await session.execute(statement)).scalar_one_or_none()

    async def stream_finished(self, workspace_id: str, last_id: int | None) -> bool:
        """True when the run is terminal and the reader has seen every event."""

        row = await self.require_workspace(workspace_id)
        if WorkspaceStatus(row.status) not in TERMINAL_STATUSES:
            return False
        latest = await self.last_event_id(workspace_id)
        return latest is None or (last_id or 0) >= latest

    async def replace_decomposition(
        self, workspace_id: str, decomposition: PicotsDecomposition | ScopeDecomposition
    ) -> WorkspaceState:
        """Write the decomposition only while the workspace is AWAITING_REVIEW (one statement)."""

        statement = (
            update(WorkspaceRow)
            .where(
                WorkspaceRow.id == workspace_id,
                WorkspaceRow.status == WorkspaceStatus.AWAITING_REVIEW,
            )
            .values(decomposition_json=decomposition.model_dump_json())
            .returning(WorkspaceRow.id)
        )
        async with self._repositories.transaction() as session:
            updated = (await session.execute(statement)).one_or_none()
        if updated is None:
            row = await self.require_workspace(workspace_id)
            raise WorkspaceStatusError(workspace_id, row.status, WorkspaceStatus.AWAITING_REVIEW)
        return await self.build_state(workspace_id)


def is_terminal_event(event: TraceEvent) -> bool:
    return event.kind == TraceEventKind.STATUS and event.payload.get("status") in TERMINAL_STATUSES
