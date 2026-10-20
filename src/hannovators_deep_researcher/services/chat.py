"""Grounded chat: answers built only from retrieved passages, with `[n]` citations to PDF spans.

One question records a `user.chat.ask` USER_ACTION step, then one CHAT step (actor AGENT) that
parents the RETRIEVE step and the LLM call. Every citation quote is checked against its passage
(verbatim, else the closest verbatim sentence of the passage); a cited passage whose quote does
not verify is quoted with its sentence that best matches the citing answer sentences, so a
citation always shows real passage text. Markers that name no retrieved passage are dropped.

PDF citations carry the page and line rectangles of the quote (`page.search_for` on the
passage page, then the whole PDF), else the passage bbox, else the closest PDF chunk's bbox.
"""

import asyncio
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import Field

from hannovators_deep_researcher.models.base import ContractModel
from hannovators_deep_researcher.models.chat import ChatMessageView, Citation
from hannovators_deep_researcher.models.contracts import Rect
from hannovators_deep_researcher.models.enums import (
    ChatRole,
    ModelRole,
    SourceStatus,
    TrajectoryActor,
    TrajectoryKind,
    TrajectoryStatus,
)
from hannovators_deep_researcher.persistence.queries.chat import recent_chat_messages
from hannovators_deep_researcher.persistence.tables import ChatMessageRow, ChunkRow, SourceRow
from hannovators_deep_researcher.services.documents.files import resolve_data_path
from hannovators_deep_researcher.services.pipeline.context import PipelineServices
from hannovators_deep_researcher.services.retrieval.hybrid import (
    RetrievedChunk,
    hierarchical_retrieve,
)
from hannovators_deep_researcher.services.retrieval.lexical import bm25_scores
from hannovators_deep_researcher.services.retrieval.quotes import locate_quote, verified_quote
from hannovators_deep_researcher.services.trajectory import bind
from hannovators_deep_researcher.services.workspace_state import file_url

CHAT_SOURCE_STATUSES = (
    SourceStatus.SEED,
    SourceStatus.SCREEN_PROMOTED,
    SourceStatus.APPRAISE_PROMOTED,
    SourceStatus.APPRAISE_DISCOUNTED,
)
PASSAGES = 8
PASSAGE_CHARS = 1_800
HISTORY_MESSAGES = 6
MAX_CLAIMS = 30
NO_COVERAGE = (
    "The evidence base of this workspace does not cover this question: none of the seed or "
    "promoted sources has a passage that answers it."
)

SYSTEM = (
    "You answer questions about a research workspace using ONLY the numbered passages given. "
    "End every factual sentence with one or more markers such as [2] or [1][3] that name the "
    "passages supporting it. For each passage you cite, add one citation with its passage "
    "number and a quote copied character for character from that passage (one or two "
    "sentences, at most 300 characters) that supports the sentence. Background notes "
    "(appraised claims, synthesis) are context only: never cite them and never state facts "
    "that no passage supports. If the passages answer only part of the question, answer that "
    "part with markers and say in plain words which part the evidence base does not cover. "
    "Set the covered field to false only when no passage answers any part, and then give no "
    "markers. Never mention the JSON fields in the answer text. Write concise markdown. Reply "
    "with JSON only."
)

MIN_QUOTE_CHARS = 30
MAX_QUOTE_CHARS = 300
_MARKERS = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
_SENTENCES = re.compile(r"(?<=[.!?])\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([.,;:!?])")


class ChatCitationDraft(ContractModel):
    passage: int = Field(ge=1)
    quote: str


class ChatAnswerDraft(ContractModel):
    """LLM reply: a markdown answer with `[n]` passage markers and one quote per cited passage."""

    answer: str
    covered: bool
    citations: list[ChatCitationDraft] = Field(default_factory=list)

    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {
            "answer": "The retrieved passages describe the intervention and its outcomes [1].",
            "covered": True,
            "citations": [{"passage": 1, "quote": "fake quote that is not in any passage"}],
        }


