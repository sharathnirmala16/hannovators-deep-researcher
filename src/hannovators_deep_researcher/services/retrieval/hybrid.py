"""Hybrid, hierarchical retrieval: BM25 + dense dot product fused with reciprocal rank fusion.

`hierarchical_retrieve` ranks the ABSTRACT tier first to pick the most relevant sources, then
ranks every chunk of those sources (plus sources that have no abstract chunk). When the best
dense score is weak, it rewrites the query once through the chat model and keeps the better
result. Each call records one RETRIEVE trajectory step.
"""

import json
import logging
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from hannovators_deep_researcher.models.base import ContractModel
from hannovators_deep_researcher.models.contracts import Rect, WorkspaceSettings
from hannovators_deep_researcher.models.enums import ChunkTier, ModelRole, TrajectoryKind
from hannovators_deep_researcher.persistence.queries.chat import list_retrieval_chunks
from hannovators_deep_researcher.persistence.tables import ChunkRow
from hannovators_deep_researcher.services.pipeline.context import PipelineServices
from hannovators_deep_researcher.services.ranking import reciprocal_rank_fusion
from hannovators_deep_researcher.services.retrieval.lexical import bm25_scores
from hannovators_deep_researcher.services.retrieval.vectors import query_vector, stack_vectors

logger = logging.getLogger(__name__)

RETRIEVAL_INSTRUCTION = "Given a clinical research question, retrieve passages that answer it"
DEFAULT_K = 8
ABSTRACT_SOURCES = 8
WEAK_DENSE = 0.40
"""Best dense cosine below this triggers one query rewrite."""
RELEVANT_DENSE = 0.30
"""A chunk with a dense cosine at or above this counts as relevant evidence."""

REWRITE_SYSTEM = (
    "You rewrite a question into one short search query for passages in clinical and "
    "scientific papers. Keep the key entities, interventions, comparators, outcomes, and "
    "numbers. Expand abbreviations once. Reply with JSON only."
)


class QueryRewrite(ContractModel):
    """LLM reply: one rewritten retrieval query."""

    query: str

    @classmethod
    def fake_example(cls) -> dict[str, Any]:
        return {"query": "randomized trial outcomes of the intervention versus comparison"}


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    source_id: str
    tier: ChunkTier
    ordinal: int
    page: int | None
    bbox: Rect | None
    text: str
    score: float
    """RRF score (higher is better)."""
    dense: float | None
    lexical: float

    @property
    def relevant(self) -> bool:
        if self.dense is not None:
            return self.dense >= RELEVANT_DENSE
        return self.lexical > 0


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    query: str
    used_query: str
    chunks: list[RetrievedChunk] = field(default_factory=list)
    best_dense: float | None = None
    refused_vectors: int = 0
    step_id: int | None = None

    @property
    def rewritten(self) -> bool:
        return self.used_query != self.query


def _bbox(row: ChunkRow) -> Rect | None:
    if not row.bbox_json:
        return None
    values = json.loads(row.bbox_json)
    if not isinstance(values, list) or len(values) != 4:
        return None
    return (float(values[0]), float(values[1]), float(values[2]), float(values[3]))


def rank_chunks(
    query: str,
    vector: Sequence[float] | None,
    chunks: Sequence[ChunkRow],
    dimensions: int,
) -> tuple[list[RetrievedChunk], int]:
    """Rank `chunks` by RRF over BM25 and dense rankings. Returns (ranked, refused vectors)."""

    if not chunks:
        return [], 0
    lexical = bm25_scores(query, [row.text for row in chunks])
    dense: list[float | None] = [None] * len(chunks)
    refused = 0
    query_array = query_vector(vector, dimensions) if vector is not None else None
    if query_array is not None:
        matrix, positions = stack_vectors([row.embedding for row in chunks], dimensions)
        refused = sum(row.embedding is not None for row in chunks) - len(positions)
        if positions:
            cosines = matrix @ query_array
            for position, cosine in zip(positions, cosines.tolist(), strict=True):
                dense[position] = float(cosine)
    order = range(len(chunks))
    lexical_rank = sorted((i for i in order if lexical[i] > 0), key=lambda i: -lexical[i])
    dense_rank = sorted(
        (i for i in order if dense[i] is not None), key=lambda i: -(dense[i] or 0.0)
    )
    fused = reciprocal_rank_fusion([lexical_rank, dense_rank])
    ranked = [
        RetrievedChunk(
            chunk_id=chunks[i].id,
            source_id=chunks[i].source_id,
            tier=ChunkTier(chunks[i].tier),
            ordinal=chunks[i].ordinal,
            page=chunks[i].page,
            bbox=_bbox(chunks[i]),
            text=chunks[i].text,
            score=round(score, 6),
            dense=None if dense[i] is None else round(float(dense[i] or 0.0), 4),
            lexical=round(lexical[i], 4),
        )
        for i, score in fused
    ]
    return ranked, refused


def _best_dense(chunks: Sequence[RetrievedChunk]) -> float | None:
    values = [chunk.dense for chunk in chunks if chunk.dense is not None]
    return max(values) if values else None


