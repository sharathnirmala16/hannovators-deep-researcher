"""Recording port wrappers: every port call becomes one trajectory step (PLAN.md section 5.3).

`main.build_container` wraps the real or fake ports, so stages, chat, and deep research record
LLM, DECISION, SEARCH, FETCH, and EMBED steps without extra code. Each wrapper delegates to the
wrapped port inside `TrajectoryRecorder.step()`, so a failure closes the step as ERROR (and
re-raises) and nested calls get the step as their parent. Nothing is recorded without a bound
workspace (see `services/trajectory.bind`). Bodies never hold secrets or embedding vectors.

`record_download` wraps `services/documents/files.download` for stages that fetch files with
plain httpx, and `record_user_action` records a USER_ACTION step from a router.
"""

from collections.abc import Callable, Collection, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel

from hannovators_deep_researcher.models.decisions import DecisionAnswer, DecisionQuestion
from hannovators_deep_researcher.models.enums import (
    ModelRole,
    StageId,
    TrajectoryActor,
    TrajectoryKind,
    VerdictOutcome,
)
from hannovators_deep_researcher.models.literature import CandidateRecord, SourceLinkRecord
from hannovators_deep_researcher.models.ports import (
    ChatModel,
    DecisionModel,
    Embedder,
    LiteratureSearch,
    WebSearch,
)
from hannovators_deep_researcher.models.web import (
    FetchedDocument,
    ProviderFailure,
    WebSearchRequest,
    WebSearchResponse,
)
from hannovators_deep_researcher.services.documents.files import (
    DEFAULT_MAX_DOWNLOAD_BYTES,
    PDF_CONTENT_TYPES,
    DownloadResult,
    download,
)
from hannovators_deep_researcher.services.trajectory import StepHandle, TrajectoryRecorder

PREVIEW_CHARS = 500
"""Characters of fetched content kept in a FETCH step response."""

MAX_LISTED_ITEMS = 50
"""Most result rows (titles + URLs, records, links) kept in a step response."""

SUMMARY_ANSWERS = 3
"""Answers spelled out in a DECISION step summary."""


def model_label(model: str) -> str:
    """Short step-name prefix for a model ID: `nemotron` for Nemotron, else the last segment."""

    if "nemotron" in model.lower():
        return "nemotron"
    return model.rsplit("/", 1)[-1] or model


def _shorten(text: str, limit: int = 80) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else f"{flat[: limit - 3]}..."


def _failure_response(handle: StepHandle, error: ProviderFailure) -> None:
    """Keep the mapped provider error (and router attempts, when present) on the step."""

    handle.response = {"error": error.error.model_dump(mode="json")}
    attempts = getattr(error, "attempts", None)
    if isinstance(attempts, list):
        handle.response["attempts"] = [
            item.model_dump(mode="json") if isinstance(item, BaseModel) else item
            for item in attempts
        ]


# --- LLM ---------------------------------------------------------------------------------


class RecordingChatModel:
    """`ChatModel` that records one LLM step per `complete_json` call."""

    def __init__(
        self,
        inner: ChatModel,
        trajectory: TrajectoryRecorder,
        *,
        model_for: Callable[[ModelRole], str],
    ) -> None:
        self._inner = inner
        self._trajectory = trajectory
        self._model_for = model_for

    async def complete_json[T: BaseModel](
        self,
        *,
        role: ModelRole,
        system: str,
        user: str,
        schema: type[T],
        images: Sequence[bytes] = (),
    ) -> T:
        model = self._model_for(role)
        request: dict[str, object] = {
            "role": role,
            "model": model,
            "schema": schema.__name__,
            "system": system,
            "user": user,
            "image_count": len(images),
        }
        images_note = f", {len(images)} image(s)" if images else ""
        async with self._trajectory.step(
            kind=TrajectoryKind.LLM,
            name=f"{model_label(model)}.{role}",
            target=model,
            summary=f"{schema.__name__} ({role}{images_note})",
            request=request,
        ) as handle:
            try:
                reply = await self._inner.complete_json(
                    role=role, system=system, user=user, schema=schema, images=images
                )
            except ProviderFailure as error:
                _failure_response(handle, error)
                raise
            handle.response = reply.model_dump(mode="json")
        return reply


