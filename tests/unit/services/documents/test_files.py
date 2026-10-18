"""Edge cases for safe data paths and the capped streaming download."""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx

from hannovators_deep_researcher.services.documents.files import (
    RAW_PDF,
    DownloadTooLargeError,
    UnsafePathError,
    download,
    resolve_data_path,
    source_path,
)

PDF_URL = "https://example.org/paper.pdf"
MAX_BYTES = 1024


@pytest.mark.unit
@pytest.mark.parametrize(
    "relative_path",
    [
        "",
        "../secrets.env",
        "workspaces/../../etc/passwd",
        "workspaces/ws/sources/../../../outside.pdf",
        "workspaces/./ws/raw.pdf",
        "/etc/passwd",
        "//server/share/raw.pdf",
        "C:/Windows/win.ini",
        "c:relative.pdf",
        "workspaces\\ws\\..\\..\\raw.pdf",
        "seeds/ws/raw.pdf",
        "hannovators.db",
        "workspaces",
    ],
)
def test_unsafe_paths_are_rejected(relative_path: str, tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        resolve_data_path(relative_path, root=tmp_path)


async def _chunks(body: bytes, size: int = 256) -> AsyncIterator[bytes]:
    for start in range(0, len(body), size):
        yield body[start : start + size]


@pytest.mark.unit
@pytest.mark.parametrize("declares_length", [True, False], ids=["content-length", "streamed"])
async def test_download_over_size_cap_aborts_and_keeps_no_file(
    declares_length: bool, tmp_path: Path
) -> None:
    body = b"%PDF-1.7\n" + b"0" * (MAX_BYTES * 2)
    content: bytes | AsyncIterator[bytes] = body if declares_length else _chunks(body)
    relative_path = source_path("ws1", "src1", RAW_PDF)

    with respx.mock:
        respx.get(PDF_URL).mock(
            return_value=httpx.Response(
                200, headers={"content-type": "application/pdf"}, content=content
            )
        )
        async with httpx.AsyncClient() as client:
            with pytest.raises(DownloadTooLargeError):
                await download(client, PDF_URL, relative_path, max_bytes=MAX_BYTES, root=tmp_path)

    source_dir = resolve_data_path(relative_path, root=tmp_path).parent
    assert list(source_dir.iterdir()) == []
