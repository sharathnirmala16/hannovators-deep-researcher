"""Ingest SEED sources: PDFs, PMIDs, DOIs, and URLs become chunks, embeddings, and metadata.

- PDF: chunk (ABSTRACT + FULLTEXT tiers, page + bbox), fill empty metadata from PyMuPDF
  metadata, one LLM extraction over the first pages, and a PubMed lookup when a DOI shows up.
- PMID / DOI: PubMed record, then the open-access PDF when there is one (else the abstract).
- URL: web fetch -> `snapshot.md` -> markdown chunks (a `.pdf` URL is downloaded instead).

Every seed gets one VERDICT step (KEPT, or FLAGGED with a WARNING event on failure) and a
compact `extra_json.seed_summary` that decompose can read. Failures never stop the run.
"""

import asyncio
import json
from dataclasses import dataclass, field

import httpx

from hannovators_deep_researcher.models.enums import (
    ChunkTier,
    ModelRole,
    SourceStatus,
    TraceEventKind,
    VerdictOutcome,
)
from hannovators_deep_researcher.models.literature import CandidateRecord
from hannovators_deep_researcher.persistence.tables import SourceRow
from hannovators_deep_researcher.services.documents.files import resolve_data_path
from hannovators_deep_researcher.services.documents.pdf_chunker import PdfChunkResult, chunk_pdf
from hannovators_deep_researcher.services.pipeline.context import StageContext
from hannovators_deep_researcher.services.pipeline.stages.acquire.fulltext import (
    describe_error,
    download_pdf,
    fetch_snapshot,
    http_client,
    index_abstract,
    index_markdown,
    merged_extra,
    record_verdict,
    source_extra,
)
from hannovators_deep_researcher.services.pipeline.stages.ingest.metadata import (
    EXTRACT_SYSTEM,
    PdfFacts,
    SeedMetadata,
    find_doi,
    plausible_title,
    read_pdf_facts,
)
from hannovators_deep_researcher.services.retrieval.indexing import (
    abstract_draft,
    pdf_drafts,
    store_chunks,
)

CONCURRENCY = 3
SUMMARY_ABSTRACT_CHARS = 1_500
SUMMARY_KEY_TEXT_CHARS = 1_500
_DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:")
_KEY_SECTION = ("result", "conclusion", "finding", "interpretation")


@dataclass
class SeedOutcome:
    kind: str
    chunks: int = 0
    full_text: bool = False
    problems: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)


def _seed_kind(source: SourceRow) -> str:
    external = source.external_id.strip()
    lowered = external.lower()
    if source.raw_path:
        return "pdf"
    if external.isdigit() or (lowered.startswith("pmid:") and external[5:].strip().isdigit()):
        return "pmid"
    if lowered.startswith("10.") or lowered.startswith(_DOI_PREFIXES):
        return "doi"
    if lowered.startswith(("http://", "https://")) or source.url:
        return "url"
    return "unknown"


def _bare_doi(value: str) -> str:
    lowered = value.strip()
    for prefix in _DOI_PREFIXES:
        if lowered.lower().startswith(prefix):
            return lowered[len(prefix) :].strip()
    return lowered


def _placeholder_title(source: SourceRow) -> bool:
    title = source.title.strip()
    return (
        not title
        or title == source.external_id
        or title.lower().endswith(".pdf")
        or title.upper().startswith(("PMID", "DOI", "HTTP"))
    )


async def _lookup(ctx: StageContext, query: str) -> CandidateRecord | None:
    try:
        records = await ctx.literature.search(query, limit=1)
    except Exception as error:
        await ctx.emit(TraceEventKind.WARNING, f"PubMed lookup failed: {describe_error(error)}")
        return None
    return records[0] if records else None


