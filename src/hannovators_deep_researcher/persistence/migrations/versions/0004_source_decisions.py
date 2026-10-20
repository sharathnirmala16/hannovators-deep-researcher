"""Researcher decisions on sources: a manual include or exclude with its reason."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_source_decisions"
down_revision: str | None = "0003_trajectory_chat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.add_column(sa.Column("decision_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.drop_column("decision_json")
