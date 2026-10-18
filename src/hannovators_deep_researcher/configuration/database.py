"""Database URL and project data path configuration."""

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import URL, make_url

DATABASE_ENVIRONMENT_VARIABLE = "DATABASE_URL"
DEFAULT_DATABASE_RELATIVE_PATH = Path("data") / "hannovators.db"


def project_root() -> Path:
    """Return the repository root, independent of the process working directory."""

    return Path(__file__).resolve().parents[3]


def default_database_path() -> Path:
    """Return the default SQLite database path under the repository's data directory."""

    return project_root() / DEFAULT_DATABASE_RELATIVE_PATH


def normalize_database_url(database_url: str | URL) -> URL:
    """Resolve relative SQLite filenames against the repository root."""

    url = make_url(database_url) if isinstance(database_url, str) else database_url
    if url.get_backend_name() != "sqlite":
        return url

    database = url.database
    if database is None or database == ":memory:" or database.startswith("file:"):
        return url

    path = Path(database)
    if not path.is_absolute():
        url = url.set(database=str(project_root() / path))
    return url


def get_database_url() -> URL:
    """Read DATABASE_URL from the environment or root .env, then use the default."""

    environment_value = os.environ.get(DATABASE_ENVIRONMENT_VARIABLE)
    dotenv_value = dotenv_values(project_root() / ".env").get(DATABASE_ENVIRONMENT_VARIABLE)
    configured_value = environment_value if environment_value is not None else dotenv_value
    if configured_value is None:
        return normalize_database_url(
            URL.create("sqlite+aiosqlite", database=str(default_database_path()))
        )
    if not configured_value.strip():
        raise ValueError(f"{DATABASE_ENVIRONMENT_VARIABLE} must not be empty")
    return normalize_database_url(configured_value)
