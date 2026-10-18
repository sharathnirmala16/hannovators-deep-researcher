"""Exact, version-scoped source excerpts for code API curation."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import HTTPRedirectHandler, Request, build_opener


def timestamp_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def manifest_entry(
    *,
    source_id: str,
    repo: str,
    tag: str,
    revision: str,
    source_path: str,
    raw_path: str,
    url: str,
    retrieved_at: str,
    payload: bytes,
) -> dict[str, Any]:
    return {
        "sourceRecordId": source_id,
        "repo": repo,
        "tag": tag,
        "upstreamRevision": revision,
        "path": source_path,
        "url": url,
        "rawUrl": f"https://raw.githubusercontent.com/{repo}/{revision}/{source_path}",
        "retrievedAt": retrieved_at,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "rawPath": raw_path,
    }


def release_section_excerpt(source: str, version: str, needle: str) -> str:
    """Return the exact changelog heading through its answer-bearing entry."""
    lines = source.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.strip() == f"Version {version}"]
    if len(starts) != 1:
        raise ValueError(f"expected one changelog heading for {version}")
    start = starts[0]
    end = next(
        (i for i in range(start + 1, len(lines)) if re.match(r"^Version\s+\S+", lines[i])),
        len(lines),
    )
    matches = [i for i in range(start, end) if needle in lines[i]]
    if len(matches) != 1:
        raise ValueError(f"expected one release entry matching {needle!r}")
    excerpt = "".join(lines[start : matches[0] + 1])
    if not excerpt.strip() or len(excerpt) > 8000 or excerpt not in source:
        raise ValueError(f"release section excerpt is invalid for {version}")
    return excerpt


def section_option_excerpt(source: str, heading: str, selector: str) -> str:
    """Return one complete RST section containing an exact example selector."""
    lines = source.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.strip() == heading]
    if len(starts) != 1:
        raise ValueError(f"expected one RST heading for {heading!r}")
    start = starts[0]
    if start + 1 >= len(lines):
        raise ValueError(f"RST heading lacks an underline for {heading!r}")
    underline = lines[start + 1].strip()
    if len(underline) < len(heading) or len(set(underline)) != 1:
        raise ValueError(f"RST heading underline is invalid for {heading!r}")
    marker = underline[0]
    end = len(lines)
    for index in range(start + 2, len(lines) - 1):
        candidate = lines[index].strip()
        candidate_underline = lines[index + 1].strip()
        if (
            candidate
            and len(candidate_underline) >= len(candidate)
            and candidate_underline
            and set(candidate_underline) == {marker}
        ):
            end = index
            break
    excerpt = "".join(lines[start:end])
    if source.count(selector) != 1 or selector not in excerpt:
        raise ValueError(f"expected one example selector in section {heading!r}")
    if not excerpt.strip() or len(excerpt) > 8000 or excerpt not in source:
        raise ValueError(f"RST section excerpt is invalid for {heading!r}")
    return excerpt


def long_option(excerpt: str) -> str:
    """Extract the first long-form Click option spelling from source text."""
    literal_values = re.findall(r"(['\"])(.*?)\1", excerpt)
    for _, literal in literal_values:
        if isinstance(literal, str) and literal.startswith("--"):
            return literal
    raise ValueError("Click option declaration has no long-form command-line spelling")


def click_command_default(
    source: str,
    command: str,
    option: str,
    parse_default: Callable[[str, str], tuple[str, Any]],
) -> tuple[str, str, Any]:
    """Extract a Click option default with its command declaration context."""
    lines = source.splitlines(keepends=True)
    function = re.compile(rf"^\s*def\s+{re.escape(command)}\s*\(")
    matches: list[tuple[str, str, Any]] = []
    for index, line in enumerate(lines):
        if not function.match(line):
            continue
        start = index
        while start > 0 and lines[start - 1].lstrip().startswith("@"):
            start -= 1
        decorators = lines[start:index]
        option_lines = [
            decorator
            for decorator in decorators
            if f"'{option}'" in decorator or f'"{option}"' in decorator
        ]
        if len(option_lines) != 1:
            continue
        answer, value = parse_default(option_lines[0], "default")
        excerpt = "".join(lines[start : index + 1])
        if len(excerpt) > 8000 or excerpt not in source:
            raise ValueError(f"Click command example excerpt is invalid for {command}")
        matches.append((answer, excerpt, value))
    if not matches:
        raise ValueError(f"Click command option not found for {command} {option}")
    first_match = matches[0]
    if any(match != first_match for match in matches[1:]):
        raise ValueError(f"Click command option is ambiguous for {command} {option}")
    return first_match


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def open_without_redirects(request: Request, *, timeout: float) -> Any:
    """Open one URL and surface redirects as HTTP errors without following them."""
    return build_opener(_RejectRedirects()).open(request, timeout=timeout)


def append_attempt_event(path: Path, event: dict[str, Any]) -> None:
    """Durably append one JSONL request-attempt event before or after I/O."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with path.open("ab") as output:
        output.write(payload + b"\n")
        output.flush()
        os.fsync(output.fileno())


def count_started_attempts(path: Path) -> int:
    """Count durable starts; malformed logs fail closed rather than reset budget."""
    if not path.exists():
        return 0
    count = 0
    with path.open("rb") as source:
        for raw_line in source:
            try:
                row = json.loads(raw_line.decode("utf-8", errors="strict"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("request attempt ledger is malformed") from error
            if not isinstance(row, dict):
                raise ValueError("request attempt ledger row must be an object")
            if row.get("event") == "started":
                if not all(
                    isinstance(row.get(field), str) and row[field]
                    for field in (
                        "attemptId",
                        "sourceRecordId",
                        "rawURL",
                        "startedAtUTC",
                    )
                ):
                    raise ValueError("request attempt ledger start is incomplete")
                count += 1
            elif row.get("event") == "finished":
                if not all(
                    isinstance(row.get(field), str) and row[field]
                    for field in ("attemptId", "outcome", "finishedAtUTC")
                ):
                    raise ValueError("request attempt ledger completion is incomplete")
            else:
                raise ValueError("request attempt ledger has an unknown event")
    return count