def _is_weak(chunks: Sequence[RetrievedChunk]) -> bool:
    if not chunks:
        return True
    best = _best_dense(chunks)
    if best is None:
        return all(chunk.lexical <= 0 for chunk in chunks)
    return best < WEAK_DENSE


@dataclass(frozen=True, slots=True)
class _Pass:
    chunks: list[RetrievedChunk]
    refused: int
    candidate_sources: list[str]


async def _embed_query(services: PipelineServices, query: str, instruction: str) -> list[float]:
    try:
        [vector] = await services.embedder.embed([query], instruction=instruction)
    except Exception as error:
        logger.warning("Query embedding failed; BM25 only: %s", error)
        return []
    return vector


async def _two_tier_pass(
    services: PipelineServices,
    query: str,
    rows: Sequence[ChunkRow],
    dimensions: int,
    k: int,
    instruction: str,
) -> _Pass:
    vector = await _embed_query(services, query, instruction) or None
    abstracts = [row for row in rows if row.tier == ChunkTier.ABSTRACT]
    ranked_abstracts, refused = rank_chunks(query, vector, abstracts, dimensions)
    top_sources = list(dict.fromkeys(chunk.source_id for chunk in ranked_abstracts))
    with_abstract = {row.source_id for row in abstracts}
    without_abstract = {row.source_id for row in rows} - with_abstract
    candidates = set(top_sources[:ABSTRACT_SOURCES]) | without_abstract
    pool = [row for row in rows if row.source_id in candidates]
    ranked, refused_pool = rank_chunks(query, vector, pool, dimensions)
    return _Pass(
        chunks=ranked[:k],
        refused=max(refused, refused_pool),
        candidate_sources=sorted(candidates),
    )


async def _rewrite(services: PipelineServices, question: str) -> str | None:
    try:
        reply = await services.chat.complete_json(
            role=ModelRole.QUERY,
            system=REWRITE_SYSTEM,
            user=f"Question: {question}",
            schema=QueryRewrite,
        )
    except Exception as error:
        logger.warning("Query rewrite failed: %s", error)
        return None
    query = " ".join(reply.query.split())
    return query if query and query != question else None


async def workspace_dimensions(services: PipelineServices, workspace_id: str) -> int:
    workspace = await services.repositories.get_workspace(workspace_id)
    if workspace is None:
        raise LookupError(f"workspace {workspace_id} not found")
    return WorkspaceSettings.model_validate_json(workspace.settings_json).embedding_dimensions


async def hierarchical_retrieve(
    services: PipelineServices,
    question: str,
    workspace_id: str,
    source_ids: Collection[str] | None = None,
    k: int = DEFAULT_K,
    *,
    rewrite: bool = True,
    instruction: str = RETRIEVAL_INSTRUCTION,
    step_name: str = "retrieve.hybrid",
) -> RetrievalResult:
    """Top `k` chunks for `question` among `source_ids` (all sources when None)."""

    dimensions = await workspace_dimensions(services, workspace_id)
    rows = await list_retrieval_chunks(services.repositories, workspace_id, source_ids=source_ids)
    first = await _two_tier_pass(services, question, rows, dimensions, k, instruction)
    best, used_query = first, question
    rewritten_query: str | None = None
    if rewrite and rows and _is_weak(first.chunks):
        rewritten_query = await _rewrite(services, question)
        if rewritten_query:
            second = await _two_tier_pass(
                services, rewritten_query, rows, dimensions, k, instruction
            )
            if (_best_dense(second.chunks) or -1.0) > (_best_dense(first.chunks) or -1.0):
                best, used_query = second, rewritten_query
    result = RetrievalResult(
        query=question,
        used_query=used_query,
        chunks=best.chunks,
        best_dense=_best_dense(best.chunks),
        refused_vectors=best.refused,
    )
    step_id = await _record(services, workspace_id, result, rewritten_query, len(rows), step_name)
    return replace(result, step_id=step_id)


async def _record(
    services: PipelineServices,
    workspace_id: str,
    result: RetrievalResult,
    rewritten_query: str | None,
    pool_size: int,
    step_name: str,
) -> int | None:
    best = result.best_dense
    return await services.trajectory.record(
        kind=TrajectoryKind.RETRIEVE,
        name=step_name,
        workspace_id=workspace_id,
        target="bm25+dense+rrf",
        summary=(
            f"{len(result.chunks)} of {pool_size} chunks"
            + (f", best dense {best:.2f}" if best is not None else ", BM25 only")
            + (" (rewritten query)" if result.rewritten else "")
        ),
        request={"query": result.query, "pool_size": pool_size},
        response={
            "used_query": result.used_query,
            "rewrite_tried": rewritten_query,
            "refused_vectors": result.refused_vectors,
            "best_dense": best,
            "results": [
                {
                    "chunk_id": chunk.chunk_id,
                    "source_id": chunk.source_id,
                    "tier": chunk.tier,
                    "page": chunk.page,
                    "score": chunk.score,
                    "dense": chunk.dense,
                    "bm25": chunk.lexical,
                }
                for chunk in result.chunks
            ],
        },
        source_ids=list(dict.fromkeys(chunk.source_id for chunk in result.chunks)),
    )
