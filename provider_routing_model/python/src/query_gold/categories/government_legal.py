"""Curate direct-searchable federal rule and statute facts from official sources."""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar
from urllib.parse import urljoin, urlsplit

import httpx

from query_gold.categories.government_legal_facts import (
    COURT_FACTS,
    FEDERAL_FACTS,
    LAWS,
    STATUTE_FACTS,
    CourtFactSpec,
    FederalFactSpec,
    LawSource,
    StatuteFactSpec,
)
from query_gold.categories.government_legal_sources import sources_markdown as _sources_markdown
from query_gold.io import (
    atomic_write_bytes,
    atomic_write_jsonl,
    ensure_safe_path,
    json_bytes,
    read_json,
    read_jsonl,
)
from query_gold.models import SCHEMA_VERSION, QueryGoldCase

CATEGORY_ID = "05_government_courts_legal"
GENERATOR_VERSION = "query-gold/v1"
MAX_PHYSICAL_REQUESTS = 150
MAX_ADDITIONAL_PHYSICAL_REQUESTS = 45
MAX_RETRIES = 1
MAX_SOURCE_BYTES = 10_000_000
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "query-gold-government-legal/1.0 (official public sources)"
LICENSE = "Public domain (U.S. Government work; 17 U.S.C. § 105)"
COURT_LICENSE = "Official public court record; reuse status not asserted"
SOURCE_FAMILY_RULE = "federal_register_rule_document"
SOURCE_FAMILY_STATUTE = "govinfo_public_law"
SOURCE_FAMILY_COURT = "washington_supreme_court_opinion_sheet"

_ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SECTION_MARKER = re.compile(r"(?m)^SEC\.\s+(\d{3,5})\.")
_RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5
_SENSITIVE_PARTS = {
    ".env",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "secrets.json",
}


def _utc_timestamp(path: Path) -> str:
    metadata_path = path.with_name(f"{path.name}.metadata.json")
    metadata = read_json(metadata_path)
    if not isinstance(metadata, dict):
        raise ValueError("source metadata must be a JSON object")
    retrieved = metadata.get("retrievedAtUTC")
    digest = metadata.get("rawSha256")
    if not isinstance(retrieved, str) or digest != _sha256(path.read_bytes()):
        raise ValueError("source metadata does not match cached source bytes")
    try:
        parsed = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("source metadata has an invalid retrieval timestamp") from error
    if parsed.tzinfo != UTC:
        raise ValueError("source retrieval timestamp must be UTC")
    return retrieved


def _safe_raw_path(output_dir: Path, relative: str) -> Path:
    """Resolve one constant relative path without following symlinks or credential paths."""
    posix = PurePosixPath(relative)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in posix.parts):
        raise ValueError("unsafe source cache path")
    if any(part.casefold() in _SENSITIVE_PARTS for part in posix.parts):
        raise ValueError("credential-like source cache path")
    candidate = ensure_safe_path(output_dir)
    for part in posix.parts:
        candidate = ensure_safe_path(candidate / part)
    return candidate


def _read_ledger(output_dir: Path) -> list[dict[str, Any]]:
    ledger_path = _safe_raw_path(output_dir, "raw/network-attempts.jsonl")
    if not ledger_path.exists():
        return []
    rows = read_jsonl(ledger_path)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("invalid source request ledger")
    return rows


def _append_ledger(output_dir: Path, rows: list[dict[str, Any]], entry: dict[str, Any]) -> None:
    rows.append(entry)
    ledger_path = _safe_raw_path(output_dir, "raw/network-attempts.jsonl")
    atomic_write_jsonl(ledger_path, rows)


def _metadata_path(output_dir: Path, raw_path: str) -> Path:
    return _safe_raw_path(output_dir, f"{raw_path}.metadata.json")


def _source_metadata(
    *, url: str, raw_bytes: bytes, retrieved_at: str, time_basis: str
) -> dict[str, str]:
    return {
        "url": url,
        "rawSha256": _sha256(raw_bytes),
        "retrievedAtUTC": retrieved_at,
        "retrievedAtBasis": time_basis,
    }


