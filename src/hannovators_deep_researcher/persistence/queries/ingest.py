"""Chunk and seed-claim storage for seed and acquired documents, one transaction per replace."""

from collections.abc import Sequence

from sqlalchemy import delete, func, select

from hannovators_deep_researcher.persistence.repositories import Repositories
from hannovators_deep_researcher.persistence.tables import ChunkRow, ClaimRow


async def replace_chunks(
    repositories: Repositories, source_id: str, rows: Sequence[ChunkRow]
) -> list[ChunkRow]:
    """Delete every chunk of `source_id` and insert `rows`, atomically."""

    async with repositories.transaction() as session:
        await session.execute(delete(ChunkRow).where(ChunkRow.source_id == source_id))
        session.add_all(rows)
    return list(rows)


async def chunk_counts(repositories: Repositories, workspace_id: str) -> dict[tuple[str, str], int]:
    """`{(source_id, tier): count}` for every source in the workspace that has chunks."""

    statement = (
        select(ChunkRow.source_id, ChunkRow.tier, func.count())
        .where(ChunkRow.workspace_id == workspace_id)
        .group_by(ChunkRow.source_id, ChunkRow.tier)
    )
    async with repositories.transaction() as session:
        rows = (await session.execute(statement)).all()
    return {(source_id, tier): int(count) for source_id, tier, count in rows}


async def replace_labelled_claims(
    repositories: Repositories, source_id: str, label: str, rows: Sequence[ClaimRow]
) -> list[ClaimRow]:
    """Delete the claims of `source_id` that carry `label` and insert `rows`, atomically."""

    async with repositories.transaction() as session:
        await session.execute(
            delete(ClaimRow).where(ClaimRow.source_id == source_id, ClaimRow.label == label)
        )
        session.add_all(rows)
    return list(rows)
