"""Turn chunker output into stored chunk rows with document embeddings (no instruction)."""

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from hannovators_deep_researcher.models.contracts import Rect
from hannovators_deep_researcher.models.enums import ChunkTier
from hannovators_deep_researcher.persistence.queries.ingest import replace_chunks
from hannovators_deep_researcher.persistence.tables import ChunkRow
from hannovators_deep_researcher.services.documents.markdown_chunker import MarkdownChunk
from hannovators_deep_researcher.services.documents.pdf_chunker import PdfChunkResult
from hannovators_deep_researcher.services.pipeline.context import PipelineServices
from hannovators_deep_researcher.services.retrieval.vectors import pack_vector

logger = logging.getLogger(__name__)

EMBED_MAX_CHARS = 6_000
EMBED_BATCH = 64
MIN_PDF_CHUNK_CHARS = 40
"""Shorter PDF blocks (figure labels, page numbers, running heads) are not indexed."""


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    tier: ChunkTier
    text: str
    page: int | None = None
    bbox: Rect | None = None


@dataclass(frozen=True, slots=True)
class IndexResult:
    chunks: int
    embedded: int
    abstract_chunks: int
    error: str | None = None


_LIGATURES = str.maketrans(
    {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl", "\u00ad": ""}
)


def pdf_drafts(result: PdfChunkResult) -> list[ChunkDraft]:
    """PDF chunks with ligatures expanded, so BM25, embeddings, and quotes see plain letters."""

    return [
        ChunkDraft(
            tier=chunk.tier, text=chunk.text.translate(_LIGATURES), page=chunk.page, bbox=chunk.bbox
        )
        for chunk in result.chunks
        if len(chunk.text) >= MIN_PDF_CHUNK_CHARS
    ]


def markdown_drafts(chunks: Sequence[MarkdownChunk]) -> list[ChunkDraft]:
    return [ChunkDraft(tier=ChunkTier.FULLTEXT, text=chunk.text_with_heading) for chunk in chunks]


def abstract_draft(abstract: str | None) -> list[ChunkDraft]:
    text = " ".join((abstract or "").split())
    return [ChunkDraft(tier=ChunkTier.ABSTRACT, text=text)] if text else []


async def _embed(
    services: PipelineServices, texts: Sequence[str], dimensions: int
) -> tuple[list[bytes | None], str | None]:
    blobs: list[bytes | None] = []
    try:
        for start in range(0, len(texts), EMBED_BATCH):
            vectors = await services.embedder.embed(list(texts[start : start + EMBED_BATCH]))
            for vector in vectors:
                blobs.append(pack_vector(vector) if len(vector) == dimensions else None)
    except Exception as error:
        logger.warning("Chunk embedding failed: %s", error)
        return [None] * len(texts), f"{type(error).__name__}: {error}"
    refused = sum(blob is None for blob in blobs)
    note = f"{refused} vector(s) had the wrong dimension" if refused else None
    return blobs, note


async def store_chunks(
    services: PipelineServices,
    *,
    workspace_id: str,
    source_id: str,
    title: str,
    drafts: Sequence[ChunkDraft],
    dimensions: int,
) -> IndexResult:
    """Replace the chunks of a source with `drafts`. Embedding failures keep BM25-only rows."""

    texts = [f"{title}\n\n{draft.text}"[:EMBED_MAX_CHARS] for draft in drafts]
    blobs, error = await _embed(services, texts, dimensions) if drafts else ([], None)
    rows = [
        ChunkRow(
            workspace_id=workspace_id,
            source_id=source_id,
            tier=draft.tier,
            ordinal=ordinal,
            page=draft.page,
            bbox_json=json.dumps(list(draft.bbox)) if draft.bbox else None,
            text=draft.text,
            embedding=blob,
            token_count=len(draft.text.split()),
        )
        for ordinal, (draft, blob) in enumerate(zip(drafts, blobs, strict=True))
    ]
    await replace_chunks(services.repositories, source_id, rows)
    return IndexResult(
        chunks=len(rows),
        embedded=sum(blob is not None for blob in blobs),
        abstract_chunks=sum(draft.tier == ChunkTier.ABSTRACT for draft in drafts),
        error=error,
    )
