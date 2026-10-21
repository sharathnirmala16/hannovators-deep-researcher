"""Tavily deep research record (`data/workspaces/<ws>/deep_research.json`)."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel

DeepResearchStatus = Literal["pending", "running", "completed", "failed"]


class DeepResearchSource(ContractModel):
    title: str
    url: str
    source_id: str | None = None


class DeepResearchRecord(ContractModel):
    """`GET /api/workspaces/{id}/deep-research`."""

    status: DeepResearchStatus
    content: str = ""
    sources: list[DeepResearchSource] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    report_source_id: str | None = None
    """The workspace source that holds this report (`snapshot.md`), once it exists."""
