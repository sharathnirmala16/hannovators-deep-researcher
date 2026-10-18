"""Credential-safe path guards for the code API snapshot artifacts."""

from __future__ import annotations

import stat
from pathlib import Path, PurePosixPath

from query_gold.io import ensure_safe_path


def safe_relative_path(raw_path: str) -> PurePosixPath:
    """Validate artifact paths before touching any source cache file."""
    if not raw_path or "\x00" in raw_path or "\\" in raw_path:
        raise ValueError("rawPath must be a safe relative POSIX path")
    path = PurePosixPath(raw_path)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("rawPath must be a safe relative POSIX path")
    for part in path.parts:
        lowered = part.casefold()
        if lowered == ".env" or lowered.startswith(".env."):
            raise ValueError("credential paths are not permitted")
        if lowered in {".netrc", ".npmrc", ".pypirc", "credentials", "credentials.json"}:
            raise ValueError("credential paths are not permitted")
    return path


def guard_absolute_path(path: Path) -> Path:
    """Reject credential and symlink components before an artifact read/write."""
    return ensure_safe_path(path)


def safe_file(root: Path, raw_path: str, *, must_exist: bool) -> Path:
    relative = safe_relative_path(raw_path)
    root = guard_absolute_path(root)
    candidate = root.joinpath(*relative.parts)
    candidate = guard_absolute_path(candidate)
    if must_exist:
        mode = candidate.lstat().st_mode
        if not stat.S_ISREG(mode):
            raise ValueError("source cache path is not a regular file")
    return candidate