def _record_fields(source: SourceRow, record: CandidateRecord) -> dict[str, object]:
    fields: dict[str, object] = {}
    if _placeholder_title(source) and record.title:
        fields["title"] = record.title
    if source.authors_json in (None, "", "[]") and record.authors:
        fields["authors_json"] = json.dumps(record.authors)
    if source.year is None and record.year:
        fields["year"] = record.year
    if not source.venue and record.venue:
        fields["venue"] = record.venue
    if not (source.abstract or "").strip() and record.abstract:
        fields["abstract"] = record.abstract
    if not source.url and record.url:
        fields["url"] = record.url
    extra = {
        "pmid": record.pmid,
        "doi": record.doi,
        "pmcid": record.pmcid,
        "publication_types": record.publication_types,
    }
    fields["extra_json"] = merged_extra(
        source, {key: value for key, value in extra.items() if value}
    )
    return fields


async def _apply_record(ctx: StageContext, source: SourceRow, record: CandidateRecord) -> SourceRow:
    return await ctx.repositories.update_source_fields(source.id, **_record_fields(source, record))


async def _extract(ctx: StageContext, facts: PdfFacts) -> SeedMetadata | None:
    if not facts.first_text.strip():
        return None
    try:
        return await ctx.chat.complete_json(
            role=ModelRole.QUERY,
            system=EXTRACT_SYSTEM,
            user=f"First pages of the paper:\n\n{facts.first_text}",
            schema=SeedMetadata,
        )
    except Exception as error:
        await ctx.emit(
            TraceEventKind.WARNING, f"Seed metadata extraction failed: {describe_error(error)}"
        )
        return None


def _pdf_fields(
    source: SourceRow, facts: PdfFacts, meta: SeedMetadata | None, abstract: str
) -> dict[str, object]:
    fields: dict[str, object] = {}
    title = (meta and plausible_title(meta.title)) or facts.title
    if _placeholder_title(source) and title:
        fields["title"] = title
    authors = (meta.authors if meta else []) or facts.authors
    if source.authors_json in (None, "", "[]") and authors:
        fields["authors_json"] = json.dumps(authors[:30])
    year = (meta.year if meta else None) or facts.year
    if source.year is None and year:
        fields["year"] = year
    if not source.venue and meta and meta.venue:
        fields["venue"] = meta.venue
    if not source.study_design and meta and meta.study_design:
        fields["study_design"] = meta.study_design
    best_abstract = abstract or (meta.abstract.strip() if meta else "")
    if not (source.abstract or "").strip() and best_abstract:
        fields["abstract"] = best_abstract
    return fields


def _abstract_text(result: PdfChunkResult) -> str:
    return " ".join(chunk.text for chunk in result.chunks if chunk.tier == ChunkTier.ABSTRACT)


async def _ingest_pdf(ctx: StageContext, source: SourceRow) -> SeedOutcome:
    outcome = SeedOutcome(kind="pdf")
    path = resolve_data_path(source.raw_path or "")
    facts = await asyncio.to_thread(read_pdf_facts, path)
    meta = await _extract(ctx, facts)
    outcome.key_findings = list(meta.key_findings[:5]) if meta else []
    result = await asyncio.to_thread(chunk_pdf, path)
    pdf_abstract = _abstract_text(result)
    doi = facts.doi or (meta.doi if meta else None) or find_doi(pdf_abstract)
    record = await _lookup(ctx, f"{doi}[doi]") if doi else None
    if record is not None:
        source = await _apply_record(ctx, source, record)
    fields = _pdf_fields(source, facts, meta, pdf_abstract)
    if doi and "doi" not in source_extra(source):
        fields["extra_json"] = merged_extra(source, {"doi": doi})
    if fields:
        source = await ctx.repositories.update_source_fields(source.id, **fields)
    if not result.has_text_layer or not result.chunks:
        outcome.problems.append("the PDF has no text layer")
        index = await index_abstract(ctx, source, ctx.settings.embedding_dimensions)
        outcome.chunks = index.chunks
        return outcome
    drafts = pdf_drafts(result)
    if not pdf_abstract:
        drafts = abstract_draft(source.abstract) + drafts
    index = await store_chunks(
        ctx,
        workspace_id=ctx.workspace_id,
        source_id=source.id,
        title=source.title,
        drafts=drafts,
        dimensions=ctx.settings.embedding_dimensions,
    )
    if index.error:
        outcome.problems.append(f"embeddings: {index.error}")
    outcome.chunks, outcome.full_text = index.chunks, True
    return outcome


