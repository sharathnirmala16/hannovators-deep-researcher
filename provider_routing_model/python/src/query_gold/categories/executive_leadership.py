"""Collect executive and board transition questions from official SEC 8-K filings.

The SEC's public full-text search index discovers candidate 8-Ks; each retained
fact is taken from the official filing bytes archived under the output folder.
The collector deliberately asks about the action stated in the filing, using a
short verbatim excerpt from Item 5.02 as the answer.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from query_gold.io import atomic_write_bytes, atomic_write_jsonl, ensure_safe_path

CATEGORY_ID = "23_executive_directory_corporate_leadership"
SCHEMA_VERSION = "query-gold/v1"
GENERATOR_VERSION = "query-gold-sec-leadership/1.0"
SOURCE_FAMILY = "sec_edgar_8k_item_5_02"
SEC_SEARCH = "https://efts.sec.gov/LATEST/search-index"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
MAX_PHYSICAL_REQUESTS = 400
MAX_RETRIES = 1
MAX_RESPONSE_BYTES = 2_000_000
REQUEST_TIMEOUT_SECONDS = 20
USER_AGENT = "Provider-Evals query-gold curation contact research@example.org"
_TRANSITION_WORDS = re.compile(
    r"\b(?:appoint(?:ed|ment)?|elect(?:ed|ion)?|resign(?:ed|ation)?|"
    r"retir(?:e|ed|ement)|depart(?:ed|ure)|succeed(?:ed|sor)|"
    r"Chief Executive Officer|Chief Financial Officer|director|Board)\b",
    re.IGNORECASE,
)
_ITEM_RE = re.compile(r"\bitem\s*5\.\s*02\b", re.IGNORECASE)
_NEXT_ITEM_RE = re.compile(r"\bitem\s*5\.\s*0[3-9]\b|\bitem\s*[6-9]\.\s*\d+\b", re.I)
_SPACE_RE = re.compile(r"\s+")


class _TextExtractor(HTMLParser):
    """Extract visible text from an HTML filing without altering its archive."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _get(url: str, state: dict[str, Any]) -> bytes:
    if state["attempts"] >= MAX_PHYSICAL_REQUESTS:
        raise RuntimeError("SEC physical request limit reached")
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        if state["attempts"] >= MAX_PHYSICAL_REQUESTS:
            break
        state["attempts"] += 1
        started = time.monotonic()
        status: int | None = None
        error_name: str | None = None
        try:
            request = Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
            )
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                status = response.status
                body = bytes(response.read(MAX_RESPONSE_BYTES + 1))
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError("SEC response exceeded the configured size bound")
            state["ledger"].append(
                {
                    "url": url,
                    "attempt": attempt + 1,
                    "status": status,
                    "outcome": "success",
                    "durationMs": int((time.monotonic() - started) * 1000),
                    "bytes": len(body),
                }
            )
            return body
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            last_error = error
            error_name = type(error).__name__
            if isinstance(error, HTTPError):
                status = error.code
            state["ledger"].append(
                {
                    "url": url,
                    "attempt": attempt + 1,
                    "status": status,
                    "outcome": "error",
                    "errorType": error_name,
                    "durationMs": int((time.monotonic() - started) * 1000),
                }
            )
            if attempt >= MAX_RETRIES or status not in {408, 425, 429, 500, 502, 503, 504, None}:
                break
            time.sleep(0.5)
    raise RuntimeError(f"SEC request failed ({error_name or 'unknown error'})") from last_error