@dataclass(frozen=True, slots=True)
class _Passage:
    number: int
    chunk: RetrievedChunk
    source: SourceRow


def _is_pdf(source: SourceRow) -> bool:
    return bool(source.raw_path and source.raw_path.lower().endswith(".pdf"))


def _closest_pdf_chunk(chunks: Sequence[ChunkRow], quote: str) -> ChunkRow | None:
    """The source chunk with a page and bbox whose text best matches the quote (BM25)."""

    placed = [chunk for chunk in chunks if chunk.page and chunk.bbox_json]
    if not placed:
        return None
    scores = bm25_scores(quote, [chunk.text for chunk in placed])
    best = max(range(len(placed)), key=lambda index: scores[index])
    return placed[best] if scores[best] > 0 else None


def _chunk_bbox(chunk: ChunkRow) -> Rect | None:
    values = json.loads(chunk.bbox_json) if chunk.bbox_json else None
    if not isinstance(values, list) or len(values) != 4:
        return None
    return (float(values[0]), float(values[1]), float(values[2]), float(values[3]))


async def _pdf_location(
    services: PipelineServices, passage: _Passage, quote: str
) -> tuple[int | None, list[Rect]]:
    """Page and rects of the quote in the source PDF: `search_for` on the passage's page first,
    then the whole PDF, then the passage bbox, then the bbox of the closest PDF chunk."""

    chunk, source = passage.chunk, passage.source
    match = await asyncio.to_thread(
        locate_quote,
        resolve_data_path(source.raw_path or ""),
        quote,
        preferred_pages=[chunk.page] if chunk.page else [],
    )
    if match is not None and match.rects:
        return match.page, list(match.rects)
    if chunk.page and chunk.bbox:
        return chunk.page, [chunk.bbox]
    chunks = await services.repositories.list_chunks(source.workspace_id, source.id)
    closest = _closest_pdf_chunk(chunks, quote)
    box = _chunk_bbox(closest) if closest else None
    if closest is None or box is None:
        return chunk.page, []
    return closest.page, [box]


async def _citation(services: PipelineServices, n: int, passage: _Passage, quote: str) -> Citation:
    chunk, source = passage.chunk, passage.source
    page, rects = chunk.page, [chunk.bbox] if chunk.bbox else []
    if _is_pdf(source):
        page, rects = await _pdf_location(services, passage, quote)
    return Citation(
        n=n,
        source_id=source.id,
        source_title=source.title,
        chunk_id=chunk.chunk_id,
        page=page,
        rects=[_rect(rect) for rect in rects],
        quote=quote,
        pdf_url=file_url(source.raw_path) if _is_pdf(source) else None,
        url=source.url,
    )


def _rect(rect: Rect) -> Rect:
    return (float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3]))


def _renumber(answer: str, kept: dict[int, int]) -> str:
    """Rewrite passage markers to citation numbers; drop markers without a kept citation."""

    def replace(match: re.Match[str]) -> str:
        numbers = [int(part) for part in match.group(1).split(",")]
        mapped = list(dict.fromkeys(kept[number] for number in numbers if number in kept))
        return "".join(f"[{number}]" for number in mapped)

    rewritten = _MARKERS.sub(replace, answer)
    return _SPACE_BEFORE_PUNCT.sub(r"\1", rewritten).strip()


def _citing_sentences(answer: str, number: int) -> str:
    """The answer sentences that carry the marker `[number]`."""

    picked = [
        sentence
        for sentence in _SENTENCES.split(answer)
        for match in _MARKERS.finditer(sentence)
        if number in (int(part) for part in match.group(1).split(","))
    ]
    return " ".join(dict.fromkeys(picked))


