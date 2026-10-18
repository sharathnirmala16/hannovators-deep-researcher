"""Trajectory steps, chat messages, and evidence level, stance, and search intent on sources."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_trajectory_chat"
down_revision: str | None = "0002_core_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID = sa.String(36)
ENUM = sa.String(32)
SOURCE_COLUMNS = ("evidence_level", "stance", "search_intent")


def upgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        for name in SOURCE_COLUMNS:
            batch.add_column(sa.Column(name, ENUM, nullable=True))

    op.create_table(
        "trajectory_steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("trajectory_steps.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor", ENUM, nullable=False),
        sa.Column("kind", ENUM, nullable=False),
        sa.Column("stage", ENUM, nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("target", sa.Text(), nullable=True),
        sa.Column("status", ENUM, nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("source_ids_json", sa.Text(), nullable=False),
        sa.Column("outcome", ENUM, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sqlite_autoincrement=True,
    )
    op.create_index("ix_trajectory_steps_workspace_id", "trajectory_steps", ["workspace_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", ID, primary_key=True),
        sa.Column(
            "workspace_id", ID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("role", ENUM, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations_json", sa.Text(), nullable=False),
        sa.Column(
            "trajectory_step_id",
            sa.Integer(),
            sa.ForeignKey("trajectory_steps.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_chat_messages_workspace_id", "chat_messages", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("trajectory_steps")
    with op.batch_alter_table("sources") as batch:
        for name in SOURCE_COLUMNS:
            batch.drop_column(name)
