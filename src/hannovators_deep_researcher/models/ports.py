"""Ports: the interfaces that services use and adapters (real or fake) implement."""

from collections.abc import Mapping, Sequence
from typing import Protocol

from pydantic import BaseModel

from hannovators_deep_researcher.models.decisions import DecisionAnswer, DecisionQuestion
from hannovators_deep_researcher.models.enums import ModelRole, StageId, TraceEventKind
from hannovators_deep_researcher.models.literature import CandidateRecord, SourceLinkRecord
from hannovators_deep_researcher.models.web import (
    FetchedDocument,
    WebSearchRequest,
    WebSearchResponse,
)


class ChatModel(Protocol):
    async def complete_json[T: BaseModel](
        self,
        *,
        role: ModelRole,
        system: str,
        user: str,
        schema: type[T],
        images: Sequence[bytes] = (),
    ) -> T: ...


class Embedder(Protocol):
    model: str
    dimensions: int

    async def embed(
        self, texts: Sequence[str], *, instruction: str | None = None
    ) -> list[list[float]]:
        """Embed texts as L2-normalized vectors of length `dimensions`.

        `instruction=None` embeds documents; a task instruction embeds queries.
        """
        ...


class DecisionModel(Protocol):
    async def evaluate(
        self, state: str, questions: Mapping[str, DecisionQuestion]
    ) -> dict[str, DecisionAnswer]: ...


class WebSearch(Protocol):
    """Implemented by `services/websearch_router.py`."""

    async def search(self, request: WebSearchRequest) -> WebSearchResponse: ...

    async def fetch(self, url: str, *, max_chars: int = 50_000) -> FetchedDocument: ...


class WebSearchProvider(Protocol):
    """Implemented by each `adapters/websearch/*.py`."""

    name: str
    supports_fetch: bool

    def is_configured(self) -> bool: ...

    async def search(self, request: WebSearchRequest) -> WebSearchResponse: ...

    async def fetch(self, url: str, *, max_chars: int) -> FetchedDocument: ...


class LiteratureSearch(Protocol):
    async def count(self, query: str) -> int: ...

    async def search(self, query: str, *, limit: int) -> list[CandidateRecord]: ...

    async def related(
        self, external_ids: Sequence[str], *, limit: int
    ) -> list[SourceLinkRecord]: ...

    async def open_access_pdf_url(self, record: CandidateRecord) -> str | None: ...


class EventSink(Protocol):
    async def emit(
        self,
        workspace_id: str,
        stage: StageId,
        kind: TraceEventKind,
        message: str,
        payload: Mapping[str, object] | None = None,
    ) -> None: ...