async def _attach_pdf(
    ctx: StageContext, http: httpx.AsyncClient, source: SourceRow, url: str, outcome: SeedOutcome
) -> SourceRow | None:
    try:
        relative = await download_pdf(
            ctx, http, workspace_id=ctx.workspace_id, source_id=source.id, url=url
        )
    except Exception as error:
        outcome.problems.append(f"PDF download failed: {describe_error(error)}")
        return None
    return await ctx.repositories.update_source_fields(source.id, raw_path=relative, pdf_url=url)


async def _ingest_reference(
    ctx: StageContext, http: httpx.AsyncClient, source: SourceRow, kind: str
) -> SeedOutcome:
    outcome = SeedOutcome(kind=kind)
    external = source.external_id.strip()
    query = (
        f"{external.split(':')[-1].strip()}[uid]"
        if kind == "pmid"
        else f"{_bare_doi(external)}[doi]"
    )
    record = await _lookup(ctx, query)
    if record is None:
        if kind == "doi":
            return await _ingest_url(ctx, http, source, f"https://doi.org/{_bare_doi(external)}")
        outcome.problems.append("PubMed has no record for this PMID")
        return outcome
    source = await _apply_record(ctx, source, record)
    oa_url = None
    try:
        oa_url = await ctx.literature.open_access_pdf_url(record)
    except Exception as error:
        outcome.problems.append(f"open-access lookup failed: {describe_error(error)}")
    with_pdf = await _attach_pdf(ctx, http, source, oa_url, outcome) if oa_url else None
    if with_pdf is not None:
        source = with_pdf
        return await _finish_pdf(ctx, source, outcome)
    outcome.problems.append("no open-access PDF; abstract only")
    index = await index_abstract(ctx, source, ctx.settings.embedding_dimensions)
    outcome.chunks = index.chunks
    return outcome


async def _finish_pdf(ctx: StageContext, source: SourceRow, outcome: SeedOutcome) -> SeedOutcome:
    try:
        pdf = await _ingest_pdf(ctx, source)
    except Exception as error:
        outcome.problems.append(f"PDF unreadable: {describe_error(error)}")
        index = await index_abstract(ctx, source, ctx.settings.embedding_dimensions)
        outcome.chunks = index.chunks
        return outcome
    pdf.kind = outcome.kind
    pdf.problems = outcome.problems + pdf.problems
    return pdf


async def _ingest_url(
    ctx: StageContext, http: httpx.AsyncClient, source: SourceRow, url: str
) -> SeedOutcome:
    outcome = SeedOutcome(kind="url")
    if url.lower().split("?", 1)[0].endswith(".pdf"):
        with_pdf = await _attach_pdf(ctx, http, source, url, outcome)
        if with_pdf is not None:
            return await _finish_pdf(ctx, with_pdf, outcome)
    try:
        relative, markdown, title = await fetch_snapshot(
            ctx, workspace_id=ctx.workspace_id, source_id=source.id, url=url
        )
    except Exception as error:
        outcome.problems.append(f"fetch failed: {describe_error(error)}")
        return outcome
    fields: dict[str, object] = {"raw_path": relative}
    if _placeholder_title(source) and title:
        fields["title"] = title
    if not source.url:
        fields["url"] = url
    if not (source.abstract or "").strip():
        fields["abstract"] = " ".join(markdown.split())[:SUMMARY_ABSTRACT_CHARS]
    source = await ctx.repositories.update_source_fields(source.id, **fields)
    index = await index_markdown(ctx, source, markdown, ctx.settings.embedding_dimensions)
    outcome.chunks, outcome.full_text = index.chunks, True
    return outcome


async def _key_text(ctx: StageContext, source: SourceRow) -> str:
    chunks = await ctx.repositories.list_chunks(ctx.workspace_id, source.id)
    full = [chunk for chunk in chunks if chunk.tier == ChunkTier.FULLTEXT]
    keyed = [c for c in full if any(word in c.text[:60].lower() for word in _KEY_SECTION)]
    picked: list[str] = []
    total = 0
    for chunk in keyed or full:
        if total >= SUMMARY_KEY_TEXT_CHARS:
            break
        picked.append(chunk.text)
        total += len(chunk.text)
    return " ".join(picked)[:SUMMARY_KEY_TEXT_CHARS]


