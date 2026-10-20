"""Safe workspace file paths and streaming downloads (PLAN.md section 4.1).

The database stores paths relative to `data/` with `/` separators, for example
`workspaces/<workspace_id>/sources/<source_id>/raw.pdf`. This module is the only place that turns
such a relative path into an absolute path. It rejects absolute paths, drive letters, `..`, and
any path outside `data/workspaces/`.
"""

import re
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

import httpx

from hannovators_deep_researcher.configuration.database import project_root

WORKSPACES_DIR = "workspaces"
SOURCES_DIR = "sources"
RAW_PDF = "raw.pdf"
SNAPSHOT_MD = "snapshot.md"
HIGHLIGHTED_PDF = "highlighted.pdf"

PDF_CONTENT_TYPES = frozenset({"application/pdf", "application/x-pdf"})
DEFAULT_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024

_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class UnsafePathError(ValueError):
    """A relative data path is absolute, escapes its root, or is outside `data/workspaces/`."""


class DownloadError(Exception):
    """A download failed: transport error, HTTP error, wrong content type, or too large."""


class UnsupportedContentTypeError(DownloadError):
    """The response content type is not in the allowed set."""


class DownloadTooLargeError(DownloadError):
    """The response is larger than the size cap. No file is kept."""


@dataclass(frozen=True, slots=True)
class DownloadResult:
    relative_path: str
    content_type: str
    size_bytes: int


_configured_root: Path | None = None


def configure_data_root(root: Path | None) -> None:
    """Point `data_root()` at another folder that holds `workspaces/` (None: the default).

    The composition root calls this once per app, so the API, the pipeline stages, and chat
    read and write the same files (tests use a temporary folder).
    """

    global _configured_root
    _configured_root = root


def data_root() -> Path:
    """Return the root `data/` directory (the repository's, unless configured otherwise)."""

    return _configured_root or project_root() / "data"


def validate_relative_path(relative_path: str) -> PurePosixPath:
    """Check a stored POSIX path relative to `data/` and return it as a pure path.

    The path must start with `workspaces/` and name something below it.
    """

    if not relative_path or "\x00" in relative_path or "\\" in relative_path:
        raise UnsafePathError(f"unsafe data path: {relative_path!r}")
    if relative_path.startswith("/") or _DRIVE_PREFIX.match(relative_path):
        raise UnsafePathError(f"data path must be relative: {relative_path!r}")
    if PureWindowsPath(relative_path).anchor:
        raise UnsafePathError(f"data path must be relative: {relative_path!r}")
    parts = relative_path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise UnsafePathError(f"data path has an empty, '.', or '..' segment: {relative_path!r}")
    if len(parts) < 2 or parts[0] != WORKSPACES_DIR:
        raise UnsafePathError(f"data path is outside {WORKSPACES_DIR}/: {relative_path!r}")
    return PurePosixPath(relative_path)


def resolve_data_path(relative_path: str, *, root: Path | None = None) -> Path:
    """Turn a stored relative path into an absolute path under `<root>/workspaces/`.

    The check runs again after `resolve()`, so a symbolic link cannot point outside the root.
    """

    pure = validate_relative_path(relative_path)
    base = (root or data_root()).resolve()
    resolved = base.joinpath(*pure.parts).resolve()
    if not resolved.is_relative_to(base / WORKSPACES_DIR):
        raise UnsafePathError(f"data path resolves outside {WORKSPACES_DIR}/: {relative_path!r}")
    return resolved


def source_path(workspace_id: str, source_id: str, filename: str) -> str:
    """Return the stored relative path of a file in a source folder."""

    for value in (workspace_id, source_id):
        if not _SAFE_ID.match(value):
            raise UnsafePathError(f"unsafe identifier: {value!r}")
    if not _SAFE_FILENAME.match(filename):
        raise UnsafePathError(f"unsafe file name: {filename!r}")
    return f"{WORKSPACES_DIR}/{workspace_id}/{SOURCES_DIR}/{source_id}/{filename}"


def write_bytes(relative_path: str, data: bytes, *, root: Path | None = None) -> Path:
    """Write a file at a stored relative path, creating its folders. Return the absolute path."""

    destination = resolve_data_path(relative_path, root=root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    partial.write_bytes(data)
    partial.replace(destination)
    return destination


async def download(
    client: httpx.AsyncClient,
    url: str,
    relative_path: str,
    *,
    allowed_content_types: Collection[str] = PDF_CONTENT_TYPES,
    max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    root: Path | None = None,
) -> DownloadResult:
    """Stream `url` to a stored relative path with a content-type check and a size cap.

    The body goes to a `.part` file first. On any failure the partial file is removed and the
    destination is not changed.
    """

    destination = resolve_data_path(relative_path, root=root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    try:
        content_type, size = await _stream_to_file(
            client, url, partial, frozenset(allowed_content_types), max_bytes
        )
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(destination)
    return DownloadResult(relative_path=relative_path, content_type=content_type, size_bytes=size)


async def _stream_to_file(
    client: httpx.AsyncClient,
    url: str,
    partial: Path,
    allowed_content_types: frozenset[str],
    max_bytes: int,
) -> tuple[str, int]:
    try:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = _media_type(response.headers.get("content-type"))
            if content_type not in allowed_content_types:
                raise UnsupportedContentTypeError(
                    f"content type {content_type or 'missing'!r} is not allowed for {url}"
                )
            declared = response.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > max_bytes:
                raise DownloadTooLargeError(f"{url} declares {declared} bytes > {max_bytes}")
            size = 0
            with partial.open("wb") as handle:
                async for block in response.aiter_bytes():
                    size += len(block)
                    if size > max_bytes:
                        raise DownloadTooLargeError(f"{url} is larger than {max_bytes} bytes")
                    handle.write(block)
    except httpx.HTTPError as error:
        raise DownloadError(f"download failed for {url}: {error}") from error
    return content_type, size


def _media_type(header: str | None) -> str:
    return (header or "").split(";", 1)[0].strip().lower()
