"""Core schema: workspaces, queries, sources, links, chunks, claims, highlights, trace events."""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0002_core_schema"
down_revision: str | None = "0001_empty_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID = sa.String(36)
ENUM = sa.String(32)


def _id() -> sa.Column[str]:
    return sa.Column("id", ID, primary_key=True)


def _fk(
    name: str, target: str, *, nullable: bool = False, ondelete: str = "CASCADE"
) -> sa.Column[str]:
    return sa.Column(name, ID, sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def _workspace_fk() -> sa.Column[str]:
    return _fk("workspace_id", "workspaces.id")


def _created_at() -> sa.Column[datetime]:
    return sa.Column("created_at", sa.DateTime(), nullable=False)


def _index(table: str, *columns: str) -> None:
    op.create_index(f"ix_{table}_{'_'.join(columns)}", table, list(columns))


def upgrade() -> None:
    """Create every core table with its constraints and indexes."""

    op.create_table(
        "workspaces",
        _id(),
        sa.Column("research_question", sa.Text(), nullable=False),
        sa.Column("domain_mode", ENUM, nullable=False),
        sa.Column("status", ENUM, nullable=False),
        sa.Column("current_stage", ENUM, nullable=True),
        sa.Column("auto_continue", sa.Boolean(), nullable=False),
        sa.Column("settings_json", sa.Text(), nullable=False),
        sa.Column("decomposition_json", sa.Text(), nullable=True),
        sa.Column("synthesis_json", sa.Text(), nullable=True),
        sa.Column("ui_components_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "search_queries",
        _id(),
        _workspace_fk(),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("tool", sa.String(64), nullable=False),
        sa.Column("core_query", sa.Text(), nullable=False),
        sa.Column("applied_filters", sa.Text(), nullable=False),
        sa.Column("raw_hit_count", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("refinement_note", sa.Text(), nullable=True),
        _created_at(),
    )
    _index("search_queries", "workspace_id")

    op.create_table(
        "sources",
        _id(),
        _workspace_fk(),
        sa.Column("origin", ENUM, nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("authors_json", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("venue", sa.Text(), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("pdf_url", sa.Text(), nullable=True),
        sa.Column("study_design", sa.Text(), nullable=True),
        sa.Column("status", ENUM, nullable=False),
        _fk("found_by_query_id", "search_queries.id", nullable=True, ondelete="SET NULL"),
        sa.Column("raw_path", sa.Text(), nullable=True),
        sa.Column("highlighted_path", sa.Text(), nullable=True),
        sa.Column("screen_score", sa.Float(), nullable=True),
        sa.Column("screen_z", sa.Float(), nullable=True),
        sa.Column("screen_votes", sa.Integer(), nullable=True),
        sa.Column("screen_json", sa.Text(), nullable=True),
        sa.Column("m_score", sa.Integer(), nullable=True),
        sa.Column("directness", ENUM, nullable=True),
        sa.Column("rob2_json", sa.Text(), nullable=True),
        sa.Column("appraisal_json", sa.Text(), nullable=True),
        sa.Column("rejection_code", ENUM, nullable=True),
        sa.Column("decision_explanation", sa.Text(), nullable=True),
        sa.Column("extra_json", sa.Text(), nullable=True),
        _created_at(),
        sa.UniqueConstraint("workspace_id", "external_id", name="uq_sources_workspace_external"),
    )
    _index("sources", "workspace_id")

    op.create_table(
        "source_links",
        _id(),
        _workspace_fk(),
        _fk("from_source_id", "sources.id"),
        _fk("to_source_id", "sources.id"),
        sa.Column("kind", ENUM, nullable=False),
        sa.UniqueConstraint(
            "from_source_id", "to_source_id", "kind", name="uq_source_links_from_to_kind"
        ),
    )
    _index("source_links", "workspace_id")
    _index("source_links", "to_source_id")

    op.create_table(
        "chunks",
        _id(),
        _workspace_fk(),
        _fk("source_id", "sources.id"),
        sa.Column("tier", ENUM, nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("bbox_json", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
    )
    _index("chunks", "workspace_id")
    _index("chunks", "source_id")

    op.create_table(
        "claims",
        _id(),
        _workspace_fk(),
        _fk("source_id", "sources.id", nullable=True),
        sa.Column("kind", ENUM, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("verdict", ENUM, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
    )
    _index("claims", "workspace_id")
    _index("claims", "source_id")

    op.create_table(
        "highlights",
        _id(),
        _workspace_fk(),
        _fk("source_id", "sources.id"),
        _fk("claim_id", "claims.id"),
        _fk("chunk_id", "chunks.id", nullable=True, ondelete="SET NULL"),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("rects_json", sa.Text(), nullable=False),
        sa.Column("method", ENUM, nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("color", ENUM, nullable=False),
    )
    _index("highlights", "workspace_id")
    _index("highlights", "source_id")
    _index("highlights", "claim_id")

    op.create_table(
        "trace_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _workspace_fk(),
        sa.Column("stage", ENUM, nullable=False),
        sa.Column("kind", ENUM, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        _created_at(),
        sqlite_autoincrement=True,
    )
    _index("trace_events", "workspace_id")


def downgrade() -> None:
    """Drop the core tables in reverse dependency order."""

    for table in (
        "trace_events",
        "highlights",
        "claims",
        "chunks",
        "source_links",
        "sources",
        "search_queries",
        "workspaces",
    ):
        op.drop_table(table)