def supporting_sentence(passage: str, claim: str) -> str:
    """The passage sentence with the best BM25 match to `claim` (the first one on no match)."""

    sentences = [" ".join(part.split()) for part in _SENTENCES.split(passage) if part.strip()]
    sentences = [sentence for sentence in sentences if len(sentence) >= MIN_QUOTE_CHARS]
    if not sentences:
        return " ".join(passage.split())[:MAX_QUOTE_CHARS]
    scores = bm25_scores(_MARKERS.sub(" ", claim), sentences)
    best = max(range(len(sentences)), key=lambda index: scores[index])
    return sentences[best][:MAX_QUOTE_CHARS]


def _order_of_markers(answer: str) -> list[int]:
    found = [int(part) for match in _MARKERS.finditer(answer) for part in match.group(1).split(",")]
    return list(dict.fromkeys(found))


def to_view(row: ChatMessageRow) -> ChatMessageView:
    citations = [Citation.model_validate(item) for item in json.loads(row.citations_json or "[]")]
    return ChatMessageView(
        id=row.id,
        workspace_id=row.workspace_id,
        role=ChatRole(row.role),
        content=row.content,
        citations=citations,
        trajectory_step_id=row.trajectory_step_id,
        created_at=row.created_at,
    )


class ChatService:
    """Grounded question answering over one workspace's seed and promoted sources."""

    def __init__(self, services: PipelineServices) -> None:
        self._services = services
        self._repositories = services.repositories

    async def list_messages(self, workspace_id: str) -> list[ChatMessageView]:
        return [to_view(row) for row in await self._repositories.list_chat_messages(workspace_id)]

    async def ask(self, workspace_id: str, question: str) -> ChatMessageView:
        history = await recent_chat_messages(
            self._repositories, workspace_id, limit=HISTORY_MESSAGES
        )
        trajectory = self._services.trajectory
        ask_step = await trajectory.record(
            kind=TrajectoryKind.USER_ACTION,
            name="user.chat.ask",
            actor=TrajectoryActor.USER,
            workspace_id=workspace_id,
            summary=question[:200],
            request={"question": question},
        )
        await self._repositories.add_chat_message(
            workspace_id=workspace_id,
            role=ChatRole.USER,
            content=question,
            citations_json="[]",
            trajectory_step_id=ask_step,
        )
        with bind(workspace_id):
            async with trajectory.step(
                kind=TrajectoryKind.CHAT,
                name="chat.answer",
                workspace_id=workspace_id,
                summary=f"Answer: {question[:160]}",
                request={"question": question, "ask_step_id": ask_step},
            ) as step:
                content, citations, details = await self._answer(workspace_id, question, history)
                step.response = {"answer": content, **details}
                step.source_ids = list(dict.fromkeys(c.source_id for c in citations))
                step.summary = f"{len(citations)} citation(s) for: {question[:140]}"
                if details.get("error"):
                    step.status = TrajectoryStatus.ERROR
        row = await self._repositories.add_chat_message(
            workspace_id=workspace_id,
            role=ChatRole.ASSISTANT,
            content=content,
            citations_json=json.dumps([citation.model_dump(mode="json") for citation in citations]),
            trajectory_step_id=step.id,
        )
        return to_view(row)

    async def _answer(
        self, workspace_id: str, question: str, history: Sequence[ChatMessageRow]
    ) -> tuple[str, list[Citation], dict[str, object]]:
        sources = {
            source.id: source
            for source in await self._repositories.list_sources(workspace_id, CHAT_SOURCE_STATUSES)
        }
        if not sources:
            return NO_COVERAGE, [], {"covered": False, "reason": "no sources"}
        retrieval = await hierarchical_retrieve(
            self._services, question, workspace_id, source_ids=list(sources), k=PASSAGES
        )
        relevant = [chunk for chunk in retrieval.chunks if chunk.relevant]
        details: dict[str, object] = {
            "retrieve_step_id": retrieval.step_id,
            "used_query": retrieval.used_query,
            "passages": [chunk.chunk_id for chunk in relevant],
        }
        if not relevant:
            return NO_COVERAGE, [], {**details, "covered": False, "reason": "no relevant passage"}
        passages = [
            _Passage(number, chunk, sources[chunk.source_id])
            for number, chunk in enumerate(relevant, start=1)
        ]
        prompt = await self._prompt(workspace_id, question, passages, history)
        try:
            draft = await self._services.chat.complete_json(
                role=ModelRole.SYNTHESIZE, system=SYSTEM, user=prompt, schema=ChatAnswerDraft
            )
        except Exception as error:
            message = f"{type(error).__name__}: {error}"[:300]
            text = f"I could not generate an answer: the language model failed ({message})."
            return text, [], {**details, "error": message}
        if not draft.covered and not _order_of_markers(draft.answer):
            return draft.answer.strip() or NO_COVERAGE, [], {**details, "covered": False}
        citations, kept, dropped = await self._citations(draft, passages)
        content = _renumber(draft.answer, kept)
        return content, citations, {**details, "covered": draft.covered, "dropped": dropped}

    async def _citations(
        self, draft: ChatAnswerDraft, passages: Sequence[_Passage]
    ) -> tuple[list[Citation], dict[int, int], list[dict[str, object]]]:
        by_number = {passage.number: passage for passage in passages}
        quotes: dict[int, str] = {}
        dropped: list[dict[str, object]] = []
        for item in draft.citations:
            passage = by_number.get(item.passage)
            if passage is None or item.passage in quotes:
                continue
            quote = verified_quote(item.quote, passage.chunk.text)
            if quote is None:
                dropped.append({"passage": item.passage, "quote": item.quote[:300]})
                continue
            quotes[item.passage] = quote
        for number in _order_of_markers(draft.answer):
            if number in by_number and number not in quotes:
                # The answer cites the passage but its quote did not verify: cite the passage
                # sentence that best supports the citing sentences instead (real text only).
                quotes[number] = supporting_sentence(
                    by_number[number].chunk.text, _citing_sentences(draft.answer, number)
                )
        kept: dict[int, int] = {}
        citations: list[Citation] = []
        for number in _order_of_markers(draft.answer):
            if quotes.get(number) and number not in kept:
                kept[number] = len(kept) + 1
                citations.append(
                    await _citation(self._services, kept[number], by_number[number], quotes[number])
                )
        return citations, kept, dropped

    async def _prompt(
        self,
        workspace_id: str,
        question: str,
        passages: Sequence[_Passage],
        history: Sequence[ChatMessageRow],
    ) -> str:
        blocks = []
        for passage in passages:
            source, chunk = passage.source, passage.chunk
            where = f"p.{chunk.page}" if chunk.page else chunk.tier.lower()
            text = " ".join(chunk.text.split())[:PASSAGE_CHARS]
            blocks.append(
                f"[{passage.number}] {source.title} ({source.year or 'n.d.'}, {where})\n{text}"
            )
        parts = [f"Question: {question}", "Passages:\n\n" + "\n\n".join(blocks)]
        background = await self._background(workspace_id)
        if background:
            parts.append("Background notes (context only, not citable):\n" + background)
        if history:
            turns = "\n".join(f"{row.role}: {row.content[:600]}" for row in history)
            parts.append(f"Earlier conversation:\n{turns}")
        return "\n\n".join(parts)

    async def _background(self, workspace_id: str) -> str:
        lines = [
            f"- {claim.kind} {claim.label}: {claim.text} [{claim.verdict}]"
            for claim in (await self._repositories.list_claims(workspace_id))[:MAX_CLAIMS]
        ]
        workspace = await self._repositories.get_workspace(workspace_id)
        if workspace is not None and workspace.synthesis_json:
            synthesis = json.loads(workspace.synthesis_json)
            lines.append(f"- Synthesis: {str(synthesis.get('analysis', ''))[:1500]}")
            recommendation = synthesis.get("recommendation") or {}
            if isinstance(recommendation, dict) and recommendation.get("text"):
                lines.append(f"- Recommendation: {recommendation['text']}")
        return "\n".join(lines)
