"""Integration checks for database paths, connection settings, and migrations."""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, text
from sqlalchemy.exc import IntegrityError

from hannovators_deep_researcher.configuration import database as database_config
from hannovators_deep_researcher.configuration.database import (
    default_database_path,
    get_database_url,
    project_root,
)
from hannovators_deep_researcher.infrastructure.database import create_database_engine


@pytest.mark.integration
def test_default_and_relative_database_paths_are_project_rooted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The default and relative DATABASE_URL stay rooted when cwd changes."""

    repository = tmp_path / "repository"
    working_directory = tmp_path / "working-directory"
    repository.mkdir()
    working_directory.mkdir()
    monkeypatch.setattr(database_config, "project_root", lambda: repository)
    monkeypatch.chdir(working_directory)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    expected_path = repository / "data" / "hannovators.db"
    assert default_database_path() == expected_path
    assert get_database_url().database == str(expected_path)


@pytest.mark.integration
def test_dotenv_database_url_is_overridden_by_process_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Root .env supplies DATABASE_URL, with the process environment taking priority."""

    working_directory = tmp_path / "working-directory"
    working_directory.mkdir()
    monkeypatch.setattr(database_config, "project_root", lambda: tmp_path)
    monkeypatch.chdir(working_directory)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    (tmp_path / ".env").write_text(
        "DATABASE_URL=sqlite+aiosqlite:///data/from-dotenv.db\n", encoding="utf-8"
    )

    assert get_database_url().database == str(tmp_path / "data" / "from-dotenv.db")

    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///data/from-environment.db")
    assert get_database_url().database == str(tmp_path / "data" / "from-environment.db")


@pytest.mark.integration
async def test_sqlite_connections_enable_foreign_keys_timeout_and_wal(tmp_path: Path) -> None:
    """New SQLite connections have the required database safety settings."""

    database_path = tmp_path / "sqlite-pragmas.db"
    engine = create_database_engine(URL.create("sqlite+aiosqlite", database=str(database_path)))
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("PRAGMA foreign_keys")) == 1
            assert await connection.scalar(text("PRAGMA busy_timeout")) == 5_000
            assert await connection.scalar(text("PRAGMA journal_mode")) == "wal"
            await connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
            await connection.execute(
                text("CREATE TABLE child (parent_id INTEGER NOT NULL REFERENCES parent(id))")
            )
            with pytest.raises(IntegrityError):
                await connection.execute(text("INSERT INTO child(parent_id) VALUES (999)"))
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_empty_baseline_migration_upgrades_and_downgrades(tmp_path: Path) -> None:
    """The initial revision is reversible and creates no product tables."""

    database_path = tmp_path / "migration.sqlite"
    config = Config(str(project_root() / "alembic.ini"))
    config.attributes["database_url"] = URL.create("sqlite+aiosqlite", database=str(database_path))

    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        upgraded_tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    assert upgraded_tables == {"alembic_version"}

    command.downgrade(config, "base")
    with sqlite3.connect(database_path) as connection:
        downgraded_tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        remaining_versions = list(connection.execute("SELECT version_num FROM alembic_version"))
    assert downgraded_tables == {"alembic_version"}
    assert remaining_versions == []

    command.upgrade(config, "head")
    with sqlite3.connect(database_path) as connection:
        reupgraded_versions = list(connection.execute("SELECT version_num FROM alembic_version"))
    assert reupgraded_versions == [("0001_empty_baseline",)]
