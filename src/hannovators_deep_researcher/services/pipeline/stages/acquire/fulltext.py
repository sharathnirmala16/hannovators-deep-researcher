"""Full-text helpers shared by `ingest` and `acquire`: download PDFs, snapshot web pages, index.

Every PDF download goes through `trajectory_wrappers.record_download` (one DOWNLOAD step), and
every web snapshot is one DOWNLOAD step that parents the web port's FETCH step. Indexing chunks
the document (PDF: ABSTRACT + FULLTEXT tiers with page and bbox; markdown: FULLTEXT) and stores
document embeddings.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx

from hannovators_deep_researcher.configuration.settings import ProviderMode
from hannovators_deep_researcher.infrastructure.http import create_http_client
from hannovators_deep_researcher.models.enums import (
    ChunkTier,
    SourceOrigin,
    TrajectoryKind,
    VerdictOutcome,
)
from hannovators_deep_researcher.models.literature import CandidateRecord
from hannovators_deep_researcher.persistence.tables import SourceRow
from hannovators_deep_researcher.services.documents.files import (
    PDF_CONTENT_TYPES,
    RAW_PDF,
    SNAPSHOT_MD,
    DownloadError,
    resolve_data_path,
    source_path,
    write_bytes,
)
from hannovators_deep_researcher.services.documents.markdown_chunker import chunk_markdown
from hannovators_deep_researcher.services.documents.pdf_chunker import PdfChunkResult, chunk_pdf
from hannovators_deep_researcher.services.pipeline.context import PipelineServices, StageContext
from hannovators_deep_researcher.services.retrieval.indexing import (
    ChunkDraft,
    IndexResult,
    abstract_draft,
    markdown_drafts,
    pdf_drafts,
    store_chunks,
)
from hannovators_deep_researcher.services.trajectory_wrappers import record_download

MAX_PDF_BYTES = 40 * 1024 * 1024
SNAPSHOT_MAX_CHARS = 120_000
DOWNLOAD_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
_PDF_TYPES = PDF_CONTENT_TYPES | {"application/octet-stream", "binary/octet-stream"}
_PDF_MAGIC = b"%PDF"


class NoTextLayerError(Exception):
    """The PDF has no text layer (a scan), so it cannot be chunked or highlighted."""


@asynccontextmanager
async def http_client(services: PipelineServices) -> AsyncIterator[httpx.AsyncClient]:
    """A download client. Fake mode serves the bundled PDF and never touches the network."""

    if services.app_settings.provider_mode is ProviderMode.FAKE:
        from hannovators_deep_researcher.adapters.fake.literature import fake_http_transport

        client = httpx.AsyncClient(transport=fake_http_transport(), follow_redirects=True)
    else:
        client = create_http_client(timeout=DOWNLOAD_TIMEOUT)
    async with client:
        yield client


def source_extra(source: SourceRow) -> dict[str, object]:
    if not source.extra_json:
        return {}
    try:
        value = json.loads(source.extra_json)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def merged_extra(source: SourceRow, updates: Mapping[str, object]) -> str:
    return json.dumps({**source_extra(source), **updates})


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def candidate_record(source: SourceRow) -> CandidateRecord:
    """The literature record view of a source, for `open_access_pdf_url`."""

    extra = source_extra(source)
    external = source.external_id
    pmid = _text(extra.get("pmid")) or (external if external.isdigit() else None)
    doi = _text(extra.get("doi")) or (external if external.startswith("10.") else None)
    return CandidateRecord(
        origin=SourceOrigin(source.origin),
        external_id=external,
        title=source.title,
        abstract=source.abstract,
        doi=doi,
        pmid=pmid,
        pmcid=_text(extra.get("pmcid")),
        url=source.url,
        pdf_url=source.pdf_url,
    )


async def download_pdf(
    services: PipelineServices,
    http: httpx.AsyncClient,
    *,
    workspace_id: str,
    source_id: str,
    url: str,
) -> str:
    """Download `url` to the source's `raw.pdf` and return the stored relative path."""

    relative = source_path(workspace_id, source_id, RAW_PDF)
    # The orchestrator binds the workspace and stage, so the DOWNLOAD step lands in the run.
    result = await record_download(
        services.trajectory,
        http,
        url,
        relative,
        source_ids=[source_id],
        allowed_content_types=_PDF_TYPES,
        max_bytes=MAX_PDF_BYTES,
        name="download.pdf",
    )
    path = resolve_data_path(relative)
    with path.open("rb") as handle:
        magic = handle.read(len(_PDF_MAGIC))
    if magic != _PDF_MAGIC:
        path.unlink(missing_ok=True)
        raise DownloadError(f"{url} did not return a PDF ({result.content_type})")
    return relative