# --- Jev decisions -----------------------------------------------------------------------


def _answer_value(answer: DecisionAnswer) -> str:
    if answer.choice is not None:
        return answer.choice
    for value in (answer.score, answer.noul):
        if value is not None:
            return f"{value:g}" if float(value).is_integer() else f"{value:.2f}"
    return "?"


def decision_summary(answers: Mapping[str, DecisionAnswer]) -> str:
    """`3 questions, relevance=3 (0.82), design=RCT (0.91)` style summary."""

    count = len(answers)
    parts = [f"{count} question{'s' if count != 1 else ''}"]
    for key, answer in list(answers.items())[:SUMMARY_ANSWERS]:
        confidence = f" ({answer.confidence:.2f})" if answer.confidence is not None else ""
        parts.append(f"{key}={_answer_value(answer)}{confidence}")
    if count > SUMMARY_ANSWERS:
        parts.append("...")
    return ", ".join(parts)


def _mean_confidence(answers: Mapping[str, DecisionAnswer]) -> float | None:
    values = [a.confidence for a in answers.values() if a.confidence is not None]
    return sum(values) / len(values) if values else None


class RecordingDecisionModel:
    """`DecisionModel` that records one DECISION step per Jev `evaluate` call."""

    def __init__(
        self, inner: DecisionModel, trajectory: TrajectoryRecorder, *, model: str, name: str
    ) -> None:
        self._inner = inner
        self._trajectory = trajectory
        self._model = model
        self._name = name

    async def evaluate(
        self, state: str, questions: Mapping[str, DecisionQuestion]
    ) -> dict[str, DecisionAnswer]:
        request: dict[str, object] = {
            "model": self._model,
            "state": state,
            "questions": {key: q.model_dump(mode="json") for key, q in questions.items()},
        }
        async with self._trajectory.step(
            kind=TrajectoryKind.DECISION,
            name=self._name,
            target=self._model,
            summary=f"{len(questions)} question(s)",
            request=request,
        ) as handle:
            try:
                answers = await self._inner.evaluate(state, questions)
            except ProviderFailure as error:
                _failure_response(handle, error)
                raise
            handle.response = {
                "answers": {key: a.model_dump(mode="json") for key, a in answers.items()}
            }
            handle.summary = decision_summary(answers)
            handle.confidence = _mean_confidence(answers)
        return answers


# --- Web search --------------------------------------------------------------------------


def _search_response(response: WebSearchResponse) -> dict[str, object]:
    return {
        "provider": response.provider,
        "result_count": len(response.results),
        "results": [
            {
                "title": result.title,
                "url": result.url,
                "provider": result.provider,
                "score": result.score,
                "published_at": result.published_at,
            }
            for result in response.results[:MAX_LISTED_ITEMS]
        ],
        "attempts": [attempt.model_dump(mode="json") for attempt in response.attempts],
    }


def _fetch_response(document: FetchedDocument) -> dict[str, object]:
    return {
        "url": document.url,
        "title": document.title,
        "content_type": document.content_type,
        "provider": document.provider,
        "content_length": len(document.content),
        "preview": document.content[:PREVIEW_CHARS],
    }


class RecordingWebSearch:
    """`WebSearch` that records a SEARCH step per search and a FETCH step per fetch."""

    def __init__(self, inner: WebSearch, trajectory: TrajectoryRecorder, *, provider: str) -> None:
        self._inner = inner
        self._trajectory = trajectory
        self._provider = provider

    async def search(self, request: WebSearchRequest) -> WebSearchResponse:
        async with self._trajectory.step(
            kind=TrajectoryKind.SEARCH,
            name=f"{self._provider}.search",
            target=self._provider,
            summary=f"'{_shorten(request.query)}'",
            request={"providers": self._provider, **request.model_dump(mode="json")},
        ) as handle:
            try:
                response = await self._inner.search(request)
            except ProviderFailure as error:
                _failure_response(handle, error)
                raise
            handle.response = _search_response(response)
            handle.summary = (
                f"{len(response.results)} results for '{_shorten(request.query)}' "
                f"via {response.provider}"
            )
        return response

    async def fetch(self, url: str, *, max_chars: int = 50_000) -> FetchedDocument:
        async with self._trajectory.step(
            kind=TrajectoryKind.FETCH,
            name=f"{self._provider}.fetch",
            target=url,
            summary=f"fetch {_shorten(url)}",
            request={"url": url, "max_chars": max_chars, "providers": self._provider},
        ) as handle:
            try:
                document = await self._inner.fetch(url, max_chars=max_chars)
            except ProviderFailure as error:
                _failure_response(handle, error)
                raise
            handle.response = _fetch_response(document)
            handle.summary = f"{len(document.content)} chars: {_shorten(document.title or url)}"
        return document