def _record_metadata(hit: dict[str, Any]) -> tuple[str, str, str, str] | None:
    source = hit.get("_source") or hit.get("source") or {}
    if not isinstance(source, dict):
        return None
    cik = str(source.get("ciks", source.get("cik", "")))
    if isinstance(source.get("ciks"), list):
        cik = str(source["ciks"][0]) if source["ciks"] else ""
    accession = str(source.get("adsh", source.get("accessionNo", ""))).replace("-", "")
    hit_id = str(hit.get("_id", ""))
    filename = hit_id.split(":", 1)[1] if ":" in hit_id else ""
    filed = str(source.get("file_date", source.get("fileDate", "")))
    items = source.get("items", [])
    forms = source.get("root_forms", [])
    if not (
        cik.isdigit()
        and accession.isdigit()
        and filename
        and isinstance(items, list)
        and "5.02" in items
        and isinstance(forms, list)
        and "8-K" in forms
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", filed)
    ):
        return None
    return cik, accession, filename, filed


def _search_url(offset: int = 0) -> str:
    params = {
        "q": '"appointed as" OR "appointment of" OR "resignation of" OR "elected to the board"',
        "forms": "8-K",
        "dateRange": "custom",
        "startdt": "2018-01-01",
        "enddt": datetime.now(UTC).date().isoformat(),
        "from": str(offset),
        "size": "100",
    }
    return f"{SEC_SEARCH}?{urlencode(params)}"


def _candidate_excerpt(document: bytes) -> str | None:
    decoded = document.decode("utf-8", errors="replace")
    parser = _TextExtractor()
    parser.feed(decoded)
    text = _SPACE_RE.sub(" ", html.unescape(" ".join(parser.parts))).strip()
    item_matches = list(_ITEM_RE.finditer(text))
    # Filing tables of contents often mention Item 5.02 before its body. Search
    # from the last occurrence backwards so excerpts come from the actual item.
    action_pattern = re.compile(
        r"\b(?:was appointed|has been appointed|appointed as|appointed|named|elected|"
        r"resigned|will resign|retired|will retire|departed|succeeded)\b",
        re.IGNORECASE,
    )
    for item in reversed(item_matches):
        end_match = _NEXT_ITEM_RE.search(text, item.end())
        section = text[
            item.start() : end_match.start() if end_match else min(len(text), item.start() + 18000)
        ]
        for match in action_pattern.finditer(section):
            sentence = _SPACE_RE.sub(
                " ", section[max(0, match.start() - 450) : min(len(section), match.end() + 500)]
            ).strip()
            if len(sentence) >= 30:
                return sentence
    return None


def _person_in_transition(sentence: str) -> tuple[str, str] | None:
    """Return one named person and a transition type from a filing sentence."""
    name = (
        r"(?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?)?\s*"
        r"[A-Z][A-Za-z\u2019'.-]+(?:\s+[A-Z][A-Za-z\u2019'.-]+){1,3}"
    )
    patterns = (
        (
            "executive_appointment",
            rf"({name})\s+(?:(?:has been|was|is|will be)\s+)?(?:appointed|named|elected)\b",
        ),
        (
            "executive_departure",
            rf"({name})\s+(?:(?:has|has been|will be)\s+)?(?:resigned|retired|departed)\b",
        ),
        (
            "board_transition",
            rf"(?:appointment|election|resignation|retirement|departure)\s+of\s+({name})",
        ),
        ("executive_appointment", rf"(?:appointed|named|elected)\s+(?:as\s+)?({name})"),
    )
    for question_type, pattern in patterns:
        match = re.search(pattern, sentence)
        if match:
            person = _SPACE_RE.sub(" ", match.group(1)).strip(" ,.;:")
            person = re.sub(r"^(?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?)\s+", "", person)
            return person, question_type
    return None


def _raw_person_excerpt(document: bytes, person: str) -> str | None:
    decoded = document.decode("utf-8", errors="replace")
    match = re.search(re.escape(person), decoded, flags=re.IGNORECASE)
    if match is None:
        return None
    return decoded[max(0, match.start() - 500) : min(len(decoded), match.end() + 500)]


