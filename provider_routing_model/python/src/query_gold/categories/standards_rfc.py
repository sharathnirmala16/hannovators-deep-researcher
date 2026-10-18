"""Collect dated RFC metadata from the official RFC Editor index."""

from __future__ import annotations

import hashlib
import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from query_gold.io import atomic_write_bytes, atomic_write_jsonl, ensure_safe_path, json_bytes

CATEGORY_ID = "24_standards_rfcs_technical_specifications"
GENERATOR_VERSION = "standards-rfc-collector/1.0"
INDEX_URL = "https://www.rfc-editor.org/rfc-index.xml"
MAX_PHYSICAL_REQUESTS = 152
MAX_SOURCE_BYTES = 20_000_000
REQUEST_TIMEOUT_SECONDS = 25.0
USER_AGENT = "query-gold-rfc-curation/1.0 (official public metadata)"
_NS = "{https://www.rfc-editor.org/rfc-index}"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _tag(element: ET.Element, name: str) -> str:
    node = element.find(f"{_NS}{name}")
    return " ".join("".join(node.itertext()).split()) if node is not None else ""


def _entries(raw: bytes) -> list[tuple[dict[str, str], str]]:
    text = raw.decode("utf-8", errors="strict")
    root = ET.fromstring(text)
    rows: list[tuple[dict[str, str], str]] = []
    xml_entries = re.finditer(r"<rfc-entry>.*?</rfc-entry>", text, flags=re.DOTALL)
    for element, match in zip(root.findall(f"{_NS}rfc-entry"), xml_entries, strict=True):
        number = _tag(element, "doc-id")
        if not re.fullmatch(r"RFC\d+", number):
            continue
        title = _tag(element, "title")
        month = _tag(element.find(f"{_NS}date") or ET.Element("empty"), "month")
        year = _tag(element.find(f"{_NS}date") or ET.Element("empty"), "year")
        status = _tag(element, "current-status")
        if not title or not month or not re.fullmatch(r"\d{4}", year) or not status:
            continue
        rows.append(
            (
                {"number": number, "title": title, "month": month, "year": year, "status": status},
                match.group(0),
            )
        )
    return rows