async def _summarize(ctx: StageContext, source_id: str, outcome: SeedOutcome) -> SourceRow:
    source = await ctx.repositories.get_source(source_id)
    if source is None:
        raise LookupError(f"source {source_id} disappeared")
    summary = {
        "title": source.title,
        "year": source.year,
        "kind": outcome.kind,
        "full_text": outcome.full_text,
        "abstract": (source.abstract or "")[:SUMMARY_ABSTRACT_CHARS],
        "key_findings": outcome.key_findings,
        "key_text": await _key_text(ctx, source),
        "chunks": outcome.chunks,
    }
    return await ctx.repositories.update_source_fields(
        source.id, extra_json=merged_extra(source, {"seed_summary": summary})
    )


async def ingest_seed(ctx: StageContext, http: httpx.AsyncClient, source: SourceRow) -> SeedOutcome:
    kind = _seed_kind(source)
    try:
        if kind == "pdf":
            outcome = await _ingest_pdf(ctx, source)
        elif kind in ("pmid", "doi"):
            outcome = await _ingest_reference(ctx, http, source, kind)
        elif kind == "url":
            outcome = await _ingest_url(ctx, http, source, source.url or source.external_id)
        else:
            outcome = SeedOutcome(kind=kind, problems=["unknown seed reference"])
    except Exception as error:
        outcome = SeedOutcome(kind=kind, problems=[describe_error(error)])
    try:
        source = await _summarize(ctx, source.id, outcome)
    except Exception as error:
        outcome.problems.append(f"summary: {describe_error(error)}")
    await _verdict(ctx, source, outcome)
    return outcome


async def _verdict(ctx: StageContext, source: SourceRow, outcome: SeedOutcome) -> None:
    flagged = not outcome.chunks or bool(outcome.problems)
    if flagged:
        await ctx.emit(
            TraceEventKind.WARNING,
            f"Seed {source.title[:80]!r}: {'; '.join(outcome.problems) or 'no text'}",
            {"source_id": source.id, "problems": outcome.problems},
        )
    await record_verdict(
        ctx,
        source,
        outcome=VerdictOutcome.FLAGGED if flagged else VerdictOutcome.KEPT,
        confidence=1.0 if outcome.full_text and not outcome.problems else 0.5,
        summary=f"Seed {outcome.kind}: {outcome.chunks} chunks"
        + (f" ({'; '.join(outcome.problems)})" if outcome.problems else ""),
        response={
            "reason": "SEED_INGESTED" if not flagged else "SEED_PARTIAL",
            "kind": outcome.kind,
            "chunks": outcome.chunks,
            "full_text": outcome.full_text,
            "problems": outcome.problems,
        },
    )


async def run(ctx: StageContext) -> None:
    seeds = await ctx.repositories.list_sources(ctx.workspace_id, [SourceStatus.SEED])
    if not seeds:
        await ctx.emit(TraceEventKind.PROGRESS, "No seeds to ingest", {"seeds": 0})
        return
    total = len(seeds)
    await ctx.emit(TraceEventKind.PROGRESS, f"Ingesting {total} seeds", {"seeds": total})
    limit = asyncio.Semaphore(CONCURRENCY)
    done = 0
    chunks = 0

    async def one(http: httpx.AsyncClient, source: SourceRow) -> None:
        nonlocal done, chunks
        async with limit:
            outcome = await ingest_seed(ctx, http, source)
        done += 1
        chunks += outcome.chunks
        await ctx.emit(
            TraceEventKind.PROGRESS,
            f"Ingested {done}/{total} seeds ({chunks} chunks)",
            {"done": done, "total": total, "chunks": chunks},
        )

    async with http_client(ctx) as http:
        await asyncio.gather(*(one(http, source) for source in seeds))
