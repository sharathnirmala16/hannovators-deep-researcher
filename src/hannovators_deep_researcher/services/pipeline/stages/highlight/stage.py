"""Highlight claim quotes in source PDFs: highlight rows + `highlighted.pdf` per source.

Each claim with a quote whose source has a `raw.pdf` (appraised sources and the "Seed finding"
claims that ingest extracts from seed PDFs) is located with `page.search_for` (full quote, then
its first ~60 characters). When that fails, Jev chooses among at most 19 retrieved
chunks of the source (plus NONE); a choice at or above `highlight_confidence_floor` highlights
that chunk's bbox. Web sources have no pages, so they get no highlight rows.
"""

import asyncio
import json
from collections import defaultdict
from collections.abc import Sequence

from hannovators_deep_researcher.models.contracts import Rect
from hannovators_deep_researcher.models.decisions import DecisionQuestion
from hannovators_deep_researcher.models.enums import (
    ClaimKind,
    DecisionQuestionType,
    HighlightMethod,
    TraceEventKind,
    TrajectoryKind,
    VerdictOutcome,
)
from hannovators_deep_researcher.persistence.queries.highlight import replace_highlights
from hannovators_deep_researcher.persistence.tables import (
    ChunkRow,
    ClaimRow,
    HighlightRow,
    SourceRow,
)
from hannovators_deep_researcher.services.documents.files import (
    HIGHLIGHTED_PDF,
    resolve_data_path,
    source_path,
)
from hannovators_deep_researcher.services.documents.highlighter import (
    HighlightSpec,
    write_highlighted_pdf,
)
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.acquire.fulltext import describe_error
from hannovators_deep_researcher.services.retrieval.hybrid import hierarchical_retrieve
from hannovators_deep_researcher.services.retrieval.quotes import (
    SHORT_QUOTE_CHARS,
    QuoteMatch,
    locate_quote,
)

CLAIM_COLORS: dict[str, str] = {
    ClaimKind.METRIC: "#FFE066",
    ClaimKind.CLAIM: "#8CE99A",
    ClaimKind.RECOMMENDATION: "#74C0FC",
}
JEV_CANDIDATES = 19
JEV_KEY = "passage"
NONE_OPTION = "NONE"
OPTION_CHARS = 500
PREFIX_SCORE = 0.8
SHORT_QUOTE_SCORE = 0.5
"""A whole quote shorter than `SHORT_QUOTE_CHARS` is found, but it may match the wrong spot."""


def _is_pdf(source: SourceRow) -> bool:
    return bool(source.raw_path and source.raw_path.lower().endswith(".pdf"))


def _bbox(chunk: ChunkRow) -> Rect | None:
    if not chunk.bbox_json:
        return None
    values = json.loads(chunk.bbox_json)
    return (float(values[0]), float(values[1]), float(values[2]), float(values[3]))


def _chunk_at(chunks: Sequence[ChunkRow], page: int, rect: Rect) -> str | None:
    """The chunk on `page` whose bbox contains the centre of `rect`."""

    x = (rect[0] + rect[2]) / 2
    y = (rect[1] + rect[3]) / 2
    for chunk in chunks:
        box = _bbox(chunk)
        if (
            chunk.page == page
            and box
            and box[0] - 2 <= x <= box[2] + 2
            and box[1] - 2 <= y <= box[3] + 2
        ):
            return chunk.id
    return None


def _row(
    ctx: StageContext,
    claim: ClaimRow,
    source: SourceRow,
    *,
    page: int,
    rects: list[Rect],
    method: HighlightMethod,
    score: float,
    chunk_id: str | None,
) -> HighlightRow:
    return HighlightRow(
        workspace_id=ctx.workspace_id,
        source_id=source.id,
        claim_id=claim.id,
        chunk_id=chunk_id,
        page=page,
        rects_json=json.dumps([list(rect) for rect in rects]),
        method=method,
        score=round(score, 4),
        color=CLAIM_COLORS.get(claim.kind, CLAIM_COLORS[ClaimKind.CLAIM]),
    )


async def _jev_choice(
    ctx: StageContext, claim: ClaimRow, source: SourceRow
) -> tuple[ChunkRow | None, float, str]:
    """Ask Jev which retrieved chunk holds the claim's evidence: (chunk, confidence, note)."""

    retrieval = await hierarchical_retrieve(
        ctx,
        f"{claim.text}\n{claim.quote or ''}",
        ctx.workspace_id,
        source_ids=[source.id],
        k=JEV_CANDIDATES * 2,
        rewrite=False,
        step_name="highlight.retrieve",
    )
    candidates = [chunk for chunk in retrieval.chunks if chunk.page and chunk.bbox][:JEV_CANDIDATES]
    if not candidates:
        return None, 0.0, "no candidate chunks with a page"
    options: dict[str, str | None] = {
        f"C{index}": " ".join(chunk.text.split())[:OPTION_CHARS]
        for index, chunk in enumerate(candidates, start=1)
    }
    options[NONE_OPTION] = "None of these passages holds the quoted evidence"
    question = DecisionQuestion(
        type=DecisionQuestionType.CHOICE,
        instructions="Which passage contains the evidence quoted for this claim?",
        criteria=options,
    )
    state = f"Claim ({claim.kind}, {claim.label}): {claim.text}\n\nQuoted evidence: {claim.quote}"
    try:
        answers = await ctx.decisions.evaluate(state, {JEV_KEY: question})
    except Exception as error:
        return None, 0.0, f"Jev failed: {describe_error(error)}"
    answer = answers.get(JEV_KEY)
    choice = answer.choice if answer else None
    if answer is None or choice is None or choice == NONE_OPTION or choice not in options:
        return None, 0.0, f"Jev chose {choice or 'nothing'}"
    confidence = answer.confidence
    if confidence is None:
        confidence = answer.probabilities.get(choice, 0.0)
    picked = candidates[int(choice[1:]) - 1]
    chunk = await ctx.repositories.get(ChunkRow, picked.chunk_id)
    return chunk, float(confidence), f"Jev chose {choice} ({confidence:.2f})"