def _source_notes(count: int, attempts: list[dict[str, Any]], digest: str) -> str:
    return f"""# Standards, RFCs & technical specifications source notes

## Benchmark fit

This dataset asks direct questions about RFC titles, publication dates, and document identifiers.
Each answer is taken from an official RFC Editor document.

## Rejection criteria

Records without a title, publication month/year, or answer-bearing header are rejected.

## Construction method

Collected {count} unique RFC documents using {len(attempts)} physical network attempts.
RFC discovery index SHA-256: {digest}.

## License and source revision/snapshot policy

RFC texts are public; no reuse license is asserted. Response bytes, checksums, and retrieval
times are archived. Refresh only through explicit collection.

## Source concentration and diversity

All cases use the RFC Editor source family. Each question cites one distinct RFC document.

## Manual sample review

The collector checks literal answer support within the pinned source text. Manual search-result
placement review has not been performed.

## Public answer-bearing pages

Each RFC Editor text URL is a public answer-bearing page containing the cited title, date, or
identifier.

## Direct-search discoverability limitations

The RFC number is directly searchable. Long titles and publication dates may require a query
including the RFC identifier.

## Representativeness gaps

This RFC Editor dataset is not representative of ISO, IEEE, or W3C standards.
Protocol defaults and normative clause-level requirements are outside this version. This is a
limited metadata snapshot focused on public answer-bearing RFC documents.
"""


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:  # noqa: C901
    if isinstance(count, bool) or not isinstance(count, int) or count != 50:
        raise ValueError("standards RFC collector currently requires exactly 50 cases")
    output_dir = ensure_safe_path(Path(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = ensure_safe_path(output_dir, require_existing=True)
    raw_path = ensure_safe_path(output_dir / "raw" / "rfc-index.xml")
    attempts: list[dict[str, Any]] = []
    started = time.monotonic()
    with httpx.Client(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=10.0),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": USER_AGENT, "Accept": "application/xml"},
    ) as client:
        for attempt in (1, 2):
            if len(attempts) >= MAX_PHYSICAL_REQUESTS or time.monotonic() - started > 60:
                raise RuntimeError("RFC index request budget exceeded")
            index_attempt_row: dict[str, Any] = {
                "url": INDEX_URL,
                "attempt": attempt,
                "startedAtUTC": _now(),
                "statusCode": None,
                "responseBytes": None,
                "responseSha256": None,
                "errorType": None,
            }
            try:
                response = client.get(INDEX_URL)
                index_attempt_row["statusCode"] = response.status_code
                index_attempt_row["responseBytes"] = len(response.content)
                index_attempt_row["responseSha256"] = hashlib.sha256(response.content).hexdigest()
                index_attempt_row["completedAtUTC"] = _now()
                attempts.append(index_attempt_row)
                response.raise_for_status()
                if len(response.content) > MAX_SOURCE_BYTES:
                    raise ValueError("RFC index exceeded byte limit")
                response.content.decode("utf-8", errors="strict")
                raw = response.content
                break
            except (httpx.HTTPError, OSError, ValueError) as error:
                index_attempt_row["errorType"] = type(error).__name__
                if not attempts or attempts[-1] is not index_attempt_row:
                    index_attempt_row["completedAtUTC"] = _now()
                    attempts.append(index_attempt_row)
                if attempt == 2:
                    raise RuntimeError("official RFC index request failed") from None
                time.sleep(0.2)
        else:
            raise RuntimeError("RFC index request did not complete")

    digest = hashlib.sha256(raw).hexdigest()
    atomic_write_bytes(raw_path, raw)
    atomic_write_jsonl(ensure_safe_path(output_dir / "raw" / "network-attempts.jsonl"), attempts)
    candidates = _entries(raw)
    # Mix publication dates, current status, and title questions while ensuring
    # that each RFC identifier appears only once.
    eligible = [row for row in candidates if int(row[0]["year"]) >= 1980]
    if len(eligible) < count:
        raise RuntimeError("RFC index contained fewer than 50 eligible records")
    eligible = [row for row in reversed(eligible) if 2000 <= int(row[0]["year"]) <= 2025]
    targets = (("document_title", 17), ("publication_month", 17), ("rfc_number", 16))
    records: list[dict[str, Any]] = []
    used: set[str] = set()
    for question_type, target_count in targets:
        gathered = 0
        for metadata, _ in eligible:
            number = metadata["number"]
            if number in used:
                continue
            url = f"https://www.rfc-editor.org/rfc/{number.lower()}.txt"
            raw_doc: bytes | None = None
            doc_retrieved = _now()
            for attempt in (1, 2):
                if len(attempts) >= MAX_PHYSICAL_REQUESTS or time.monotonic() - started > 240:
                    raise RuntimeError("RFC document collection budget exceeded")
                row: dict[str, Any] = {
                    "url": url,
                    "attempt": attempt,
                    "startedAtUTC": _now(),
                    "statusCode": None,
                    "responseBytes": None,
                    "responseSha256": None,
                    "errorType": None,
                }
                try:
                    time.sleep(0.3)
                    response = httpx.get(
                        url,
                        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=10.0),
                        follow_redirects=False,
                        trust_env=False,
                        headers={"User-Agent": USER_AGENT, "Accept": "text/plain"},
                    )
                    row["statusCode"] = response.status_code
                    row["responseBytes"] = len(response.content)
                    row["responseSha256"] = hashlib.sha256(response.content).hexdigest()
                    row["completedAtUTC"] = _now()
                    attempts.append(row)
                    atomic_write_jsonl(
                        ensure_safe_path(output_dir / "raw" / "network-attempts.jsonl"),
                        attempts,
                    )
                    response.raise_for_status()
                    if len(response.content) > 3_000_000:
                        raise ValueError("RFC document exceeded byte limit")
                    response.content.decode("utf-8", errors="strict")
                    raw_doc = response.content
                    doc_retrieved = _now()
                    break
                except (httpx.HTTPError, OSError, ValueError) as error:
                    row["errorType"] = type(error).__name__
                    if not attempts or attempts[-1] is not row:
                        row["completedAtUTC"] = _now()
                        attempts.append(row)
                    atomic_write_jsonl(
                        ensure_safe_path(output_dir / "raw" / "network-attempts.jsonl"),
                        attempts,
                    )
                    if attempt == 2:
                        raw_doc = None
                        break
                    time.sleep(0.15)
            if raw_doc is None:
                continue
            document = raw_doc.decode("utf-8", errors="strict")
            if question_type == "document_title":
                title_pattern = r"\s+".join(re.escape(part) for part in metadata["title"].split())
                match = re.search(title_pattern, document[:20_000], flags=re.IGNORECASE)
                answer = match.group(0) if match is not None else metadata["title"]
                query = f"What is the exact title of RFC {number} in the RFC Editor document?"
            elif question_type == "publication_month":
                match = re.search(
                    rf"\b{re.escape(metadata['month'])}\s+{re.escape(metadata['year'])}\b",
                    document[:8_000],
                )
                answer = f"{metadata['month']} {metadata['year']}"
                query = f"What publication month and year appear in the header of RFC {number}?"
            else:
                number_value = number.removeprefix("RFC")
                match = re.search(
                    rf"(?:Request for Comments\s*:\s*0*{number_value}\b|"
                    rf"RFC\s*:\s*0*{number_value}\b)",
                    document[:8_000],
                    flags=re.IGNORECASE,
                )
                answer = number_value
                title_label = re.sub(r"\band\b", "&", metadata["title"], flags=re.IGNORECASE)
                query = (
                    f"What numeric RFC identifier appears in the header of the document titled "
                    f"{title_label}?"
                )
            if match is None:
                used.add(number)
                continue
            used.add(number)
            digest_doc = hashlib.sha256(raw_doc).hexdigest()
            raw_rel = f"raw/{number.lower()}.txt"
            atomic_write_bytes(ensure_safe_path(output_dir / raw_rel), raw_doc)
            excerpt = document[max(0, match.start() - 160) : min(len(document), match.end() + 240)]
            month_number = datetime.strptime(metadata["month"], "%B").month
            year_month = f"{metadata['year']}-{month_number:02d}"
            records.append(
                {
                    "schemaVersion": "query-gold/v1",
                    "id": f"standards-rfc-{number.lower()}-{question_type.replace('_', '-')}",
                    "categoryId": CATEGORY_ID,
                    "query": query,
                    "temporal": {
                        "kind": "immutable",
                        "precision": "immutable",
                        "immutableReason": (
                            "RFC document identifier and publication metadata are fixed "
                            "for this edition."
                        ),
                    },
                    "gold": {"answer": answer, "acceptedAnswers": [answer], "value": answer},
                    "evidence": [
                        {
                            "url": url,
                            "title": f"RFC Editor RFC {number} text",
                            "retrievedAtUTC": doc_retrieved,
                            "publishedAt": year_month,
                            "sourceRecordId": number,
                            "rawSha256": digest_doc,
                            "rawPath": raw_rel,
                            "excerpt": excerpt,
                        }
                    ],
                    "derivation": {
                        "sourceFamily": "official_rfc_editor_document",
                        "generatorVersion": GENERATOR_VERSION,
                        "questionType": question_type,
                    },
                }
            )
            gathered += 1
            if gathered == target_count:
                break
        if gathered != target_count:
            raise RuntimeError(f"RFC collector gathered only {gathered} {question_type} cases")
    atomic_write_jsonl(ensure_safe_path(output_dir / "raw" / "network-attempts.jsonl"), attempts)
    atomic_write_jsonl(ensure_safe_path(output_dir / "cases.jsonl"), records)
    atomic_write_bytes(
        ensure_safe_path(output_dir / "sources.md"),
        _source_notes(len(records), attempts, digest).encode("utf-8"),
    )
    atomic_write_bytes(
        ensure_safe_path(output_dir / "collection.json"),
        json_bytes(
            {
                "categoryId": CATEGORY_ID,
                "generatorVersion": GENERATOR_VERSION,
                "caseCount": len(records),
                "sourceSha256": digest,
                "attemptCount": len(attempts),
            },
            pretty=True,
        ),
    )
    return records
