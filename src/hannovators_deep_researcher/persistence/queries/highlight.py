"""Highlight rows: replace the highlights of one source in one transaction."""

from collections.abc import Sequence

from sqlalchemy import delete

from hannovators_deep_researcher.persistence.repositories import Repositories
from hannovators_deep_researcher.persistence.tables import HighlightRow


async def replace_highlights(
    repositories: Repositories, source_id: str, rows: Sequence[HighlightRow]
) -> list[HighlightRow]:
    """Delete every highlight of `source_id` and insert `rows`, atomically."""

    async with repositories.transaction() as session:
        await session.execute(delete(HighlightRow).where(HighlightRow.source_id == source_id))
        session.add_all(rows)
    return list(rows)
