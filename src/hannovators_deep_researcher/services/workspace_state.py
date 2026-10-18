"""Builds `WorkspaceState` and `GraphView` from the database (PLAN.md section 4.4).

Stored file paths are relative to `data/`, so a `/files/` prefix gives their public URL.
"""

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from enum import StrEnum

from pydantic import TypeAdapter
from sqlalchemy import func, select, update

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
    SourceView,
    Synthesis,
    WorkspaceSettings,
    WorkspaceState,
    WorkspaceView,
)
from hannovators_deep_researcher.models.enums import (
    ClaimKind,
    ClaimVerdict,
    Directness,
    HighlightMethod,
    RejectionCode,
    RequestedDomainMode,
    SourceLinkKind,
    SourceOrigin,
    SourceStatus,
    StageId,
    TraceEventKind,
    UiComponentId,
    WorkspaceStatus,
)
from hannovators_deep_researcher.models.events import TraceEvent
from hannovators_deep_researcher.persistence.repositories import Repositories
from hannovators_deep_researcher.persistence.tables import (
    ClaimRow,
    HighlightRow,
    SearchQueryRow,
    SourceRow,
    TraceEventRow,
    WorkspaceRow,
)

FILES_PREFIX = "/files/"
TERMINAL_STATUSES = frozenset({WorkspaceStatus.COMPLETED, WorkspaceStatus.FAILED})
_UI_COMPONENTS = TypeAdapter(list[UiComponentId])
_PAST_SCREENING = (
    SourceStatus.SCREEN_PROMOTED,
    SourceStatus.APPRAISE_PROMOTED,
    SourceStatus.APPRAISE_DISCOUNTED,
    SourceStatus.ACQUIRE_FAILED,
)


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


def _source_view(row: SourceRow) -> SourceView:
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
    )


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


class WorkspaceStateService:
    """Read models for the HTTP API, plus the guarded decomposition update."""

    def __init__(self, repositories: Repositories) -> None:
        self._repositories = repositories

    async def require_workspace(self, workspace_id: str) -> WorkspaceRow:
        row = await self._repositories.get_workspace(workspace_id)
        if row is None:
            raise WorkspaceNotFoundError(workspace_id)
        return row

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
