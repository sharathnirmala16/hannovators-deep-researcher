"""SQLAlchemy tables for the core schema (PLAN.md section 4.2, revision `0002_core_schema`).

Enum columns store the `StrEnum` value. `*_json` columns hold JSON text that a Pydantic model in
`models/` validates. File paths are relative to `data/` with `/` separators.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Dialect,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from hannovators_deep_researcher.persistence.base import Base

ID_LENGTH = 36
ENUM_LENGTH = 32


def new_id() -> str:
    """Return a new UUID string primary key."""

    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class UtcDateTime(TypeDecorator[datetime]):
    """Store datetimes as naive UTC and read them back as UTC-aware values."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("datetime values must be timezone-aware")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


def _id_column() -> Mapped[str]:
    return mapped_column(String(ID_LENGTH), primary_key=True, default=new_id)


def _workspace_fk() -> Mapped[str]:
    return mapped_column(
        String(ID_LENGTH), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )


def _source_fk() -> Mapped[str]:
    return mapped_column(
        String(ID_LENGTH), ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(UtcDateTime(), default=utc_now)


class WorkspaceRow(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = _id_column()
    research_question: Mapped[str] = mapped_column(Text)
    domain_mode: Mapped[str] = mapped_column(String(ENUM_LENGTH))
    status: Mapped[str] = mapped_column(String(ENUM_LENGTH))
    current_stage: Mapped[str | None] = mapped_column(String(ENUM_LENGTH))
    auto_continue: Mapped[bool] = mapped_column(Boolean, default=False)
    settings_json: Mapped[str] = mapped_column(Text)
    decomposition_json: Mapped[str | None] = mapped_column(Text)
    synthesis_json: Mapped[str | None] = mapped_column(Text)
    ui_components_json: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=utc_now, onupdate=utc_now)


class SearchQueryRow(Base):
    __tablename__ = "search_queries"

    id: Mapped[str] = _id_column()
    workspace_id: Mapped[str] = _workspace_fk()
    iteration: Mapped[int] = mapped_column(Integer)
    tool: Mapped[str] = mapped_column(String(64))
    core_query: Mapped[str] = mapped_column(Text)
    applied_filters: Mapped[str] = mapped_column(Text, default="")
    raw_hit_count: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    refinement_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class SourceRow(Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("workspace_id", "external_id", name="uq_sources_workspace_external"),
    )

    id: Mapped[str] = _id_column()
    workspace_id: Mapped[str] = _workspace_fk()
    origin: Mapped[str] = mapped_column(String(ENUM_LENGTH))
    external_id: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    authors_json: Mapped[str] = mapped_column(Text, default="[]")
    year: Mapped[int | None] = mapped_column(Integer)
    venue: Mapped[str | None] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    pdf_url: Mapped[str | None] = mapped_column(Text)
    study_design: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(ENUM_LENGTH))
    found_by_query_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH), ForeignKey("search_queries.id", ondelete="SET NULL")
    )
    raw_path: Mapped[str | None] = mapped_column(Text)
    highlighted_path: Mapped[str | None] = mapped_column(Text)
    screen_score: Mapped[float | None] = mapped_column(Float)
    screen_z: Mapped[float | None] = mapped_column(Float)
    screen_votes: Mapped[int | None] = mapped_column(Integer)
    screen_json: Mapped[str | None] = mapped_column(Text)
    m_score: Mapped[int | None] = mapped_column(Integer)
    directness: Mapped[str | None] = mapped_column(String(ENUM_LENGTH))
    rob2_json: Mapped[str | None] = mapped_column(Text)
    appraisal_json: Mapped[str | None] = mapped_column(Text)
    rejection_code: Mapped[str | None] = mapped_column(String(ENUM_LENGTH))
    decision_explanation: Mapped[str | None] = mapped_column(Text)
    extra_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class SourceLinkRow(Base):
    __tablename__ = "source_links"
    __table_args__ = (
        UniqueConstraint(
            "from_source_id", "to_source_id", "kind", name="uq_source_links_from_to_kind"
        ),
    )

    id: Mapped[str] = _id_column()
    workspace_id: Mapped[str] = _workspace_fk()
    from_source_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("sources.id", ondelete="CASCADE")
    )
    to_source_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(ENUM_LENGTH))


class ChunkRow(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = _id_column()
    workspace_id: Mapped[str] = _workspace_fk()
    source_id: Mapped[str] = _source_fk()
    tier: Mapped[str] = mapped_column(String(ENUM_LENGTH))
    ordinal: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    bbox_json: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary)
    token_count: Mapped[int | None] = mapped_column(Integer)


class ClaimRow(Base):
    __tablename__ = "claims"

    id: Mapped[str] = _id_column()
    workspace_id: Mapped[str] = _workspace_fk()
    source_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH), ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(ENUM_LENGTH))
    label: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    quote: Mapped[str | None] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(String(ENUM_LENGTH))
    confidence: Mapped[float | None] = mapped_column(Float)
    payload_json: Mapped[str | None] = mapped_column(Text)


class HighlightRow(Base):
    __tablename__ = "highlights"

    id: Mapped[str] = _id_column()
    workspace_id: Mapped[str] = _workspace_fk()
    source_id: Mapped[str] = _source_fk()
    claim_id: Mapped[str] = mapped_column(
        String(ID_LENGTH), ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[str | None] = mapped_column(
        String(ID_LENGTH), ForeignKey("chunks.id", ondelete="SET NULL")
    )
    page: Mapped[int] = mapped_column(Integer)
    rects_json: Mapped[str] = mapped_column(Text, default="[]")
    method: Mapped[str] = mapped_column(String(ENUM_LENGTH))
    score: Mapped[float | None] = mapped_column(Float)
    color: Mapped[str] = mapped_column(String(ENUM_LENGTH))


class TraceEventRow(Base):
    __tablename__ = "trace_events"
    __table_args__ = ({"sqlite_autoincrement": True},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = _workspace_fk()
    stage: Mapped[str] = mapped_column(String(ENUM_LENGTH))
    kind: Mapped[str] = mapped_column(String(ENUM_LENGTH))
    message: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
