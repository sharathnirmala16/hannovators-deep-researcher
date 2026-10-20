"""Queries for researcher decisions on sources and the re-synthesis that applies them."""

from sqlalchemy import delete, select

from hannovators_deep_researcher.models.enums import ClaimKind
from hannovators_deep_researcher.persistence.repositories import Repositories
from hannovators_deep_researcher.persistence.tables import ClaimRow, SourceRow


async def decided_sources(repositories: Repositories, workspace_id: str) -> list[SourceRow]:
    """Sources that carry a researcher decision, oldest first."""

    statement = (
        select(SourceRow)
        .where(SourceRow.workspace_id == workspace_id, SourceRow.decision_json.is_not(None))
        .order_by(SourceRow.created_at, SourceRow.id)
    )
    async with repositories.transaction() as session:
        return list((await session.scalars(statement)).all())


async def delete_recommendation_claims(repositories: Repositories, workspace_id: str) -> int:
    """Remove the synthesis recommendation claims, so a new synthesis writes the only one."""

    statement = delete(ClaimRow).where(
        ClaimRow.workspace_id == workspace_id,
        ClaimRow.kind == ClaimKind.RECOMMENDATION,
        ClaimRow.source_id.is_(None),
    )
    async with repositories.transaction() as session:
        result = await session.execute(statement)
    return int(getattr(result, "rowcount", 0) or 0)