# --- Literature search -------------------------------------------------------------------


def _record_row(record: CandidateRecord) -> dict[str, object]:
    return {
        "external_id": record.external_id,
        "title": record.title,
        "origin": record.origin,
        "year": record.year,
        "pdf_url": record.pdf_url,
        "publication_types": record.publication_types,
    }


class RecordingLiteratureSearch:
    """`LiteratureSearch` that records SEARCH steps for count/search and FETCH steps for
    related and open-access lookups."""

    def __init__(
        self,
        inner: LiteratureSearch,
        trajectory: TrajectoryRecorder,
        *,
        provider: str,
        target: str | None = None,
    ) -> None:
        self._inner = inner
        self._trajectory = trajectory
        self._provider = provider
        self._target = target or provider

    async def count(self, query: str) -> int:
        async with self._trajectory.step(
            kind=TrajectoryKind.SEARCH,
            name=f"{self._provider}.count",
            target=self._target,
            summary=f"count '{_shorten(query)}'",
            request={"provider": self._provider, "query": query},
        ) as handle:
            try:
                hits = await self._inner.count(query)
            except ProviderFailure as error:
                _failure_response(handle, error)
                raise
            handle.response = {"hit_count": hits}
            handle.summary = f"{hits} hits for '{_shorten(query)}'"
        return hits

    async def search(self, query: str, *, limit: int) -> list[CandidateRecord]:
        async with self._trajectory.step(
            kind=TrajectoryKind.SEARCH,
            name=f"{self._provider}.search",
            target=self._target,
            summary=f"'{_shorten(query)}'",
            request={"provider": self._provider, "query": query, "limit": limit},
        ) as handle:
            try:
                records = await self._inner.search(query, limit=limit)
            except ProviderFailure as error:
                _failure_response(handle, error)
                raise
            handle.response = {
                "result_count": len(records),
                "records": [_record_row(record) for record in records[:MAX_LISTED_ITEMS]],
            }
            handle.summary = f"{len(records)} records for '{_shorten(query)}'"
        return records

    async def related(self, external_ids: Sequence[str], *, limit: int) -> list[SourceLinkRecord]:
        async with self._trajectory.step(
            kind=TrajectoryKind.FETCH,
            name=f"{self._provider}.related",
            target=self._target,
            summary=f"related to {len(external_ids)} id(s)",
            request={
                "provider": self._provider,
                "external_ids": list(external_ids),
                "limit": limit,
            },
        ) as handle:
            try:
                links = await self._inner.related(external_ids, limit=limit)
            except ProviderFailure as error:
                _failure_response(handle, error)
                raise
            handle.response = {
                "link_count": len(links),
                "links": [link.model_dump(mode="json") for link in links[:MAX_LISTED_ITEMS]],
            }
            handle.summary = f"{len(links)} links from {len(external_ids)} id(s)"
        return links

    async def open_access_pdf_url(self, record: CandidateRecord) -> str | None:
        async with self._trajectory.step(
            kind=TrajectoryKind.FETCH,
            name=f"{self._provider}.open_access_pdf_url",
            target=self._target,
            summary=f"OA PDF for {record.external_id}",
            request={
                "provider": self._provider,
                "external_id": record.external_id,
                "pmid": record.pmid,
                "pmcid": record.pmcid,
                "doi": record.doi,
                "title": record.title,
            },
        ) as handle:
            try:
                url = await self._inner.open_access_pdf_url(record)
            except ProviderFailure as error:
                _failure_response(handle, error)
                raise
            handle.response = {"pdf_url": url}
            handle.summary = (
                f"OA PDF found for {record.external_id}"
                if url
                else f"no OA PDF for {record.external_id}"
            )
        return url


