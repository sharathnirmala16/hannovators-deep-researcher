"""Async Alembic environment for the application database."""

import asyncio
from logging.config import fileConfig
from typing import cast

from alembic import context
from sqlalchemy import URL
from sqlalchemy.engine import Connection

from hannovators_deep_researcher.configuration.database import (
    get_database_url,
    normalize_database_url,
)
from hannovators_deep_researcher.infrastructure.database import create_database_engine
from hannovators_deep_researcher.persistence.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> URL:
    """Use a test-supplied URL when present, otherwise resolve application settings."""

    configured_url = config.attributes.get("database_url")
    if configured_url is not None:
        return normalize_database_url(cast(str | URL, configured_url))
    return get_database_url()


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Run migrations without opening a database connection."""

    context.configure(
        url=_database_url().render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations through an async SQLAlchemy connection."""

    connectable = create_database_engine(_database_url())
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(_configure)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against the configured application database."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
