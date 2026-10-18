"""Safe JSON/JSONL serialization and atomic local artifact writes."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from query_gold.paths import check_portable_path_component


def _assert_not_credential_path(path: Path) -> None:
    """Reject credential-like paths before any filesystem operation."""
    # Inspect the caller's lexical spelling first: Windows path normalization can
    # erase a trailing dot before the absolute path is inspected.
    for part in path.parts:
        if part != path.anchor and part not in {".", ".."}:
            check_portable_path_component(part)
        lowered = part.casefold()
        if lowered == ".env" or lowered.startswith(".env."):
            raise ValueError("Refusing to access a credential path")
        if lowered in {
            ".netrc",
            ".npmrc",
            ".pypirc",
            "credentials",
            "credentials.json",
            "id_ed25519",
            "id_rsa",
            "secrets.json",
        }:
            raise ValueError("Refusing to access a credential path")

    absolute = Path(os.path.abspath(path))
    for part in absolute.parts:
        if part != absolute.anchor:
            check_portable_path_component(part)
        lowered = part.casefold()
        if lowered == ".env" or lowered.startswith(".env."):
            raise ValueError("Refusing to access a credential path")
        if lowered in {
            ".netrc",
            ".npmrc",
            ".pypirc",
            "credentials",
            "credentials.json",
            "id_ed25519",
            "id_rsa",
            "secrets.json",
        }:
            raise ValueError("Refusing to access a credential path")


def _assert_no_symlinks(path: Path, *, require_existing: bool) -> Path:
    """Return an absolute path after rejecting symlink components without following them."""
    absolute = Path(os.path.abspath(path))
    parts = absolute.parts
    cursor = Path(parts[0]) if parts else absolute
    for index, part in enumerate(parts[1:], start=1):
        cursor = cursor / part
        try:
            component_stat = cursor.lstat()
        except FileNotFoundError:
            if require_existing:
                raise
            continue
        mode = component_stat.st_mode
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        is_reparse_point = bool(getattr(component_stat, "st_file_attributes", 0) & reparse_flag)
        if stat.S_ISLNK(mode) or is_reparse_point:
            raise ValueError("Refusing to follow symlink or reparse-point artifact paths")
        if index < len(parts) - 1 and not stat.S_ISDIR(mode):
            raise ValueError("Artifact path contains a non-directory component")
    return absolute


def ensure_safe_path(path: Path, *, require_existing: bool = False) -> Path:
    """Validate an artifact path before the caller creates, stats, or reads it."""
    _assert_not_credential_path(path)
    return _assert_no_symlinks(path, require_existing=require_existing)


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def json_bytes(value: Any, *, pretty: bool = False) -> bytes:
    """Encode strict JSON; non-finite floats are rejected."""
    if pretty:
        content = json.dumps(
            value,
            default=_json_default,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
    else:
        content = json.dumps(
            value,
            default=_json_default,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return (content + "\n").encode("utf-8")


def jsonl_bytes(rows: list[Any]) -> bytes:
    """Encode stable newline-delimited JSON records."""
    return b"".join(json_bytes(row) for row in rows)


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON constant {value} is not allowed")


def read_json(path: Path) -> Any:
    """Read one JSON document after guarding its lexical path."""
    _assert_not_credential_path(path)
    _assert_no_symlinks(path, require_existing=True)
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except UnicodeDecodeError as error:
        raise ValueError(f"JSON file is not UTF-8: {path.name}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path.name} at line {error.lineno}") from error


def read_jsonl(path: Path) -> list[Any]:
    """Read strict UTF-8 JSONL without including source content in errors."""
    _assert_not_credential_path(path)
    _assert_no_symlinks(path, require_existing=True)
    rows: list[Any] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    raise ValueError(f"Blank JSONL record in {path.name} at line {line_number}")
                try:
                    rows.append(json.loads(line, parse_constant=_reject_json_constant))
                except (json.JSONDecodeError, ValueError) as error:
                    raise ValueError(
                        f"Invalid JSONL record in {path.name} at line {line_number}"
                    ) from error
    except UnicodeDecodeError as error:
        raise ValueError(f"JSONL file is not UTF-8: {path.name}") from error
    return rows


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Atomically replace one artifact after fully writing a sibling temp file."""
    _assert_not_credential_path(path)
    _assert_no_symlinks(path, require_existing=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_symlinks(path, require_existing=False)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name[:16]}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_many(files: dict[Path, bytes]) -> None:
    """Stage a small related file set and roll back replacements if a commit fails."""
    staged: dict[Path, Path] = {}
    backups: dict[Path, bytes | None] = {}
    committed: list[Path] = []
    try:
        for path, content in files.items():
            _assert_not_credential_path(path)
            _assert_no_symlinks(path, require_existing=False)
            path.parent.mkdir(parents=True, exist_ok=True)
            _assert_no_symlinks(path, require_existing=False)
            try:
                backups[path] = path.read_bytes()
            except FileNotFoundError:
                backups[path] = None
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name[:16]}.", suffix=".tmp", dir=path.parent
            )
            temporary = Path(temporary_name)
            staged[path] = temporary
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())

        for path, temporary in staged.items():
            os.replace(temporary, path)
            committed.append(path)
    except BaseException:
        for path in reversed(committed):
            previous = backups[path]
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write_bytes(path, previous)
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)


def atomic_write_json(path: Path, value: Any, *, pretty: bool = True) -> None:
    atomic_write_bytes(path, json_bytes(value, pretty=pretty))


def atomic_write_jsonl(path: Path, rows: list[Any]) -> None:
    atomic_write_bytes(path, jsonl_bytes(rows))


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    _assert_not_credential_path(path)
    _assert_no_symlinks(path, require_existing=True)
    return sha256_bytes(path.read_bytes())


def read_text(path: Path) -> str:
    """Read a UTF-8 text artifact without following symlinks."""
    _assert_not_credential_path(path)
    _assert_no_symlinks(path, require_existing=True)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"Text file is not UTF-8: {path.name}") from error
