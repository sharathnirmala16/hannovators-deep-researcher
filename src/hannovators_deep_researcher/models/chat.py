"""Chat contracts: grounded answers whose numbered citations open the highlighted PDF span."""

from datetime import datetime

from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel, NonEmptyText
from hannovators_deep_researcher.models.contracts import Rect
from hannovators_deep_researcher.models.enums import ChatRole


class Citation(ContractModel):
    """Citation `[n]` in an answer. `rects` are PDF points on the 1-based `page`.

    `pdf_url` points at the source PDF (`/files/...`); the viewer draws `rects` itself. Web
    sources have no page or rects and carry the quote for the snapshot view.
    """

    n: int = Field(ge=1)
    source_id: str
    source_title: str
    chunk_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    rects: list[Rect] = Field(default_factory=list)
    quote: str
    pdf_url: str | None = None
    url: str | None = None


class ChatMessageView(ContractModel):
    id: str
    workspace_id: str
    role: ChatRole
    content: str
    """Markdown. Assistant answers mark citations as `[n]` that match `citations[].n`."""
    citations: list[Citation] = Field(default_factory=list)
    trajectory_step_id: int | None = None
    created_at: datetime


class ChatRequest(ContractModel):
    """`POST /api/workspaces/{id}/chat`."""

    question: NonEmptyText