def _cached_source(
    output_dir: Path,
    raw_path: str,
    url: str,
    ledger: list[dict[str, Any]],
    require_metadata: bool,
) -> tuple[Path, bytes] | None:
    path = _safe_raw_path(output_dir, raw_path)
    if not path.is_file():
        return None
    content = path.read_bytes()
    content.decode("utf-8", errors="strict")
    if len(content) > MAX_SOURCE_BYTES:
        raise ValueError("cached source exceeds the per-file size limit")
    digest = _sha256(content)
    meta_path = _metadata_path(output_dir, raw_path)
    if meta_path.is_file():
        metadata = read_json(meta_path)
        if (
            not isinstance(metadata, dict)
            or metadata.get("url") != url
            or metadata.get("rawSha256") != digest
            or not isinstance(metadata.get("retrievedAtUTC"), str)
        ):
            raise ValueError("cached source metadata mismatch; refusing to repin bytes")
        return path, content

    matching_attempts = [
        entry
        for entry in ledger
        if entry.get("status") == 200
        and entry.get("url") == url
        and entry.get("responseSha256") == digest
        and isinstance(entry.get("startedAtUTC"), str)
    ]
    if matching_attempts:
        retrieved_at = matching_attempts[-1]["startedAtUTC"]
        metadata = _source_metadata(
            url=url,
            raw_bytes=content,
            retrieved_at=retrieved_at,
            time_basis="request_started_at_utc",
        )
        atomic_write_bytes(meta_path, json_bytes(metadata))
        return path, content
    if not require_metadata:
        return path, content
    return None


def _ensure_source(
    output_dir: Path,
    raw_path: str,
    url: str,
    *,
    run_state: dict[str, Any],
    require_metadata: bool = True,
) -> tuple[Path, bytes]:
    """Read a pinned cache or fetch that exact source with bounded retries and logging."""
    path = _safe_raw_path(output_dir, raw_path)
    ledger: list[dict[str, Any]] = run_state["ledger"]
    meta_path = _metadata_path(output_dir, raw_path)
    cached = _cached_source(output_dir, raw_path, url, ledger, require_metadata)
    if cached is not None:
        return cached

    if run_state["client"] is None:
        run_state["client"] = httpx.Client(
            timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=10.0),
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/html"},
        )
    client: httpx.Client = run_state["client"]
    source_host = urlsplit(url).hostname
    for attempt in range(MAX_RETRIES + 1):
        request_url = url
        for redirect_count in range(MAX_REDIRECTS + 1):
            if len(ledger) >= MAX_PHYSICAL_REQUESTS:
                raise RuntimeError("public source request limit reached")
            if len(ledger) >= MAX_ADDITIONAL_PHYSICAL_REQUESTS:
                raise RuntimeError("additional public source request limit reached")
            started = _now_utc()
            entry: dict[str, Any] = {
                "url": request_url,
                "attempt": attempt + 1,
                "startedAtUTC": started,
                "status": None,
                "responseBytes": None,
                "responseSha256": None,
                "errorType": None,
            }
            try:
                response = client.get(request_url)
                entry["status"] = response.status_code
                entry["responseBytes"] = len(response.content)
                entry["responseSha256"] = _sha256(response.content)
                location = response.headers.get("location")
                if response.status_code in _REDIRECT_STATUSES and location:
                    target_url = urljoin(request_url, location)
                    target = urlsplit(target_url)
                    entry["redirectTo"] = target_url
                    _append_ledger(output_dir, ledger, entry)
                    if target.scheme != "https" or target.hostname != source_host:
                        raise ValueError("official source redirected outside its HTTPS host")
                    if redirect_count >= MAX_REDIRECTS:
                        raise RuntimeError("official source exceeded the redirect limit")
                    request_url = target_url
                    continue
                _append_ledger(output_dir, ledger, entry)
                if response.status_code == 200:
                    if len(response.content) > MAX_SOURCE_BYTES:
                        raise ValueError("downloaded source exceeds the per-file size limit")
                    response.content.decode("utf-8", errors="strict")
                    atomic_write_bytes(path, response.content)
                    metadata = _source_metadata(
                        url=url,
                        raw_bytes=response.content,
                        retrieved_at=_now_utc(),
                        time_basis="response_received_at_utc",
                    )
                    atomic_write_bytes(meta_path, json_bytes(metadata))
                    return path, response.content
                if attempt < MAX_RETRIES and response.status_code in _RETRYABLE_STATUS:
                    break
                raise RuntimeError(f"official source request returned HTTP {response.status_code}")
            except httpx.RequestError as error:
                entry["errorType"] = type(error).__name__
                _append_ledger(output_dir, ledger, entry)
                if attempt < MAX_RETRIES:
                    break
                raise RuntimeError("official source request failed after one retry") from None
        else:
            raise RuntimeError("official source exceeded the redirect limit")
    raise RuntimeError("official source request failed")


