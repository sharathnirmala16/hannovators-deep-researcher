"""Async SQLAlchemy engine setup and SQLite connection defaults."""

from pathlib import Path
from typing import Any

from sqlalchemy import URL, event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from hannovators_deep_researcher.configuration.database import (
    get_database_url,
    normalize_database_url,
)

SQLITE_BUSY_TIMEOUT_MS = 5_000


def _sqlite_connection_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    """Enable foreign keys, a bounded wait, and WAL on each SQLite connection."""

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cursor.execute("PRAGMA journal_mode=WAL")
    finally:
        cursor.close()


def create_database_engine(database_url: str | URL | None = None) -> AsyncEngine:
    """Create an async engine and apply SQLite connection settings when relevant."""

    url = normalize_database_url(database_url) if database_url is not None else get_database_url()
    if url.get_backend_name() == "sqlite":
        database = url.database
        if database and database != ":memory:" and not database.startswith("file:"):
            Path(database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(url)
    if url.get_backend_name() == "sqlite":
        event.listen(engine.sync_engine, "connect", _sqlite_connection_pragmas)
    return engine
