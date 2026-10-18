"""Reads for retrieval and grounded chat: chunks by source and tier, recent chat turns."""

from collections.abc import Collection

from sqlalchemy import select

from hannovators_deep_researcher.models.enums import ChunkTier
from hannovators_deep_researcher.persistence.repositories import Repositories
from hannovators_deep_researcher.persistence.tables import ChatMessageRow, ChunkRow


async def list_retrieval_chunks(
    repositories: Repositories,
    workspace_id: str,
    *,
    source_ids: Collection[str] | None = None,
    tiers: Collection[ChunkTier] | None = None,
) -> list[ChunkRow]:
    """Chunks of the workspace, optionally limited to some sources and tiers, in reading order."""

    statement = select(ChunkRow).where(ChunkRow.workspace_id == workspace_id)
    if source_ids is not None:
        statement = statement.where(ChunkRow.source_id.in_(list(source_ids)))
    if tiers is not None:
        statement = statement.where(ChunkRow.tier.in_(list(tiers)))
    statement = statement.order_by(ChunkRow.source_id, ChunkRow.ordinal)
    async with repositories.transaction() as session:
        return list((await session.scalars(statement)).all())


async def recent_chat_messages(
    repositories: Repositories, workspace_id: str, *, limit: int
) -> list[ChatMessageRow]:
    """The last `limit` chat messages, oldest first."""

    statement = (
        select(ChatMessageRow)
        .where(ChatMessageRow.workspace_id == workspace_id)
        .order_by(ChatMessageRow.created_at.desc(), ChatMessageRow.id.desc())
        .limit(limit)
    )
    async with repositories.transaction() as session:
        rows = list((await session.scalars(statement)).all())
    return rows[::-1]
