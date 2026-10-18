"""Empty baseline before application persistence tables are introduced."""

from collections.abc import Sequence

revision: str = "0001_empty_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial Alembic revision marker without application tables."""


def downgrade() -> None:
    """Remove the initial revision marker."""