def _search_score(match: QuoteMatch) -> float:
    if not match.full:
        return PREFIX_SCORE
    return SHORT_QUOTE_SCORE if len(match.needle) < SHORT_QUOTE_CHARS else 1.0


async def _locate(
    ctx: StageContext,
    source: SourceRow,
    claim: ClaimRow,
    chunks: Sequence[ChunkRow],
) -> tuple[HighlightRow | None, str]:
    path = resolve_data_path(source.raw_path or "")
    match: QuoteMatch | None = await asyncio.to_thread(locate_quote, path, claim.quote or "")
    if match is not None and match.rects:
        return (
            _row(
                ctx,
                claim,
                source,
                page=match.page,
                rects=match.rects,
                method=HighlightMethod.SEARCH,
                score=_search_score(match),
                chunk_id=_chunk_at(chunks, match.page, match.rects[0]),
            ),
            "search: full quote" if match.full else "search: quote prefix",
        )
    chunk, confidence, note = await _jev_choice(ctx, claim, source)
    box = _bbox(chunk) if chunk else None
    if chunk is None or box is None or chunk.page is None:
        return None, note
    if confidence < ctx.settings.highlight_confidence_floor:
        return None, f"{note}; below the confidence floor"
    row = _row(
        ctx,
        claim,
        source,
        page=chunk.page,
        rects=[box],
        method=HighlightMethod.JEV_CHOICE,
        score=confidence,
        chunk_id=chunk.id,
    )
    return row, note


async def _claim_verdict(
    ctx: StageContext, claim: ClaimRow, source: SourceRow, row: HighlightRow | None, note: str
) -> None:
    await ctx.trajectory.record(
        kind=TrajectoryKind.VERDICT,
        name="highlight.verdict",
        target=source.raw_path,
        summary=(f"p.{row.page} {row.method}" if row else "quote not located") + f": {note}",
        source_ids=[source.id],
        outcome=VerdictOutcome.KEPT if row else VerdictOutcome.FLAGGED,
        confidence=row.score if row else 0.0,
        response={
            "claim_id": claim.id,
            "quote": claim.quote,
            "located": row is not None,
            "page": row.page if row else None,
            "method": row.method if row else None,
            "rects": json.loads(row.rects_json) if row else [],
            "note": note,
        },
    )


async def highlight_source(
    ctx: StageContext, source: SourceRow, claims: Sequence[ClaimRow]
) -> tuple[int, int]:
    """Highlight one source's claims. Returns (located, total)."""

    chunks = await ctx.repositories.list_chunks(ctx.workspace_id, source.id)
    rows: list[HighlightRow] = []
    for claim in claims:
        try:
            row, note = await _locate(ctx, source, claim, chunks)
        except Exception as error:
            row, note = None, describe_error(error)
        await _claim_verdict(ctx, claim, source, row, note)
        if row is not None:
            rows.append(row)
    await replace_highlights(ctx.repositories, source.id, rows)
    if rows:
        relative = source_path(ctx.workspace_id, source.id, HIGHLIGHTED_PDF)
        specs = [
            HighlightSpec(
                page=row.page, rects=[tuple(r) for r in json.loads(row.rects_json)], color=row.color
            )
            for row in rows
        ]
        await asyncio.to_thread(
            write_highlighted_pdf,
            resolve_data_path(source.raw_path or ""),
            resolve_data_path(relative),
            specs,
        )
        await ctx.repositories.update_source_fields(source.id, highlighted_path=relative)
    return len(rows), len(claims)


async def run(ctx: StageContext) -> None:
    claims = [
        claim
        for claim in await ctx.repositories.list_claims(ctx.workspace_id)
        if claim.source_id and claim.quote and claim.quote.strip()
    ]
    sources = {
        source.id: source for source in await ctx.repositories.list_sources(ctx.workspace_id)
    }
    by_source: dict[str, list[ClaimRow]] = defaultdict(list)
    skipped = 0
    for claim in claims:
        source = sources.get(claim.source_id or "")
        if source is not None and _is_pdf(source):
            by_source[source.id].append(claim)
        else:
            skipped += 1
    await ctx.emit(
        TraceEventKind.PROGRESS,
        f"Highlighting {len(claims) - skipped} quotes in {len(by_source)} PDFs "
        f"({skipped} without a PDF)",
        {"claims": len(claims), "pdfs": len(by_source), "skipped": skipped},
    )
    located = total = 0
    for source_id, source_claims in by_source.items():
        source = sources[source_id]
        try:
            found, count = await highlight_source(ctx, source, source_claims)
        except Exception as error:
            await ctx.emit(
                TraceEventKind.WARNING,
                f"Highlighting failed for {source.title[:80]!r}: {describe_error(error)}",
                {"source_id": source_id},
            )
            continue
        located += found
        total += count
        await ctx.emit(
            TraceEventKind.PROGRESS,
            f"Highlighted {found}/{count} quotes in {source.title[:60]!r}",
            {"source_id": source_id, "located": found, "claims": count},
        )
    await ctx.emit(
        TraceEventKind.DECISION,
        f"Highlight done: {located}/{total} quotes located in {len(by_source)} PDFs",
        {"located": located, "claims": total, "pdfs": len(by_source), "skipped": skipped},
    )
