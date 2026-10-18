"""Acquire full text for SCREEN_PROMOTED sources: OA PDF or web snapshot -> chunks -> embeddings.

A source without full text keeps an abstract-only ABSTRACT chunk, a `NO_FULL_TEXT` note in
`extra_json.full_text`, and a FLAGGED verdict; the run never blocks. A source with neither full
text nor an abstract becomes ACQUIRE_FAILED. Citation links come from `literature.related`.
"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from hannovators_deep_researcher.models.enums import (
    ChunkTier,
    RejectionCode,
    SourceLinkKind,
    SourceOrigin,
    SourceStatus,
    TraceEventKind,
    VerdictOutcome,
)
from hannovators_deep_researcher.persistence.queries.acquire import add_links
from hannovators_deep_researcher.persistence.queries.ingest import chunk_counts
from hannovators_deep_researcher.persistence.tables import SourceRow
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.acquire.fulltext import (
    candidate_record,
    describe_error,
    download_pdf,
    fetch_snapshot,
    http_client,
    index_abstract,
    index_markdown,
    index_pdf,
    merged_extra,
    record_verdict,
    source_extra,
)

CONCURRENCY = 4
RELATED_LIMIT = 300
NO_FULL_TEXT = RejectionCode.NO_FULL_TEXT.value


@dataclass(frozen=True, slots=True)
class Acquired:
    source_id: str
    full_text: bool
    kind: str
    """`pdf`, `web`, `abstract`, or `none`."""
    chunks: int = 0
    reason: str | None = None


def _pdf_urls(source: SourceRow, oa_url: str | None) -> list[str]:
    urls = [source.pdf_url, oa_url]
    if source.url and source.url.lower().split("?", 1)[0].endswith(".pdf"):
        urls.append(source.url)
    return list(dict.fromkeys(url for url in urls if url))


async def _try_pdf(
    ctx: StageContext, http: httpx.AsyncClient, source: SourceRow, urls: Sequence[str]
) -> tuple[Acquired | None, list[str]]:
    errors: list[str] = []
    for url in urls:
        try:
            relative = await download_pdf(
                ctx, http, workspace_id=ctx.workspace_id, source_id=source.id, url=url
            )
            indexed = await index_pdf(ctx, source, relative, ctx.settings.embedding_dimensions)
        except Exception as error:
            errors.append(f"{url}: {describe_error(error)}")
            continue
        await ctx.repositories.update_source_fields(
            source.id,
            raw_path=relative,
            pdf_url=url,
            extra_json=merged_extra(
                source,
                {
                    "full_text": {
                        "status": "PDF",
                        "pages": indexed.chunks.page_count,
                        "embedded": indexed.index.embedded,
                    }
                },
            ),
        )
        return Acquired(source.id, True, "pdf", indexed.index.chunks), errors
    return None, errors


async def _try_web(ctx: StageContext, source: SourceRow) -> tuple[Acquired | None, list[str]]:
    url = source.url or (source.external_id if source.external_id.startswith("http") else None)
    if url is None:
        return None, []
    try:
        relative, markdown, _title = await fetch_snapshot(
            ctx, workspace_id=ctx.workspace_id, source_id=source.id, url=url
        )
        index = await index_markdown(ctx, source, markdown, ctx.settings.embedding_dimensions)
    except Exception as error:
        return None, [f"{url}: {describe_error(error)}"]
    await ctx.repositories.update_source_fields(
        source.id,
        raw_path=relative,
        extra_json=merged_extra(
            source, {"full_text": {"status": "SNAPSHOT", "embedded": index.embedded}}
        ),
    )
    return Acquired(source.id, True, "web", index.chunks), []


async def _fallback(ctx: StageContext, source: SourceRow, errors: list[str]) -> Acquired:
    reason = "; ".join(errors) or "no open-access full text found"
    note = {"full_text": {"status": NO_FULL_TEXT, "reason": reason[:800]}}
    if source.abstract and source.abstract.strip():
        index = await index_abstract(ctx, source, ctx.settings.embedding_dimensions)
        await ctx.repositories.update_source_fields(
            source.id, extra_json=merged_extra(source, note)
        )
        return Acquired(source.id, False, "abstract", index.chunks, reason)
    await ctx.repositories.update_source_fields(
        source.id,
        status=SourceStatus.ACQUIRE_FAILED,
        rejection_code=RejectionCode.NO_FULL_TEXT,
        decision_explanation=f"No full text and no abstract: {reason[:300]}",
        extra_json=merged_extra(source, note),
    )
    return Acquired(source.id, False, "none", 0, reason)


async def acquire_source(ctx: StageContext, http: httpx.AsyncClient, source: SourceRow) -> Acquired:
    """Full text for one source, or the abstract-only fallback. Never raises."""

    errors: list[str] = []
    try:
        result: Acquired | None = None
        if source.origin != SourceOrigin.WEB:
            oa_url = await ctx.literature.open_access_pdf_url(candidate_record(source))
            result, errors = await _try_pdf(ctx, http, source, _pdf_urls(source, oa_url))
        else:
            result, errors = await _try_pdf(ctx, http, source, _pdf_urls(source, None))
            if result is None:
                result, web_errors = await _try_web(ctx, source)
                errors += web_errors
        if result is None:
            result = await _fallback(ctx, source, errors)
    except Exception as error:
        errors.append(describe_error(error))
        result = await _fallback(ctx, source, errors)
    await _verdict(ctx, source, result)
    return result


async def _verdict(ctx: StageContext, source: SourceRow, result: Acquired) -> None:
    if result.full_text:
        await record_verdict(
            ctx,
            source,
            outcome=VerdictOutcome.KEPT,
            confidence=1.0,
            summary=f"Full text ({result.kind}): {result.chunks} chunks",
            response={"reason": "FULL_TEXT", "kind": result.kind, "chunks": result.chunks},
        )
        return
    await ctx.emit(
        TraceEventKind.WARNING,
        f"No full text for {source.title[:80]!r}; kept abstract only",
        {"source_id": source.id, "reason": (result.reason or "")[:300]},
    )
    await record_verdict(
        ctx,
        source,
        outcome=VerdictOutcome.FLAGGED,
        confidence=0.5 if result.kind == "abstract" else 0.0,
        summary=f"{NO_FULL_TEXT}: {result.kind} only",
        response={
            "reason": NO_FULL_TEXT,
            "rejection_code": NO_FULL_TEXT,
            "kind": result.kind,
            "chunks": result.chunks,
            "details": result.reason,
        },
    )


async def _targets(ctx: StageContext) -> list[SourceRow]:
    sources = await ctx.repositories.list_sources(
        ctx.workspace_id, [SourceStatus.SCREEN_PROMOTED, SourceStatus.SEED]
    )
    counts = await chunk_counts(ctx.repositories, ctx.workspace_id)
    targets = []
    for source in sources:
        has_full_text = counts.get((source.id, ChunkTier.FULLTEXT), 0) > 0
        has_any = has_full_text or counts.get((source.id, ChunkTier.ABSTRACT), 0) > 0
        if source.status == SourceStatus.SEED and has_any:
            continue
        if not has_full_text:
            targets.append(source)
    return targets


def _pmid(source: SourceRow) -> str | None:
    pmid = source_extra(source).get("pmid")
    if isinstance(pmid, str) and pmid.isdigit():
        return pmid
    return source.external_id if source.external_id.isdigit() else None


async def link_sources(ctx: StageContext) -> int:
    """Add CITES / RELATED links between workspace sources from `literature.related`."""

    sources = await ctx.repositories.list_sources(ctx.workspace_id)
    by_pmid = {pmid: source.id for source in sources if (pmid := _pmid(source))}
    anchors = [
        pmid
        for source in sources
        if source.status in (SourceStatus.SEED, SourceStatus.SCREEN_PROMOTED)
        and (pmid := _pmid(source))
    ]
    if not anchors:
        return 0
    try:
        records = await ctx.literature.related(anchors, limit=RELATED_LIMIT)
    except Exception as error:
        await ctx.emit(TraceEventKind.WARNING, f"citation links failed: {describe_error(error)}")
        return 0
    known = {source.id: source.external_id for source in sources}
    by_external = {external: source_id for source_id, external in known.items()}
    links = []
    for record in records:
        source = by_external.get(record.from_external_id) or by_pmid.get(record.from_external_id)
        target = by_external.get(record.to_external_id) or by_pmid.get(record.to_external_id)
        if source and target and record.kind in (SourceLinkKind.CITES, SourceLinkKind.RELATED):
            links.append((source, target, record.kind))
    return await add_links(ctx.repositories, ctx.workspace_id, links)


async def run(ctx: StageContext) -> None:
    targets = await _targets(ctx)
    total = len(targets)
    await ctx.emit(
        TraceEventKind.PROGRESS, f"Acquiring full text for {total} sources", {"total": total}
    )
    limit = asyncio.Semaphore(CONCURRENCY)
    tally = {"pdf": 0, "web": 0, "abstract": 0, "none": 0}

    async def one(http: httpx.AsyncClient, source: SourceRow) -> None:
        async with limit:
            result = await acquire_source(ctx, http, source)
        tally[result.kind] += 1
        done = sum(tally.values())
        await ctx.emit(
            TraceEventKind.PROGRESS,
            f"Acquired {done}/{total}: {tally['pdf']} PDF, {tally['web']} web, "
            f"{tally['abstract']} abstract only, {tally['none']} failed",
            {"done": done, "total": total, **tally},
        )

    async with http_client(ctx) as http:
        await asyncio.gather(*(one(http, source) for source in targets))
    links = await link_sources(ctx)
    await ctx.emit(
        TraceEventKind.DECISION,
        f"Acquire done: {tally['pdf'] + tally['web']} full text, "
        f"{tally['abstract']} abstract only, {tally['none']} failed, {links} links",
        {**tally, "links": links},
    )
