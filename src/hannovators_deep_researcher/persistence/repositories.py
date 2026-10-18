"""Generic create/get/list/update helpers that every pipeline stage shares.

Each call runs in its own short transaction, so concurrent stage work never shares a session.
Lanes that need other queries add `persistence/queries/<lane>.py` and use `transaction()`.

`*_json` fields accept a JSON string, a Pydantic model, or plain JSON values (serialized here).
Rows come back detached with every column loaded.
"""

import json
from collections.abc import AsyncIterator, Collection, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any

from pydantic_core import to_json
from sqlalchemy import ColumnElement, inspect, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from hannovators_deep_researcher.models.contracts import WorkspaceSettings
from hannovators_deep_researcher.models.enums import (
    ChunkTier,
    ClaimKind,
    ClaimVerdict,
    HighlightMethod,
    RequestedDomainMode,
    SourceLinkKind,
    SourceOrigin,
    SourceStatus,
    StageId,
    TraceEventKind,
    WorkspaceStatus,
)
from hannovators_deep_researcher.models.events import TraceEvent
from hannovators_deep_researcher.persistence.base import Base
from hannovators_deep_researcher.persistence.tables import (
    ChatMessageRow,
    ChunkRow,
    ClaimRow,
    HighlightRow,
    SearchQueryRow,
    SourceLinkRow,
    SourceRow,
    TraceEventRow,
    TrajectoryStepRow,
    WorkspaceRow,
)