async def fetch_snapshot(
    services: PipelineServices, *, workspace_id: str, source_id: str, url: str
) -> tuple[str, str, str | None]:
    """Fetch a web page as markdown into `snapshot.md`. Returns (path, markdown, title)."""

    relative = source_path(workspace_id, source_id, SNAPSHOT_MD)
    async with services.trajectory.step(
        kind=TrajectoryKind.DOWNLOAD,
        name="download.snapshot",
        workspace_id=workspace_id,
        target=url,
        summary=f"Snapshot {url}",
        request={"url": url, "max_chars": SNAPSHOT_MAX_CHARS, "relative_path": relative},
        source_ids=[source_id],
    ) as step:
        document = await services.web.fetch(url, max_chars=SNAPSHOT_MAX_CHARS)
        if not document.content.strip():
            raise DownloadError(f"{url} returned an empty page")
        data = document.content.encode("utf-8")
        write_bytes(relative, data)
        step.response = {
            "relative_path": relative,
            "content_type": "text/markdown",
            "size_bytes": len(data),
            "chars": len(document.content),
            "provider": document.provider,
            "title": document.title,
        }
        step.summary = f"{len(data)} bytes snapshot via {document.provider}"
    return relative, document.content, document.title


@dataclass(frozen=True, slots=True)
class PdfIndex:
    index: IndexResult
    chunks: PdfChunkResult


async def index_pdf(
    services: PipelineServices,
    source: SourceRow,
    relative_path: str,
    dimensions: int,
    *,
    abstract: str | None = None,
) -> PdfIndex:
    """Chunk and embed a stored PDF. A PDF without a text layer raises `NoTextLayerError`."""

    result = await asyncio.to_thread(chunk_pdf, resolve_data_path(relative_path))
    if not result.has_text_layer or not result.chunks:
        raise NoTextLayerError(f"{relative_path} has no text layer")
    drafts = pdf_drafts(result)
    if not any(draft.tier == ChunkTier.ABSTRACT for draft in drafts):
        drafts = abstract_draft(abstract or source.abstract) + drafts
    index = await store_chunks(
        services,
        workspace_id=source.workspace_id,
        source_id=source.id,
        title=source.title,
        drafts=drafts,
        dimensions=dimensions,
    )
    return PdfIndex(index=index, chunks=result)


async def index_markdown(
    services: PipelineServices, source: SourceRow, markdown: str, dimensions: int
) -> IndexResult:
    drafts: list[ChunkDraft] = abstract_draft(source.abstract) + markdown_drafts(
        chunk_markdown(markdown)
    )
    return await store_chunks(
        services,
        workspace_id=source.workspace_id,
        source_id=source.id,
        title=source.title,
        drafts=drafts,
        dimensions=dimensions,
    )


async def index_abstract(
    services: PipelineServices, source: SourceRow, dimensions: int
) -> IndexResult:
    return await store_chunks(
        services,
        workspace_id=source.workspace_id,
        source_id=source.id,
        title=source.title,
        drafts=abstract_draft(source.abstract),
        dimensions=dimensions,
    )


async def record_verdict(
    ctx: StageContext,
    source: SourceRow,
    *,
    outcome: VerdictOutcome,
    confidence: float,
    summary: str,
    response: Mapping[str, object],
) -> None:
    await ctx.trajectory.record(
        kind=TrajectoryKind.VERDICT,
        name=f"{ctx.stage}.verdict",
        target=source.url or source.external_id,
        summary=summary,
        source_ids=[source.id],
        outcome=outcome,
        confidence=confidence,
        response=dict(response),
    )


def describe_error(error: BaseException) -> str:
    message = str(error) or type(error).__name__
    failure_error = getattr(error, "error", None)
    if failure_error is not None and hasattr(failure_error, "message"):
        message = f"{failure_error.code}: {failure_error.message}"
    return f"{type(error).__name__}: {message}"[:500]
