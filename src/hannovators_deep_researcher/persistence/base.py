"""SQLAlchemy metadata base for application persistence models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for persistence tables added in future application work."""
