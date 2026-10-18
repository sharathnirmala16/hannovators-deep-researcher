"""Integration checks for repository constraints on a migrated SQLite database."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL
from sqlalchemy.exc import IntegrityError

from hannovators_deep_researcher.configuration.database import project_root
from hannovators_deep_researcher.infrastructure.database import create_database_engine
from hannovators_deep_researcher.models.contracts import WorkspaceSettings
from hannovators_deep_researcher.models.enums import (
    RequestedDomainMode,
    SourceOrigin,
    SourceStatus,
)
from hannovators_deep_researcher.persistence.repositories import (
    Repositories,
    create_session_factory,
)


@pytest.fixture
def database_url(tmp_path: Path) -> URL:
    url = URL.create("sqlite+aiosqlite", database=str(tmp_path / "repositories.sqlite"))
    config = Config(str(project_root() / "alembic.ini"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    return url


@pytest.fixture
async def repositories(database_url: URL) -> AsyncIterator[Repositories]:
    engine = create_database_engine(database_url)
    try:
        yield Repositories(create_session_factory(engine))
    finally:
        await engine.dispose()


@pytest.mark.integration
async def test_duplicate_external_id_in_one_workspace_is_rejected(
    repositories: Repositories,
) -> None:
    """UNIQUE(workspace_id, external_id) rejects a second insert, but not in another workspace."""

    first, second = [
        await repositories.create_workspace(
            research_question="Does drug A reduce mortality?",
            domain_mode=RequestedDomainMode.MEDICAL,
            settings=WorkspaceSettings(),
        )
        for _ in range(2)
    ]

    async def insert(workspace_id: str) -> None:
        await repositories.create_source(
            workspace_id,
            origin=SourceOrigin.PUBMED,
            external_id="12345678",
            title="Trial of drug A",
            status=SourceStatus.RAW,
        )

    await insert(first.id)
    with pytest.raises(IntegrityError):
        await insert(first.id)

    await insert(second.id)
    assert len(await repositories.list_sources(first.id)) == 1