def _now_utc() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value} is not allowed")


def _top_level_members(text: str) -> dict[str, tuple[Any, str]]:
    """Decode JSON values while retaining each exact top-level source substring."""
    decoder = json.JSONDecoder(parse_constant=_reject_json_constant)
    offset = _skip_space(text, 0)
    if offset >= len(text) or text[offset] != "{":
        raise ValueError("Federal Register source must be a JSON object")
    offset += 1
    members: dict[str, tuple[Any, str]] = {}
    while True:
        offset = _skip_space(text, offset)
        if offset >= len(text):
            raise ValueError("incomplete Federal Register JSON object")
        if text[offset] == "}":
            break
        key_start = offset
        key, key_end = decoder.raw_decode(text, offset)
        if not isinstance(key, str):
            raise ValueError("Federal Register JSON object key is not text")
        offset = _skip_space(text, key_end)
        if offset >= len(text) or text[offset] != ":":
            raise ValueError("invalid Federal Register JSON object member")
        value_start = _skip_space(text, offset + 1)
        value, value_end = decoder.raw_decode(text, value_start)
        if key in members:
            raise ValueError("duplicate Federal Register JSON member")
        members[key] = (value, text[key_start:value_end])
        offset = _skip_space(text, value_end)
        if offset < len(text) and text[offset] == ",":
            offset += 1
            continue
        if offset < len(text) and text[offset] == "}":
            break
        raise ValueError("invalid Federal Register JSON separator")
    return members


def _skip_space(text: str, offset: int) -> int:
    while offset < len(text) and text[offset] in " \t\r\n":
        offset += 1
    return offset


def _required_member(members: dict[str, tuple[Any, str]], key: str) -> tuple[Any, str]:
    try:
        return members[key]
    except KeyError as error:
        raise ValueError(f"Federal Register record is missing {key}") from error


def _iso_date(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _ISO_DAY.fullmatch(value):
        raise ValueError(f"{field} must be a source-supplied ISO calendar date")
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} is not a valid ISO date") from error
    return value


def _human_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