def _primary_filing_filename(
    cik: str, accession: str, index_hint: str, state: dict[str, Any]
) -> str | None:
    base_url = f"{ARCHIVES}/{int(cik)!s}/{accession}/"
    index_payload = json.loads(_get(base_url + "index.json", state))
    items = index_payload.get("directory", {}).get("item", [])
    hint_stem = index_hint.casefold().split("_", 1)[0]
    candidates = [
        str(item.get("name", ""))
        for item in items
        if isinstance(item, dict)
        and re.search(r"(?:8-k|form8k|form_8k)[^/]*\.html?$", str(item.get("name", "")), re.I)
    ]
    hinted = [name for name in candidates if name.casefold().startswith(hint_stem)]
    matches = hinted or candidates
    return matches[0] if matches else None


def _default_output_dir() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "results"
        / "query-gold-curation"
        / "eval-v2-v1"
        / "categories"
        / CATEGORY_ID
    )


def _safe_output_dir(path: Path) -> Path:
    safe = ensure_safe_path(path)
    for child in ("raw", "raw/filings", "raw/requests.jsonl", "cases.jsonl", "sources.md"):
        ensure_safe_path(safe / child)
    return safe


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:  # noqa: C901
    """Discover and archive up to 50 unique official 8-K leadership transitions."""
    if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 50:
        raise ValueError("count must be an integer between 0 and 50")
    if count == 0:
        return []
    output_dir = _safe_output_dir(Path(output_dir))
    raw_dir = _safe_output_dir(output_dir / "raw")
    filings_dir = _safe_output_dir(raw_dir / "filings")
    output_dir.mkdir(parents=True, exist_ok=True)
    filings_dir.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {"attempts": 0, "ledger": []}
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_rows: list[dict[str, str]] = []
    try:
        hits: list[dict[str, Any]] = []
        for offset in range(0, 500, 100):
            search_data = json.loads(_get(_search_url(offset), state))
            page = search_data.get("hits", {}).get("hits", [])
            if not page:
                break
            hits.extend(page)
        for hit in hits:
            metadata = _record_metadata(hit)
            if metadata is None:
                continue
            cik, accession, filename_hint, filed = metadata
            accession_hyphenated = f"{accession[:10]}-{accession[10:12]}-{accession[12:]}"
            case_id = f"exec-sec-{accession.lower()}"
            if case_id in seen:
                continue
            try:
                filename = _primary_filing_filename(cik, accession, filename_hint, state)
                if filename is None:
                    continue
                url = f"{ARCHIVES}/{int(cik)!s}/{accession}/{filename}"
                filing = _get(url, state)
            except RuntimeError:
                if state["attempts"] >= MAX_PHYSICAL_REQUESTS:
                    break
                continue
            sentence = _candidate_excerpt(filing)
            if sentence is None:
                continue
            transition = _person_in_transition(sentence)
            if transition is None:
                continue
            person, question_type = transition
            excerpt = _raw_person_excerpt(filing, person)
            if excerpt is None:
                continue
            raw_name = f"{accession}.html"
            raw_path = filings_dir / raw_name
            atomic_write_bytes(raw_path, filing)
            relative_raw = f"raw/filings/{raw_name}"
            digest = hashlib.sha256(filing).hexdigest()
            display_names = (hit.get("_source") or {}).get("display_names", [])
            company = (
                str(display_names[0])
                if isinstance(display_names, list) and display_names
                else "the issuer"
            )
            company = re.sub(r"\s+\(.*?\)$", "", company).strip()
            prompt_by_type = {
                "executive_appointment": (
                    f"Which executive did {company} appoint in its SEC Form 8-K filed on {filed}?"
                ),
                "executive_departure": (
                    f"Which executive departure did {company} disclose in its SEC Form 8-K "
                    f"filed on {filed}?"
                ),
                "board_transition": (
                    f"Which person was involved in the board transition disclosed by {company} "
                    f"in its SEC Form 8-K filed on {filed}?"
                ),
            }
            cases.append(
                {
                    "schemaVersion": SCHEMA_VERSION,
                    "id": case_id,
                    "categoryId": CATEGORY_ID,
                    "query": prompt_by_type[question_type],
                    "temporal": {"kind": "event", "precision": "day", "date": filed},
                    "gold": {"answer": person, "acceptedAnswers": [person]},
                    "evidence": [
                        {
                            "url": url,
                            "title": f"{company} SEC Form 8-K, accession {accession_hyphenated}",
                            "retrievedAtUTC": _utc_now(),
                            "publishedAt": filed,
                            "sourceRecordId": accession_hyphenated,
                            "license": "U.S. government work; SEC EDGAR filing",
                            "rawSha256": digest,
                            "rawPath": relative_raw,
                            "excerpt": excerpt,
                        }
                    ],
                    "derivation": {
                        "sourceFamily": SOURCE_FAMILY,
                        "generatorVersion": GENERATOR_VERSION,
                        "questionType": question_type,
                    },
                }
            )
            seen.add(case_id)
            source_rows.append(
                {"id": case_id, "company": company, "filed": filed, "url": url, "sha256": digest}
            )
            if len(cases) >= count:
                break
    finally:
        atomic_write_jsonl(raw_dir / "requests.jsonl", state["ledger"])
    if len(cases) < count:
        raise RuntimeError(
            f"SEC yielded {len(cases)} qualifying leadership cases; {count} requested "
            f"(physical requests: {state['attempts']}/{MAX_PHYSICAL_REQUESTS})"
        )
    atomic_write_jsonl(output_dir / "cases.jsonl", cases)
    lines = [
        "# Executive leadership SEC source manifest",
        "",
        f"Collected {len(source_rows)} unique Form 8-K filings from SEC EDGAR on {_utc_now()}.",
        (
            "Each case preserves bytes under raw/filings/; the SHA-256 values "
            "below identify those bytes."
        ),
        "",
        "| Case ID | Issuer | Filed | Official filing | SHA-256 |",
        "|---|---|---|---|---|",
    ]
    lines.extend(
        f"| {row['id']} | {row['company'].replace('|', ' ')} | {row['filed']} | "
        f"[{row['url']}]({row['url']}) | {row['sha256']} |"
        for row in source_rows
    )
    lines.extend(
        [
            "",
            "## Benchmark fit",
            "",
            (
                "Cases ask which named person appears in an executive appointment, departure, "
                "or board transition in an official SEC Form 8-K."
            ),
            "",
            "## Rejection criteria",
            "",
            (
                "Filings without Item 5.02 transition language, a named person, or an "
                "answer-bearing primary document are rejected."
            ),
            "",
            "## Construction method",
            "",
            (
                "SEC EDGAR full-text search discovers candidates. Primary filing pages are "
                "fetched and archived; every case cites its filing bytes."
            ),
            "",
            "## License and source revision/snapshot policy",
            "",
            (
                "SEC filings are U.S. government records; no additional license is asserted. "
                "Retrieval date, response checksum, and raw filing are preserved."
            ),
            "",
            "## Source concentration and diversity",
            "",
            "The set uses 50 distinct SEC accessions, one Form 8-K per case.",
            "",
            "## Manual sample review",
            "",
            (
                "Automated checks confirm the named answer occurs in the cited filing excerpt. "
                "Review the name-to-transition association before downstream use."
            ),
            "",
            "## Public answer-bearing pages",
            "",
            "Each evidence URL is the public SEC EDGAR primary Form 8-K page.",
            "",
            "## Direct-search discoverability limitations",
            "",
            (
                "Questions include issuer, filing date, Form 8-K, and the leadership event, "
                "which can be searched directly."
            ),
            "",
            "## Representativeness gaps and limitations",
            "",
            (
                "This sample reflects EDGAR-searchable filings and does not cover unreported "
                "executive changes or non-U.S. corporate registries."
            ),
        ]
    )
    (output_dir / "sources.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=_default_output_dir())
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args(argv)
    try:
        cases = collect(args.output_dir, args.count)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"executive leadership collection failed: {error}", file=sys.stderr)
        return 1
    print(
        f"Wrote {len(cases)} executive leadership query/gold cases "
        f"to {args.output_dir / 'cases.jsonl'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