# --- Embeddings --------------------------------------------------------------------------


class RecordingEmbedder:
    """`Embedder` that records one EMBED step per call (counts and sizes, never vectors)."""

    def __init__(self, inner: Embedder, trajectory: TrajectoryRecorder, *, provider: str) -> None:
        self._inner = inner
        self._trajectory = trajectory
        self._provider = provider
        self.model = inner.model
        self.dimensions = inner.dimensions

    async def embed(
        self, texts: Sequence[str], *, instruction: str | None = None
    ) -> list[list[float]]:
        purpose = "query" if instruction else "documents"
        async with self._trajectory.step(
            kind=TrajectoryKind.EMBED,
            name=f"{self._provider}.embed",
            target=self.model,
            summary=f"{len(texts)} {purpose} text(s)",
            request={
                "model": self.model,
                "dimensions": self.dimensions,
                "count": len(texts),
                "total_chars": sum(len(text) for text in texts),
                "instruction": instruction,
            },
        ) as handle:
            try:
                vectors = await self._inner.embed(texts, instruction=instruction)
            except ProviderFailure as error:
                _failure_response(handle, error)
                raise
            handle.response = {
                "count": len(vectors),
                "dimensions": len(vectors[0]) if vectors else self.dimensions,
            }
            handle.summary = f"{len(vectors)} {purpose} vector(s) x {self.dimensions}"
        return vectors


# --- Downloads and user actions ----------------------------------------------------------


async def record_download(
    trajectory: TrajectoryRecorder,
    client: httpx.AsyncClient,
    url: str,
    relative_path: str,
    *,
    source_ids: Sequence[str] = (),
    allowed_content_types: Collection[str] = PDF_CONTENT_TYPES,
    max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    root: Path | None = None,
    name: str = "http.download",
) -> DownloadResult:
    """`files.download` inside a DOWNLOAD step (URL, content type, bytes; ERROR on failure).

    Use it from stages that download with plain httpx, e.g. open-access PDFs in `acquire`.
    """

    async with trajectory.step(
        kind=TrajectoryKind.DOWNLOAD,
        name=name,
        target=url,
        summary=f"GET {_shorten(url)}",
        request={
            "url": url,
            "relative_path": relative_path,
            "allowed_content_types": sorted(allowed_content_types),
            "max_bytes": max_bytes,
        },
        source_ids=source_ids,
    ) as handle:
        result = await download(
            client,
            url,
            relative_path,
            allowed_content_types=allowed_content_types,
            max_bytes=max_bytes,
            root=root,
        )
        handle.response = {
            "relative_path": result.relative_path,
            "content_type": result.content_type,
            "size_bytes": result.size_bytes,
        }
        handle.summary = f"{result.size_bytes} bytes ({result.content_type})"
    return result


async def record_user_action(
    trajectory: TrajectoryRecorder,
    workspace_id: str,
    name: str,
    *,
    summary: str = "",
    target: str | None = None,
    request: Mapping[str, object] | None = None,
    source_ids: Sequence[str] = (),
    stage: StageId | None = None,
    outcome: VerdictOutcome | None = None,
) -> int | None:
    """Record a finished USER_ACTION step (actor USER) and return its ID."""

    return await trajectory.record(
        kind=TrajectoryKind.USER_ACTION,
        name=name,
        actor=TrajectoryActor.USER,
        workspace_id=workspace_id,
        stage=stage,
        target=target,
        summary=summary,
        request=request,
        source_ids=source_ids,
        outcome=outcome,
    )


if TYPE_CHECKING:

    def _conforms(
        chat: RecordingChatModel,
        decisions: RecordingDecisionModel,
        web: RecordingWebSearch,
        literature: RecordingLiteratureSearch,
        embedder: RecordingEmbedder,
    ) -> tuple[ChatModel, DecisionModel, WebSearch, LiteratureSearch, Embedder]:
        return chat, decisions, web, literature, embedder
