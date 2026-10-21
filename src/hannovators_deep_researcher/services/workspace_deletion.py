"""Delete a workspace: its rows in one transaction, then its folder under `data/workspaces/`.

The workspace has no trajectory left to record into afterwards, so the deletion is logged.
"""

import asyncio
import logging
import shutil
from pathlib import Path

from sqlalchemy import delete

from hannovators_deep_researcher.models.enums import WorkspaceStatus
from hannovators_deep_researcher.persistence.repositories import Repositories
from hannovators_deep_researcher.persistence.tables import (
    ChatMessageRow,
    ChunkRow,
    ClaimRow,
    HighlightRow,
    SearchQueryRow,
    SourceLinkRow,
    SourceRow,
    TraceEventRow,
    TrajectoryStepRow,
    WorkspaceRow,
)
from hannovators_deep_researcher.services.documents.files import (
    UnsafePathError,
    resolve_data_path,
    workspace_path,
)
from hannovators_deep_researcher.services.workspace_state import WorkspaceNotFoundError

logger = logging.getLogger(__name__)

_CHILD_TABLES = (
    HighlightRow,
    ClaimRow,
    ChunkRow,
    SourceLinkRow,
    ChatMessageRow,
    TraceEventRow,
    TrajectoryStepRow,
    SourceRow,
    SearchQueryRow,
)
"""Workspace children, leaves first. The foreign keys cascade as well; the explicit deletes give
the same result on a connection without `PRAGMA foreign_keys=ON`."""


class WorkspaceBusyError(Exception):
    """A run, revision, or deep research task is active for the workspace."""

    def __init__(self, workspace_id: str) -> None:
        super().__init__(
            f"workspace {workspace_id} is running; stop or wait for the run to finish first"
        )
        self.workspace_id = workspace_id


async def delete_workspace(
    repositories: Repositories, workspace_id: str, *, busy: bool, root: Path | None = None
) -> None:
    """Delete the workspace row and every child row, then remove `workspaces/<id>/`.

    `busy` is True when a background task is active for the workspace. Raises
    `WorkspaceNotFoundError` for an unknown or unsafe id and `WorkspaceBusyError` while the
    workspace is RUNNING or busy. The folder is removed after the commit; a missing folder is fine.
    """

    try:
        folder = resolve_data_path(workspace_path(workspace_id), root=root)
    except UnsafePathError as error:
        raise WorkspaceNotFoundError(workspace_id) from error
    if busy:
        raise WorkspaceBusyError(workspace_id)
    if not await _delete_rows(repositories, workspace_id):
        if await repositories.get_workspace(workspace_id) is None:
            raise WorkspaceNotFoundError(workspace_id)
        raise WorkspaceBusyError(workspace_id)
    logger.info("Deleted workspace %s", workspace_id)
    await asyncio.to_thread(_remove_folder, folder)


async def _delete_rows(repositories: Repositories, workspace_id: str) -> bool:
    """Delete the row unless it is RUNNING (one guarded statement), then its children."""

    guarded = (
        delete(WorkspaceRow)
        .where(WorkspaceRow.id == workspace_id, WorkspaceRow.status != WorkspaceStatus.RUNNING)
        .returning(WorkspaceRow.id)
    )
    async with repositories.transaction() as session:
        if (await session.execute(guarded)).one_or_none() is None:
            return False
        for table in _CHILD_TABLES:
            await session.execute(delete(table).where(table.workspace_id == workspace_id))
    return True


def _remove_folder(folder: Path) -> None:
    try:
        shutil.rmtree(folder)
    except FileNotFoundError:
        return
    except OSError:
        logger.warning(
            "Could not remove every file of deleted workspace at %s", folder, exc_info=True
        )
        return
    logger.info("Removed workspace files at %s", folder)