DEFAULT_EVENT_PAGE = 500


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory whose rows stay readable after commit."""

    return async_sessionmaker(engine, expire_on_commit=False)


def _column_values(model: type[Base], fields: Mapping[str, object]) -> dict[str, object]:
    """Check field names against the table and serialize `*_json` values."""

    columns = set(inspect(model).columns.keys())
    unknown = sorted(set(fields) - columns)
    if unknown:
        raise TypeError(f"{model.__tablename__} has no column(s): {', '.join(unknown)}")
    return {
        name: to_json(value).decode()
        if name.endswith("_json") and value is not None and not isinstance(value, str)
        else value
        for name, value in fields.items()
    }


def _to_trace_event(row: TraceEventRow) -> TraceEvent:
    return TraceEvent(
        id=row.id,
        workspace_id=row.workspace_id,
        stage=StageId(row.stage),
        kind=TraceEventKind(row.kind),
        message=row.message,
        payload=json.loads(row.payload_json) if row.payload_json else {},
        created_at=row.created_at,
    )


class Repositories:
    """Repository helpers over one async session factory."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Open a session with a transaction that commits on success and rolls back on error."""

        async with self._session_factory() as session, session.begin():
            yield session

    # --- Generic helpers (any table) ---------------------------------------------------

    async def add[RowT: Base](self, row: RowT) -> RowT:
        async with self.transaction() as session:
            session.add(row)
        return row

    async def add_all[RowT: Base](self, rows: Sequence[RowT]) -> list[RowT]:
        async with self.transaction() as session:
            session.add_all(rows)
        return list(rows)

    async def get[RowT: Base](self, model: type[RowT], row_id: str | int) -> RowT | None:
        async with self.transaction() as session:
            return await session.get(model, row_id)

    async def update[RowT: Base](self, model: type[RowT], row_id: str | int, **fields: Any) -> RowT:
        """Set the given columns on one row. Raises `LookupError` when the row is missing."""

        values = _column_values(model, fields)
        async with self.transaction() as session:
            row = await session.get(model, row_id)
            if row is None:
                raise LookupError(f"{model.__tablename__} row {row_id!r} not found")
            for name, value in values.items():
                setattr(row, name, value)
        return row

    async def list_for_workspace[RowT: Base](
        self,
        model: type[RowT],
        workspace_id: str,
        *criteria: ColumnElement[bool],
        order_by: Sequence[str] = ("id",),
    ) -> list[RowT]:
        table = model.__table__
        statement = (
            select(model)
            .where(table.c.workspace_id == workspace_id, *criteria)
            .order_by(*(table.c[name] for name in order_by))
        )
        async with self.transaction() as session:
            return list((await session.scalars(statement)).all())

    # --- workspaces --------------------------------------------------------------------

    async def create_workspace(
        self,
        *,
        research_question: str,
        domain_mode: RequestedDomainMode,
        settings: WorkspaceSettings,
        auto_continue: bool = False,
    ) -> WorkspaceRow:
        return await self.add(
            WorkspaceRow(
                research_question=research_question,
                domain_mode=domain_mode,
                status=WorkspaceStatus.CREATED,
                auto_continue=auto_continue,
                settings_json=settings.model_dump_json(),
            )
        )

    async def get_workspace(self, workspace_id: str) -> WorkspaceRow | None:
        return await self.get(WorkspaceRow, workspace_id)

    async def list_workspaces(self) -> list[WorkspaceRow]:
        statement = select(WorkspaceRow).order_by(WorkspaceRow.created_at, WorkspaceRow.id)
        async with self.transaction() as session:
            return list((await session.scalars(statement)).all())

    async def update_workspace_fields(self, workspace_id: str, **fields: Any) -> WorkspaceRow:
        return await self.update(WorkspaceRow, workspace_id, **fields)

    # --- search_queries ----------------------------------------------------------------

    async def create_search_query(
        self, workspace_id: str, *, iteration: int, tool: str, core_query: str, **fields: Any
    ) -> SearchQueryRow:
        values = _column_values(SearchQueryRow, fields)
        return await self.add(
            SearchQueryRow(
                workspace_id=workspace_id,
                iteration=iteration,
                tool=tool,
                core_query=core_query,
                **values,
            )
        )

    async def list_search_queries(self, workspace_id: str) -> list[SearchQueryRow]:
        return await self.list_for_workspace(
            SearchQueryRow, workspace_id, order_by=("created_at", "id")
        )

    # --- sources -----------------------------------------------------------------------

    async def create_source(
        self,
        workspace_id: str,
        *,
        origin: SourceOrigin,
        external_id: str,
        title: str,
        status: SourceStatus,
        **fields: Any,
    ) -> SourceRow:
        """Insert a source. A duplicate `(workspace_id, external_id)` raises `IntegrityError`."""

        values = _column_values(SourceRow, fields)
        return await self.add(
            SourceRow(
                workspace_id=workspace_id,
                origin=origin,
                external_id=external_id,
                title=title,
                status=status,
                **values,
            )
        )

    async def get_source(self, source_id: str) -> SourceRow | None:
        return await self.get(SourceRow, source_id)

    async def list_sources(
        self, workspace_id: str, statuses: Collection[SourceStatus] | None = None
    ) -> list[SourceRow]:
        criteria = () if statuses is None else (SourceRow.status.in_(list(statuses)),)
        return await self.list_for_workspace(
            SourceRow, workspace_id, *criteria, order_by=("created_at", "id")
        )

    async def update_source_fields(self, source_id: str, **fields: Any) -> SourceRow:
        return await self.update(SourceRow, source_id, **fields)

    # --- source_links ------------------------------------------------------------------

    async def create_source_link(
        self, workspace_id: str, *, from_source_id: str, to_source_id: str, kind: SourceLinkKind
    ) -> SourceLinkRow:
        return await self.add(
            SourceLinkRow(
                workspace_id=workspace_id,
                from_source_id=from_source_id,
                to_source_id=to_source_id,
                kind=kind,
            )
        )

    async def list_source_links(self, workspace_id: str) -> list[SourceLinkRow]:
        return await self.list_for_workspace(SourceLinkRow, workspace_id)

    # --- chunks ------------------------------------------------------------------------

    async def create_chunk(
        self,
        workspace_id: str,
        *,
        source_id: str,
        tier: ChunkTier,
        ordinal: int,
        text: str,
        **fields: Any,
    ) -> ChunkRow:
        values = _column_values(ChunkRow, fields)
        return await self.add(
            ChunkRow(
                workspace_id=workspace_id,
                source_id=source_id,
                tier=tier,
                ordinal=ordinal,
                text=text,
                **values,
            )
        )

    async def list_chunks(self, workspace_id: str, source_id: str | None = None) -> list[ChunkRow]:
        criteria = () if source_id is None else (ChunkRow.source_id == source_id,)
        return await self.list_for_workspace(
            ChunkRow, workspace_id, *criteria, order_by=("source_id", "ordinal")
        )

    # --- claims ------------------------------------------------------------------------

    async def create_claim(
        self,
        workspace_id: str,
        *,
        kind: ClaimKind,
        label: str,
        text: str,
        verdict: ClaimVerdict,
        **fields: Any,
    ) -> ClaimRow:
        values = _column_values(ClaimRow, fields)
        return await self.add(
            ClaimRow(
                workspace_id=workspace_id,
                kind=kind,
                label=label,
                text=text,
                verdict=verdict,
                **values,
            )
        )

    async def list_claims(self, workspace_id: str) -> list[ClaimRow]:
        return await self.list_for_workspace(ClaimRow, workspace_id)

    # --- highlights --------------------------------------------------------------------

    async def create_highlight(
        self,
        workspace_id: str,
        *,
        source_id: str,
        claim_id: str,
        page: int,
        method: HighlightMethod,
        color: str,
        **fields: Any,
    ) -> HighlightRow:
        values = _column_values(HighlightRow, fields)
        return await self.add(
            HighlightRow(
                workspace_id=workspace_id,
                source_id=source_id,
                claim_id=claim_id,
                page=page,
                method=method,
                color=color,
                **values,
            )
        )

    async def list_highlights(self, workspace_id: str) -> list[HighlightRow]:
        return await self.list_for_workspace(HighlightRow, workspace_id)

    # --- trace_events ------------------------------------------------------------------

    async def append_event(
        self,
        workspace_id: str,
        stage: StageId,
        kind: TraceEventKind,
        message: str,
        payload: Mapping[str, object] | None = None,
    ) -> TraceEvent:
        row = await self.add(
            TraceEventRow(
                workspace_id=workspace_id,
                stage=stage,
                kind=kind,
                message=message,
                payload_json=to_json(dict(payload)).decode() if payload else None,
            )
        )
        return _to_trace_event(row)

    # --- trajectory_steps ---------------------------------------------------------------

    async def add_trajectory_step(self, **fields: Any) -> TrajectoryStepRow:
        return await self.add(TrajectoryStepRow(**_column_values(TrajectoryStepRow, fields)))

    async def update_trajectory_step(self, step_id: int, **fields: Any) -> TrajectoryStepRow:
        return await self.update(TrajectoryStepRow, step_id, **fields)

    async def get_trajectory_step(self, step_id: int) -> TrajectoryStepRow | None:
        return await self.get(TrajectoryStepRow, step_id)

    async def list_trajectory_steps(
        self,
        workspace_id: str,
        *criteria: ColumnElement[bool],
        after: int | None = None,
        limit: int = DEFAULT_EVENT_PAGE,
    ) -> list[TrajectoryStepRow]:
        """Steps with `id > after`, oldest first. `criteria` filter on `TrajectoryStepRow`."""

        statement = (
            select(TrajectoryStepRow)
            .where(
                TrajectoryStepRow.workspace_id == workspace_id,
                TrajectoryStepRow.id > (after or 0),
                *criteria,
            )
            .order_by(TrajectoryStepRow.id)
            .limit(limit)
        )
        async with self.transaction() as session:
            return list((await session.scalars(statement)).all())

    # --- chat_messages -------------------------------------------------------------------

    async def add_chat_message(self, **fields: Any) -> ChatMessageRow:
        return await self.add(ChatMessageRow(**_column_values(ChatMessageRow, fields)))

    async def list_chat_messages(self, workspace_id: str) -> list[ChatMessageRow]:
        return await self.list_for_workspace(
            ChatMessageRow, workspace_id, order_by=("created_at", "id")
        )

    async def events_after(
        self, workspace_id: str, last_id: int | None, *, limit: int = DEFAULT_EVENT_PAGE
    ) -> list[TraceEvent]:
        """Events with `id > last_id` (all events when `last_id` is None), oldest first."""

        statement = (
            select(TraceEventRow)
            .where(TraceEventRow.workspace_id == workspace_id, TraceEventRow.id > (last_id or 0))
            .order_by(TraceEventRow.id)
            .limit(limit)
        )
        async with self.transaction() as session:
            rows = (await session.scalars(statement)).all()
        return [_to_trace_event(row) for row in rows]
