"""Seed uploads (PLAN.md section 5.3): multipart `files` (PDFs) or JSON `SeedReferenceRequest`.

PDFs are saved at `data/workspaces/<ws>/sources/<source_id>/raw.pdf` as SEED sources whose
`external_id` is the file's SHA-256 (the same file twice gives one source). References become
SEED sources keyed by PMID, DOI, or canonical URL; the `ingest` stage resolves them in the run.
"""

from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from hannovators_deep_researcher.models.contracts import SeedReferenceRequest, SourceView
from hannovators_deep_researcher.persistence.tables import SourceRow
from hannovators_deep_researcher.routers.dependencies import Container
from hannovators_deep_researcher.routers.errors import api_error
from hannovators_deep_researcher.services.trajectory_wrappers import record_user_action
from hannovators_deep_researcher.services.workspace_state import source_view

router = APIRouter(prefix="/workspaces", tags=["seeds"])

MAX_SEED_BYTES = 50 * 1024 * 1024
MAX_SEED_FILES = 20
PDF_MAGIC = b"%PDF-"
FILES_FIELD = "files"

_OPENAPI: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "properties": {
                        FILES_FIELD: {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                        }
                    },
                    "required": [FILES_FIELD],
                }
            },
            "application/json": {"schema": {"$ref": "#/components/schemas/SeedReferenceRequest"}},
        },
    }
}


async def _read_pdfs(request: Request) -> list[tuple[str, bytes]]:
    """Read and check every uploaded file before anything is stored."""

    form = await request.form(max_files=MAX_SEED_FILES)
    uploads = [item for item in form.getlist(FILES_FIELD) if isinstance(item, UploadFile)]
    if not uploads:
        raise api_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "NO_FILES",
            f"Send one or more PDFs in the multipart field '{FILES_FIELD}'.",
        )
    files: list[tuple[str, bytes]] = []
    for upload in uploads:
        name = upload.filename or "upload.pdf"
        data = await upload.read(MAX_SEED_BYTES + 1)
        await upload.close()
        if len(data) > MAX_SEED_BYTES:
            raise api_error(
                status.HTTP_413_CONTENT_TOO_LARGE,
                "SEED_TOO_LARGE",
                f"{name} is larger than {MAX_SEED_BYTES // (1024 * 1024)} MB.",
            )
        if not data.startswith(PDF_MAGIC):
            raise api_error(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "UNSUPPORTED_MEDIA_TYPE",
                f"{name} is not a PDF.",
            )
        files.append((name, data))
    return files


async def _add_pdfs(
    container: Container, workspace_id: str, request: Request
) -> tuple[list[SourceRow], dict[str, object]]:
    rows: list[SourceRow] = []
    listed: list[dict[str, object]] = []
    for name, data in await _read_pdfs(request):
        try:
            row = await container.state.add_pdf_seed(workspace_id, filename=name, data=data)
        except ValueError as error:
            raise api_error(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "UNSUPPORTED_MEDIA_TYPE", f"{name}: {error}"
            ) from error
        rows.append(row)
        listed.append(
            {"filename": name, "size_bytes": len(data), "source_id": row.id, "title": row.title}
        )
    return rows, {"kind": "pdf", "files": listed}


async def _add_reference(
    container: Container, workspace_id: str, request: Request
) -> tuple[list[SourceRow], dict[str, object]]:
    try:
        body = SeedReferenceRequest.model_validate(await request.json())
    except ValueError as error:
        errors: list[Any] = list(error.errors()) if isinstance(error, ValidationError) else []
        invalid = {"loc": ("body",), "msg": "invalid JSON body", "type": "json_invalid"}
        raise RequestValidationError(errors or [invalid]) from error
    row = await container.state.add_reference_seed(workspace_id, body)
    return [row], {"kind": "reference", **body.model_dump(mode="json", exclude_none=True)}


@router.post("/{workspace_id}/seeds", status_code=status.HTTP_201_CREATED, openapi_extra=_OPENAPI)
async def add_seeds(workspace_id: str, request: Request, container: Container) -> list[SourceView]:
    """Add seed PDFs (multipart `files`) or one PMID/DOI/URL (JSON) as SEED sources."""

    await container.state.require_workspace(workspace_id)
    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("multipart/form-data"):
        rows, details = await _add_pdfs(container, workspace_id, request)
    elif content_type.startswith("application/json"):
        rows, details = await _add_reference(container, workspace_id, request)
    else:
        raise api_error(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "UNSUPPORTED_MEDIA_TYPE",
            "Send multipart/form-data with PDF files or a JSON pmid/doi/url body.",
        )
    await record_user_action(
        container.services.trajectory,
        workspace_id,
        "user.seed.upload",
        summary=f"Added {len(rows)} seed(s): " + "; ".join(row.title[:60] for row in rows),
        request=details,
        source_ids=[row.id for row in rows],
    )
    return [source_view(row) for row in rows]