class _VisibleTextParser(html.parser.HTMLParser):
    """Collect readable text from a public HTML page."""

    _ignored: ClassVar[frozenset[str]] = frozenset({"script", "style", "template", "noscript"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in self._ignored:
            self.ignore_depth += 1
        elif tag in {"br", "div", "li", "p", "td", "th", "tr"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._ignored and self.ignore_depth:
            self.ignore_depth -= 1
        elif tag in {"div", "li", "p", "td", "th", "tr"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.ignore_depth:
            self.parts.append(data)


def _visible_html_text(raw_bytes: bytes) -> str:
    text = raw_bytes.decode("utf-8", errors="strict")
    parser = _VisibleTextParser()
    parser.feed(text)
    parser.close()
    return " ".join(" ".join(parser.parts).split())


def _literal_html_excerpt(
    raw_text: str,
    answer: str,
    *,
    required_phrase: str | None = None,
) -> str:
    """Return an exact source substring around an answer and its source context."""
    body_start = raw_text.casefold().find("<body")
    search_from = body_start if body_start >= 0 else 0
    while search_from < len(raw_text):
        answer_span = _normalized_span(raw_text[search_from:], answer)
        if answer_span is None:
            break
        found = search_from + answer_span[0]
        answer_end = search_from + answer_span[1]
        start = max(0, found - 400)
        end = min(len(raw_text), answer_end + 1_200)
        excerpt = raw_text[start:end]
        visible = _visible_html_text(excerpt.encode("utf-8"))
        if required_phrase is None or _normalized(required_phrase) in _normalized(visible):
            return excerpt
        search_from = answer_end
    raise ValueError("public HTML evidence does not contain a literal answer excerpt")


def _public_html_excerpt(
    raw_bytes: bytes,
    answer: str,
    *,
    title: str,
    support: str | None = None,
) -> str:
    visible = _visible_html_text(raw_bytes)
    # Long Federal Register headings differ in punctuation from API metadata.
    _require_in_source(title[:64], visible, "public document page title")
    _require_in_source(answer, visible, "public answer-bearing page")
    if support is not None:
        _require_in_source(support, visible, "public answer-bearing page context")
    raw_text = raw_bytes.decode("utf-8", errors="strict")
    return _literal_html_excerpt(raw_text, answer, required_phrase=support)


def _require_in_source(value: str, source_text: str, field: str) -> None:
    if _normalized(value) not in _normalized(source_text):
        raise ValueError(f"gold fact is not literally supported by source field {field}")


def _rule_context(
    spec: FederalFactSpec, members: dict[str, tuple[Any, str]]
) -> tuple[dict[str, Any], str, str, str, str]:
    record = {key: item[0] for key, item in members.items()}
    if record.get("document_number") != spec.document_number:
        raise ValueError("Federal Register document number mismatch")
    if record.get("type") != "Rule":
        raise ValueError("candidate is not a Federal Register rule")
    action = record.get("action")
    if not isinstance(action, str) or not action.strip():
        raise ValueError("Federal Register action is missing")
    action_lower = action.casefold()
    if "proposed rule" in action_lower and "final rule" not in action_lower:
        raise ValueError("proposed rules are not eligible for this source family")
    title = record.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Federal Register title is missing")
    publication_date = _iso_date(record.get("publication_date"), "publication_date")
    page_url = record.get("html_url")
    if not isinstance(page_url, str):
        raise ValueError("Federal Register public document URL is missing")
    parsed = urlsplit(page_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "www.federalregister.gov"
        or not parsed.path.startswith("/documents/")
        or "/api/" in parsed.path
    ):
        raise ValueError("Federal Register evidence must use the normal public document page")
    version = f"Federal Register Doc. No. {spec.document_number} (published {publication_date})"
    return record, title, publication_date, page_url, version


def _govinfo_fr_url(document_number: str, publication_date: str) -> str:
    """Return the GPO-hosted, answer-bearing HTML page for a Federal Register item."""
    publication_date = _iso_date(publication_date, "publication_date")
    return f"https://www.govinfo.gov/content/pkg/FR-{publication_date}/html/{document_number}.htm"


def _string_values(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Federal Register {field} must be a non-empty string list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Federal Register {field} contains an invalid identifier")
        result.append(item.strip())
    return result


def _cfr_part_value(value: Any, expected: str) -> tuple[str, int]:
    if not isinstance(value, list) or not value:
        raise ValueError("Federal Register CFR references are missing")
    try:
        title_expected, part_expected = expected.split(":", maxsplit=1)
    except ValueError as error:
        raise ValueError("CFR fact selector must include title and part") from error
    matches: list[tuple[str, int]] = []
    for reference in value:
        if not isinstance(reference, dict):
            raise ValueError("Federal Register CFR reference is malformed")
        title = reference.get("title")
        part = reference.get("part")
        if title is None or part is None:
            continue
        title_text = str(title)
        part_text = str(part)
        if not title_text.isdigit() or not part_text.isdigit():
            raise ValueError("Federal Register CFR title/part is not numeric")
        if title_text == title_expected and part_text == part_expected:
            matches.append((part_text, int(part_text)))
    if len(matches) != 1:
        raise ValueError("selected CFR title/part is not unique in the source record")
    return matches[0]


@dataclass(frozen=True, slots=True)
class _ResolvedFederalFact:
    answer: str
    value: Any
    units: str | None
    currency: str | None
    effective_date: str | None = None


def _date_fact(
    spec: FederalFactSpec,
    record: dict[str, Any],
    field_value: Any,
    evidence_field: str,
) -> _ResolvedFederalFact:
    if spec.mode in {"effective_date", "applicability_date"}:
        source_date = _iso_date(record.get("effective_on"), "effective_on")
        if not isinstance(field_value, str):
            raise ValueError("Federal Register dates field must be text")
        _require_in_source(_human_date(source_date), field_value, evidence_field)
        answer = _human_date(source_date)
        effective_date = source_date if spec.mode == "effective_date" else None
        date_label = "effective" if spec.mode == "effective_date" else "applicable"
        if date_label not in field_value.casefold():
            raise ValueError(f"DATES section does not state an {date_label} date")
        return _ResolvedFederalFact(answer, source_date, spec.units, spec.currency, effective_date)

    if spec.mode == "compliance_date":
        if record.get("effective_on") is not None:
            raise ValueError("compliance-date question must not use effective_on")
        if spec.expected is None or not isinstance(field_value, str):
            raise ValueError("compliance-date source or expected date is missing")
        expected_date = _iso_date(spec.expected, "compliance date")
        _require_in_source(_human_date(expected_date), field_value, evidence_field)
        if "compliance date" not in field_value.casefold():
            raise ValueError("DATES section does not distinguish the compliance date")
        return _ResolvedFederalFact(
            _human_date(expected_date), expected_date, spec.units, spec.currency
        )
    raise ValueError("unsupported Federal Register date fact mode")


def _field_fact(
    spec: FederalFactSpec, field_value: Any, evidence_field: str
) -> _ResolvedFederalFact:
    value = spec.value
    answer: str
    if spec.mode == "abstract":
        if not isinstance(field_value, str) or spec.answer is None or spec.support is None:
            raise ValueError("abstract fact requires source text, answer, and support phrase")
        _require_in_source(spec.support, field_value, evidence_field)
        _require_in_source(spec.answer, field_value, evidence_field)
        answer = spec.answer
    elif spec.mode == "docket":
        if spec.expected is None:
            raise ValueError("docket fact requires a selected docket identifier")
        identifiers = _string_values(field_value, evidence_field)
        if spec.expected not in identifiers:
            raise ValueError("selected docket identifier is not in the official source field")
        answer = spec.expected
        value = answer
    elif spec.mode == "rin":
        identifiers = _string_values(field_value, evidence_field)
        if len(identifiers) != 1 or spec.expected != identifiers[0]:
            raise ValueError("selected RIN must be the record's single explicit identifier")
        answer = identifiers[0]
        value = answer
    elif spec.mode == "cfr_part":
        if spec.expected is None:
            raise ValueError("CFR part fact requires one explicit title/part selector")
        answer, value = _cfr_part_value(field_value, spec.expected)
    elif spec.mode == "citation":
        if not isinstance(field_value, str) or not field_value.strip():
            raise ValueError("Federal Register citation is missing")
        answer = field_value.strip()
        value = answer
    else:
        raise ValueError("unsupported Federal Register fact mode")
    return _ResolvedFederalFact(answer, value, spec.units, spec.currency)


def _fr_fact(
    spec: FederalFactSpec,
    raw_path: str,
    api_bytes: bytes,
    page_bytes: bytes,
    source_path: Path,
) -> dict[str, Any]:
    text = api_bytes.decode("utf-8", errors="strict")
    members = _top_level_members(text)
    record, title, published_at, _page_url, version = _rule_context(spec, members)
    mode_fields = {
        "effective_date": "dates",
        "applicability_date": "dates",
        "compliance_date": "dates",
        "abstract": "abstract",
        "docket": "docket_ids",
        "rin": "regulation_id_numbers",
        "cfr_part": "cfr_references",
        "citation": "citation",
    }
    try:
        evidence_field = mode_fields[spec.mode]
    except KeyError as error:
        raise ValueError("unsupported Federal Register fact mode") from error
    field_value, _api_excerpt = _required_member(members, evidence_field)
    if spec.mode in {"effective_date", "applicability_date", "compliance_date"}:
        resolved = _date_fact(spec, record, field_value, evidence_field)
    else:
        resolved = _field_fact(spec, field_value, evidence_field)

    excerpt = _public_html_excerpt(
        page_bytes,
        resolved.answer,
        title=title,
        support=spec.support if spec.mode == "abstract" else None,
    )
    query = f"For {version}, {spec.prompt}"
    public_page_url = _govinfo_fr_url(spec.document_number, published_at)
    return _canonical_case(
        case_id=spec.id,
        query=query,
        temporal_version=version,
        answer=resolved.answer,
        value=resolved.value,
        units=resolved.units,
        currency=resolved.currency,
        evidence={
            "url": public_page_url,
            "title": title,
            "retrievedAtUTC": _utc_timestamp(source_path),
            "publishedAt": published_at,
            "effectiveDate": resolved.effective_date,
            "sourceRecordId": spec.document_number,
            "upstreamRevision": version,
            "license": LICENSE,
            "rawSha256": _sha256(page_bytes),
            "rawPath": raw_path,
            "excerpt": excerpt,
        },
        source_family=SOURCE_FAMILY_RULE,
        question_type=spec.question_type,
    )


def _section_span(raw_text: str, section: str) -> str:
    markers = list(_SECTION_MARKER.finditer(raw_text))
    matches = [marker for marker in markers if marker.group(1) == section]
    if len(matches) != 1:
        raise ValueError("public-law section marker is missing or ambiguous")
    start = matches[0].start()
    end = next((marker.start() for marker in markers if marker.start() > start), len(raw_text))
    return raw_text[start:end]


def _law_excerpt(section_text: str, support: str) -> str:
    span = _normalized_span(section_text, support)
    if span is None:
        raise ValueError("statutory support phrase is not in the pinned section")
    index, support_end = span
    end = min(len(section_text), support_end + 1_000)
    if end <= 8_000:
        return section_text[:end]
    start = max(0, index - 6_000)
    excerpt = section_text[start : min(len(section_text), start + 8_000)]
    if _normalized_span(excerpt, support) is None:
        raise ValueError("statutory evidence excerpt lost the support phrase")
    return excerpt


def _normalized_span(text: str, needle: str) -> tuple[int, int] | None:
    """Find whitespace-normalized text while returning its original UTF-8 span."""
    normalized: list[str] = []
    offsets: list[int] = []
    pending_space = False
    for index, character in enumerate(text):
        if character.isspace():
            if normalized:
                pending_space = True
            continue
        if pending_space:
            normalized.append(" ")
            offsets.append(index)
            pending_space = False
        folded = character.casefold()
        for part in folded:
            normalized.append(part)
            offsets.append(index)
    target = " ".join(needle.casefold().split())
    normalized_text = "".join(normalized)
    found = normalized_text.find(target)
    if found < 0 or not target:
        return None
    start = offsets[found]
    end = offsets[found + len(target) - 1] + 1
    return start, end


def _statute_fact(
    spec: StatuteFactSpec,
    source: LawSource,
    raw_path: str,
    raw_bytes: bytes,
    source_path: Path,
) -> dict[str, Any]:
    raw_text = raw_bytes.decode("utf-8", errors="strict")
    section_text = _section_span(raw_text, spec.section)
    _validate_statute_fact(spec, section_text, source.public_law_id)
    excerpt = _law_excerpt(section_text, spec.support)
    version = source.version(spec.section)
    query = f"In {version}, {spec.prompt}"
    return _canonical_case(
        case_id=spec.id,
        query=query,
        temporal_version=version,
        answer=spec.answer,
        value=spec.value,
        units=spec.units,
        currency=spec.currency,
        evidence={
            "url": source.url,
            "title": f"{source.short_title} - Public Law {source.public_law_id}, § {spec.section}",
            "retrievedAtUTC": _utc_timestamp(source_path),
            "publishedAt": source.enacted_date,
            "sourceRecordId": f"PLAW-{source.public_law_id}:SEC{spec.section}",
            "upstreamRevision": version,
            "license": LICENSE,
            "rawSha256": _sha256(raw_bytes),
            "rawPath": raw_path,
            "excerpt": excerpt,
        },
        source_family=SOURCE_FAMILY_STATUTE,
        question_type=spec.question_type,
    )


def _validate_statute_fact(spec: StatuteFactSpec, section_text: str, public_law_id: str) -> None:
    field_name = f"Pub. L. {public_law_id} § {spec.section}"
    _require_in_source(spec.support, section_text, field_name)
    _require_in_source(spec.answer, section_text, field_name)
    if not isinstance(spec.value, (int, float)) or isinstance(spec.value, bool):
        return
    if not spec.units or spec.units.strip() in {"$", "USD"}:
        raise ValueError("numeric statutory facts require explicit measurement units")
    normalized_source = _normalized(section_text)
    unit_tokens = re.findall(r"[a-z]+", spec.units.casefold())
    aliases = {"cents": "cent", "days": "day", "years": "year", "hours": "hour"}
    ignored = {"usd", "per", "of", "the", "a", "an", "and", "total"}
    checked_terms = [aliases.get(token, token) for token in unit_tokens if token not in ignored]
    if checked_terms and any(term not in normalized_source for term in checked_terms):
        raise ValueError("statutory units are not supported by the cited section")
    if spec.currency == "USD" and not any(
        marker in section_text for marker in ("$", "U.S. dollar", "United States dollar")
    ):
        raise ValueError("USD currency is not explicit in the cited section")


def _court_fact(
    spec: CourtFactSpec,
    raw_path: str,
    raw_bytes: bytes,
    source_path: Path,
) -> dict[str, Any]:
    visible = _visible_html_text(raw_bytes)
    _require_in_source("Supreme Court of the State of Washington", visible, "court identity")
    _require_in_source(spec.case_title, visible, "court case title")
    docket_header = visible.split("Title of Case:", maxsplit=1)[0]
    _require_in_source(spec.docket, docket_header, "opinion docket number")
    file_date = date.fromisoformat(spec.filed_date).strftime("%m/%d/%Y")
    _require_in_source(file_date, visible, "opinion file date")
    author_context = re.sub(r"\s*\|\s*", " ", visible)
    _require_in_source(
        f"{spec.majority_author} Majority Author", author_context, "majority author field"
    )
    raw_text = raw_bytes.decode("utf-8", errors="strict")
    excerpt = _literal_html_excerpt(
        raw_text, spec.majority_author, required_phrase="Majority Author"
    )
    url = (
        "https://www.courts.wa.gov/opinions/index.cfm?fa=opinions.showOpinion"
        f"&filename={spec.filename}"
    )
    query = (
        f"Who did the Washington Supreme Court list as majority author of "
        f"{spec.case_title}, docket {spec.docket}, filed {_human_date(spec.filed_date)}?"
    )
    return _canonical_case(
        case_id=spec.id,
        query=query,
        temporal_version=None,
        temporal={"kind": "event", "precision": "day", "date": spec.filed_date},
        answer=spec.majority_author,
        value=None,
        units=None,
        currency=None,
        evidence={
            "url": url,
            "title": f"{spec.case_title} opinion information sheet, Washington Supreme Court",
            "retrievedAtUTC": _utc_timestamp(source_path),
            "publishedAt": spec.filed_date,
            "sourceRecordId": f"WA-SC-{spec.docket}-filed-{spec.filed_date}",
            "upstreamRevision": f"opinion filed {spec.filed_date}",
            "license": COURT_LICENSE,
            "rawSha256": _sha256(raw_bytes),
            "rawPath": raw_path,
            "excerpt": excerpt,
        },
        source_family=SOURCE_FAMILY_COURT,
        question_type="court_majority_opinion_author",
    )


def _canonical_case(
    *,
    case_id: str,
    query: str,
    temporal_version: str | None,
    temporal: dict[str, str] | None = None,
    answer: str,
    value: Any,
    units: str | None,
    currency: str | None,
    evidence: dict[str, Any],
    source_family: str,
    question_type: str,
) -> dict[str, Any]:
    scope = temporal or {
        "kind": "version",
        "precision": "version",
        "version": temporal_version or "",
    }
    gold: dict[str, Any] = {"answer": answer, "acceptedAnswers": [answer]}
    if value is not None:
        gold["value"] = value
    if units is not None:
        gold["units"] = units
    if currency is not None:
        gold["currency"] = currency
    result = QueryGoldCase.model_validate(
        {
            "schemaVersion": SCHEMA_VERSION,
            "id": case_id,
            "categoryId": CATEGORY_ID,
            "query": query,
            "temporal": scope,
            "gold": gold,
            "evidence": [evidence],
            "derivation": {
                "sourceFamily": source_family,
                "generatorVersion": GENERATOR_VERSION,
                "questionType": question_type,
            },
        },
        strict=True,
    )
    return result.model_dump(mode="json", exclude_none=True)


def _case_specs() -> tuple[tuple[str, Any], ...]:
    return (
        tuple(("federal", spec) for spec in FEDERAL_FACTS)
        + tuple(("court", spec) for spec in COURT_FACTS)
        + tuple(("statute", spec) for spec in STATUTE_FACTS)
    )


def _verify_collection(cases: list[dict[str, Any]], count: int) -> None:
    if len(cases) != count:
        raise ValueError("government/legal collector produced the wrong case count")
    ids = [case["id"] for case in cases]
    queries = [_normalized(case["query"]) for case in cases]
    if len(ids) != len(set(ids)) or len(queries) != len(set(queries)):
        raise ValueError("government/legal cases contain duplicate IDs or normalized queries")
    if count == 50:
        source_ids = {item["sourceRecordId"] for case in cases for item in case["evidence"]}
        question_types = {case["derivation"]["questionType"] for case in cases}
        if len(source_ids) < 25 or len(question_types) < 3:
            raise ValueError("government/legal cases do not meet source and question-type gates")


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Build cases from cached primary-source snapshots; fetch only missing pinned sources."""
    specs = _case_specs()
    if count <= 0 or count > len(specs):
        raise ValueError(f"count must be between 1 and {len(specs)}")
    output_dir = ensure_safe_path(Path(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = ensure_safe_path(output_dir, require_existing=True)
    raw_cache: dict[str, tuple[Path, bytes]] = {}
    ledger = _read_ledger(output_dir)
    run_state: dict[str, Any] = {
        "client": None,
        "ledger": ledger,
    }
    cases: list[dict[str, Any]] = []
    try:
        for kind, spec in specs[:count]:
            if kind == "federal":
                api_path = f"raw/federal-register/{spec.document_number}.json"
                api_url = (
                    f"https://www.federalregister.gov/api/v1/documents/{spec.document_number}.json"
                )
                if api_path not in raw_cache:
                    raw_cache[api_path] = _ensure_source(
                        output_dir,
                        api_path,
                        api_url,
                        run_state=run_state,
                        require_metadata=False,
                    )
                _api_source_path, api_bytes = raw_cache[api_path]
                members = _top_level_members(api_bytes.decode("utf-8", errors="strict"))
                published_at = _rule_context(spec, members)[2]
                page_url = _govinfo_fr_url(spec.document_number, published_at)
                raw_path = f"raw/federal-register-pages/{spec.document_number}.htm"
                if raw_path not in raw_cache:
                    raw_cache[raw_path] = _ensure_source(
                        output_dir, raw_path, page_url, run_state=run_state
                    )
                source_path, page_bytes = raw_cache[raw_path]
                cases.append(_fr_fact(spec, raw_path, api_bytes, page_bytes, source_path))
            elif kind == "court":
                raw_path = f"raw/washington-supreme/{spec.filename}.html"
                url = (
                    "https://www.courts.wa.gov/opinions/index.cfm?fa=opinions.showOpinion"
                    f"&filename={spec.filename}"
                )
                if raw_path not in raw_cache:
                    raw_cache[raw_path] = _ensure_source(
                        output_dir, raw_path, url, run_state=run_state
                    )
                source_path, raw_bytes = raw_cache[raw_path]
                cases.append(_court_fact(spec, raw_path, raw_bytes, source_path))
            else:
                source = LAWS[spec.law_key]
                raw_path = source.raw_path
                if raw_path not in raw_cache:
                    raw_cache[raw_path] = _ensure_source(
                        output_dir, raw_path, source.url, run_state=run_state
                    )
                path, raw_bytes = raw_cache[raw_path]
                cases.append(_statute_fact(spec, source, raw_path, raw_bytes, path))
    finally:
        client = run_state["client"]
        if client is not None:
            client.close()

    _verify_collection(cases, count)
    atomic_write_jsonl(output_dir / "cases.jsonl", cases)
    atomic_write_bytes(
        output_dir / "sources.md",
        _sources_markdown(cases, run_state["ledger"], output_dir).encode("utf-8"),
    )
    return cases


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/query-gold-curation/first-five-v1/categories") / CATEGORY_ID,
    )
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()
    cases = collect(args.output_dir, args.count)
    print(f"Collected {len(cases)} government/legal query-gold cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
