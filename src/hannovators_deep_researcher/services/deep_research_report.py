"""The Tavily deep research report as one workspace source, so a researcher can include it.

`ensure_report_source()` is idempotent: it keys the source by `external_id`
`deep-research:<workspace_id>:<run started at>`, so each completed run has one report source and
calling it again returns the same source. The source is a RAW `WEB` source with search intent
DEEP_RESEARCH, a plain-text excerpt as its abstract (appraisal reads the abstract), the full
markdown as `snapshot.md` (the Document view renders it), FULLTEXT chunks with embeddings (chat
retrieval can cite it once it is included, and acquire skips it), `extra_json.kind =
"deep_research_report"` with the cited URLs, and RELATED links to the cited sources.
"""

import json
import logging
import re
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from hannovators_deep_researcher.models.contracts import WorkspaceSettings
from hannovators_deep_researcher.models.deep_research import DeepResearchRecord
from hannovators_deep_researcher.models.enums import (
    SearchIntent,
    SourceLinkKind,
    SourceOrigin,
    SourceStatus,
)
from hannovators_deep_researcher.persistence.queries.acquire import (
    add_links,
    source_id_by_external_id,
)
from hannovators_deep_researcher.persistence.tables import SourceRow, WorkspaceRow
from hannovators_deep_researcher.services.documents.files import (
    SNAPSHOT_MD,
    source_path,
    write_bytes,
)
from hannovators_deep_researcher.services.evidence import heuristic_level
from hannovators_deep_researcher.services.pipeline.context import PipelineServices
from hannovators_deep_researcher.services.pipeline.stages.acquire.fulltext import index_markdown

logger = logging.getLogger(__name__)

REPORT_KIND = "deep_research_report"
FOUND_BY = "tavily_research"
VENUE = "Tavily deep research"
TITLE_PREFIX = "Deep research report"
TITLE_CHARS = 200
ABSTRACT_CHARS = 2_000

_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_RULE = re.compile(r"^\s*(?:[-*_]\s*){3,}$")
_TABLE_DIVIDER = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")
_MARKS = re.compile(r"\*\*|__|`|^\s*#{1,6}\s+|^\s*>\s?|^\s*[-*+]\s+", re.MULTILINE)


def report_external_id(workspace_id: str, record: DeepResearchRecord) -> str:
    """Stable per run: the same record always maps to the same source."""

    started = record.started_at or record.finished_at
    run = started.strftime("%Y%m%dT%H%M%S") if started else "report"
    return f"deep-research:{workspace_id}:{run}"


def plain_excerpt(markdown: str, limit: int = ABSTRACT_CHARS) -> str:
    """Markdown as plain prose: no images, link targets, rules, table dividers, or marks."""

    lines = []
    for line in _IMAGE.sub("", markdown).splitlines():
        if _RULE.match(line) or _TABLE_DIVIDER.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        lines.append("; ".join(cell for cell in cells if cell) if "|" in line else line)
    text = " ".join(_MARKS.sub("", _LINK.sub(r"\1", "\n".join(lines))).split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return f"{cut}..."


def report_markdown(record: DeepResearchRecord) -> str:
    """The report, plus a numbered source list when the report does not already link them."""

    content = record.content.strip()
    sources = [source for source in record.sources if source.url]
    if not sources or any(source.url in content for source in sources):
        return content
    lines = [f"{n}. [{s.title or s.url}]({s.url})" for n, s in enumerate(sources, start=1)]
    return f"{content}\n\n## Sources\n\n" + "\n".join(lines)


def _title(workspace: WorkspaceRow) -> str:
    question = " ".join(workspace.research_question.split())
    return f"{TITLE_PREFIX}: {question}"[:TITLE_CHARS]


async def _create(
    services: PipelineServices,
    workspace: WorkspaceRow,
    record: DeepResearchRecord,
    root: Path | None,
) -> SourceRow:
    markdown = report_markdown(record)
    abstract = plain_excerpt(markdown)
    title = _title(workspace)
    cited = [source.url for source in record.sources if source.url]
    finished = record.finished_at or record.started_at
    row = await services.repositories.create_source(
        workspace.id,
        origin=SourceOrigin.WEB,
        external_id=report_external_id(workspace.id, record),
        title=title,
        status=SourceStatus.RAW,
        abstract=abstract,
        venue=VENUE,
        year=finished.year if finished else None,
        search_intent=SearchIntent.DEEP_RESEARCH,
        evidence_level=heuristic_level(
            title=title, abstract=abstract, origin=SourceOrigin.WEB
        ).level,
        extra_json=json.dumps({"found_by": FOUND_BY, "kind": REPORT_KIND, "cited_urls": cited}),
    )
    relative = source_path(workspace.id, row.id, SNAPSHOT_MD)
    write_bytes(relative, markdown.encode("utf-8"), root=root)
    return await services.repositories.update_source_fields(row.id, raw_path=relative)


async def ensure_report_source(
    services: PipelineServices,
    workspace: WorkspaceRow,
    record: DeepResearchRecord,
    *,
    root: Path | None = None,
) -> DeepResearchRecord:
    """Create the report source of a completed record once; return the record with its id."""

    if record.status != "completed" or not record.content.strip():
        return record
    if record.report_source_id and await services.repositories.get_source(record.report_source_id):
        return record
    external_id = report_external_id(workspace.id, record)
    source_id = await source_id_by_external_id(services.repositories, workspace.id, external_id)
    if source_id is None:
        try:
            row = await _create(services, workspace, record, root)
        except IntegrityError:
            # Another request created it at the same time.
            source_id = await source_id_by_external_id(
                services.repositories, workspace.id, external_id
            )
        else:
            source_id = row.id
            await _index_and_link(services, workspace, record, row)
    return record.model_copy(update={"report_source_id": source_id})


async def _index_and_link(
    services: PipelineServices, workspace: WorkspaceRow, record: DeepResearchRecord, row: SourceRow
) -> None:
    dimensions = WorkspaceSettings.model_validate_json(workspace.settings_json)
    try:
        await index_markdown(
            services, row, report_markdown(record), dimensions.embedding_dimensions
        )
    except Exception:
        logger.exception("Indexing the deep research report failed for %s", workspace.id)
    cited = {source.source_id for source in record.sources if source.source_id}
    await add_links(
        services.repositories,
        workspace.id,
        [(row.id, target, SourceLinkKind.RELATED) for target in sorted(cited)],
    )
