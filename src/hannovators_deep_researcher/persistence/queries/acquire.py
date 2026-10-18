"""Citation links for acquired sources. Duplicate links are skipped, never raised."""

from collections.abc import Iterable

from sqlalchemy import select

from hannovators_deep_researcher.models.enums import SourceLinkKind
from hannovators_deep_researcher.persistence.repositories import Repositories
from hannovators_deep_researcher.persistence.tables import SourceLinkRow


async def add_links(
    repositories: Repositories,
    workspace_id: str,
    links: Iterable[tuple[str, str, SourceLinkKind]],
) -> int:
    """Insert `(from_source_id, to_source_id, kind)` links that are new; return how many."""

    wanted = {link for link in links if link[0] != link[1]}
    if not wanted:
        return 0
    statement = select(
        SourceLinkRow.from_source_id, SourceLinkRow.to_source_id, SourceLinkRow.kind
    ).where(SourceLinkRow.workspace_id == workspace_id)
    async with repositories.transaction() as session:
        existing = {(row[0], row[1], row[2]) for row in (await session.execute(statement)).all()}
        new = sorted(link for link in wanted if link not in existing)
        session.add_all(
            SourceLinkRow(
                workspace_id=workspace_id, from_source_id=source, to_source_id=target, kind=kind
            )
            for source, target, kind in new
        )
    return len(new)
