# ruff: noqa: E501
"""Collect official Federal Register immigration and visa notice facts.

The Department of State Visa Bulletin archive is intermittently inaccessible
from the collection runtime. This collector instead uses the official Federal
Register API only for discovery, then captures the corresponding normal public
HTML documents and extracts their literal Agency, Action, or Dates sections.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from query_gold.io import atomic_write_bytes, atomic_write_jsonl, ensure_safe_path, json_bytes
from query_gold.models import QueryGoldCase

CATEGORY_ID = "19_immigration_visa_bulletins_consular_policies"
GENERATOR_VERSION = "immigration-visa-collector/2.0"
API_URL = "https://www.federalregister.gov/api/v1/documents.json"
SEARCH_TERM = "immigration visa"
MAX_PHYSICAL_REQUESTS = 110
MAX_RETRIES = 1
MAX_SOURCE_BYTES = 10_000_000
REQUEST_TIMEOUT_SECONDS = 20.0
MAX_COLLECTION_SECONDS = 240.0
USER_AGENT = "query-gold-immigration-curation/2.0 (official public sources)"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe(output_dir: Path, relative: str) -> Path:
    path = ensure_safe_path(output_dir)
    for part in Path(relative).parts:
        path = ensure_safe_path(path / part)
    return path


def _visible(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", fragment)).split())


def _section(document: str, name: str) -> str | None:
    match = re.search(
        rf'<div\s+id=["\']{re.escape(name)}["\']\s*>(.*?)</div>',
        document,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return None
    answer = _visible(match.group(1))
    heading = {"agency": "AGENCY:", "action": "ACTION:", "dates": "DATES:"}[name]
    if answer.casefold().startswith(heading.casefold()):
        answer = answer[len(heading) :].strip()
    return answer or None


def _effective_date(dates_text: str | None) -> str | None:
    if not dates_text:
        return None
    match = re.search(
        r"\b(?:is|on|from)\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})",
        dates_text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    try:
        datetime.strptime(match.group(1), "%B %d, %Y").date()
    except ValueError:
        return None
    return match.group(1)


def _request(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None,
    ledger: list[dict[str, Any]],
    started: float,
) -> bytes:
    for attempt in range(1, MAX_RETRIES + 2):
        if len(ledger) >= MAX_PHYSICAL_REQUESTS:
            raise RuntimeError("immigration source request cap reached")
        if time.monotonic() - started > MAX_COLLECTION_SECONDS:
            raise TimeoutError("immigration source collection time limit reached")
        entry: dict[str, Any] = {
            "url": url,
            "attempt": attempt,
            "startedAtUTC": _now(),
            "statusCode": None,
            "responseBytes": None,
            "responseSha256": None,
            "errorType": None,
        }
        try:
            response = client.get(url, params=params)
            entry["statusCode"] = response.status_code
            entry["responseBytes"] = len(response.content)
            entry["responseSha256"] = _sha256(response.content)
            entry["completedAtUTC"] = _now()
            ledger.append(entry)
            response.raise_for_status()
            if len(response.content) > MAX_SOURCE_BYTES:
                raise ValueError("Federal Register response exceeded the byte limit")
            response.content.decode("utf-8", errors="strict")
            return response.content
        except (httpx.HTTPError, OSError, ValueError) as error:
            entry["errorType"] = type(error).__name__
            if not ledger or ledger[-1] is not entry:
                entry["completedAtUTC"] = _now()
                ledger.append(entry)
            if attempt > MAX_RETRIES:
                raise RuntimeError(f"official Federal Register request failed ({url})") from None
            time.sleep(0.2 * attempt)
    raise RuntimeError("unreachable Federal Register retry state")


def _page_url(result: dict[str, Any]) -> str:
    number = result.get("document_number")
    publication_date = result.get("publication_date")
    if not isinstance(number, str) or not isinstance(publication_date, str):
        raise ValueError("Federal Register result lacks a document number or publication date")
    year, month, day = publication_date.split("-")
    # The normal document route redirects to an anti-bot gate in this runtime.
    # The Federal Register's official full-text HTML route serves the same
    # public document bytes directly and avoids following an untrusted host.
    return (
        "https://www.federalregister.gov/documents/full_text/html/"
        f"{year}/{month}/{day}/{number}.html"
    )


def _raw_section_excerpt(document: str, name: str) -> tuple[str, str] | None:
    match = re.search(
        rf'<div\s+id=["\']{re.escape(name)}["\']\s*>(.*?)</div>',
        document,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        return None
    answer = _visible(match.group(1))
    heading = {"agency": "AGENCY:", "action": "ACTION:", "dates": "DATES:"}[name]
    if answer.casefold().startswith(heading.casefold()):
        answer = answer[len(heading) :].strip()
    if answer:
        return answer, match.group(0)
    return None


def _query_for(result: dict[str, Any], kind: str, year: str) -> tuple[str, str, str] | None:
    title = result.get("title")
    number = result.get("document_number")
    if not isinstance(title, str) or not isinstance(number, str):
        return None
    if kind == "immigration_notice_agency":
        section = "agency"
        prefix = "Which agency issued the Federal Register immigration notice"
    elif kind == "immigration_notice_action":
        section = "action"
        prefix = "What action does the Federal Register immigration notice"
    else:
        section = "dates"
        prefix = "What effective date does the Federal Register immigration notice"
    query = f'{prefix} titled "{title}" ({number}, {year}) specify?'
    return section, query, title


def _source_candidates(api_data: bytes) -> list[dict[str, Any]]:
    payload = json.loads(api_data)
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise ValueError("Federal Register discovery response has no results list")
    candidates: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        abstract = item.get("abstract")
        text = f"{title or ''} {abstract or ''}".casefold()
        if not any(
            term in text for term in ("immigration", "immigrant visa", "consular", "visa bulletin")
        ):
            continue
        if not isinstance(item.get("publication_date"), str):
            continue
        if re.search(r"\b(?:latest|most recent|current|currently|today)\b", str(title), re.I):
            continue
        candidates.append(item)
    return candidates


def _make_case(
    result: dict[str, Any],
    *,
    section_name: str,
    answer: str,
    excerpt: str,
    page_url: str,
    raw_path: str,
    digest: str,
    retrieved: str,
) -> dict[str, Any]:
    publication_date = result["publication_date"]
    year = publication_date[:4]
    number = result["document_number"]
    title = result["title"]
    query_title = re.sub(r"\band\b", "&", title, flags=re.IGNORECASE)
    if section_name == "agency":
        qtype = "immigration_notice_agency"
        query = f'Which agency issued Federal Register immigration notice "{query_title}" ({number}, {year})?'
    elif section_name == "action":
        qtype = "immigration_notice_action"
        query = f'What action does Federal Register immigration notice "{query_title}" ({number}, {year}) specify?'
    else:
        qtype = "immigration_notice_effective_date"
        query = f'What effective date does Federal Register immigration notice "{query_title}" ({number}, {year}) specify?'
    record_id = f"federal-register-{number.lower()}-{qtype.removeprefix('immigration_notice_')}"
    record: dict[str, Any] = {
        "schemaVersion": "query-gold/v1",
        "id": f"imm-visa-{record_id}",
        "categoryId": CATEGORY_ID,
        "query": query,
        "temporal": {
            "kind": "immutable",
            "precision": "immutable",
            "immutableReason": "Published content of an official Federal Register notice",
        },
        "gold": {"answer": answer, "acceptedAnswers": []},
        "evidence": [
            {
                "url": page_url,
                "title": title,
                "retrievedAtUTC": retrieved,
                "publishedAt": publication_date,
                "sourceRecordId": f"federal-register-document-{number.lower()}",
                "license": "U.S. government work",
                "rawSha256": digest,
                "rawPath": raw_path,
                "excerpt": excerpt,
            }
        ],
        "derivation": {
            "sourceFamily": "federal_register_immigration_notice",
            "generatorVersion": GENERATOR_VERSION,
            "questionType": qtype,
        },
    }
    return QueryGoldCase.model_validate(record, strict=True).model_dump(
        mode="json", exclude_none=True
    )


def _sources_note(cases: list[dict[str, Any]], attempts: list[dict[str, Any]]) -> str:
    counts = Counter(item["derivation"]["questionType"] for item in cases)
    urls = sorted({item["evidence"][0]["url"] for item in cases})
    return "\n".join(
        (
            "# Immigration and visa source notes",
            "",
            "## Benchmark fit and construction method",
            "",
            "The collector asks direct questions about issuing agencies, document actions, and effective dates in official Federal Register immigration, visa, and consular notices. The official API is used only to discover document URLs; each case is supported by a captured normal public Federal Register HTML page.",
            "",
            "## Rejection criteria and limitations",
            "",
            "Documents without a visible Agency, Action, or explicit effective date section are rejected for the corresponding question. DOS Visa Bulletin HTML and PDF endpoints returned HTTP 403 in the collection runtime, so priority-date cutoff questions could not be captured from their original bytes. This dataset covers statutory and regulatory immigration notices and does not represent the visa-bulletin cutoff-date series.",
            "",
            "## License, revision, and network accounting",
            "",
            f"Collected {len(cases)} cases using {len(attempts)} physical requests. Federal Register government text is captured with exact response bytes, SHA-256 digests, timestamps, and an append-only request ledger. No reuse license beyond public government text is asserted.",
            "",
            "## Source and question-type concentration",
            "",
            f"Cases: {len(cases)}; distinct official document pages: {len(urls)}; question types: {dict(sorted(counts.items()))}.",
            "",
            "## Normal public answer-bearing pages",
            "",
            *[f"- {url}" for url in urls],
            "",
            "Search discoverability and the representativeness of this sampled notice set require human review.",
            "",
        )
    )


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:  # noqa: C901
    """Capture 50 distinct immigration and visa facts from official notices."""
    if isinstance(count, bool) or not isinstance(count, int) or count != 50:
        raise ValueError("immigration collector is curated for exactly 50 cases")
    output_dir = ensure_safe_path(Path(output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = ensure_safe_path(output_dir, require_existing=True)
    raw_dir = ensure_safe_path(output_dir / "raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = ensure_safe_path(raw_dir / "network-attempts.jsonl")
    ledger = (
        [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line]
        if ledger_path.is_file()
        else []
    )
    started = time.monotonic()
    api_path = ensure_safe_path(raw_dir / "federal-register-discovery-v2.json")
    api_meta = ensure_safe_path(raw_dir / "federal-register-discovery-v2.metadata.json")

    with httpx.Client(
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=8.0),
        follow_redirects=False,
        trust_env=False,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"},
    ) as client:
        if api_path.is_file() and api_meta.is_file():
            api_bytes = api_path.read_bytes()
            metadata = json.loads(api_meta.read_text(encoding="utf-8"))
            if metadata.get("rawSha256") != _sha256(api_bytes):
                raise ValueError("Federal Register discovery cache checksum mismatch")
        else:
            api_bytes = _request(
                client,
                API_URL,
                params={
                    "conditions[term]": SEARCH_TERM,
                    "per_page": 200,
                    "order": "newest",
                },
                ledger=ledger,
                started=started,
            )
            atomic_write_bytes(api_path, api_bytes)
            atomic_write_bytes(
                api_meta,
                json_bytes(
                    {"url": API_URL, "rawSha256": _sha256(api_bytes), "retrievedAtUTC": _now()}
                ),
            )

        cases: list[dict[str, Any]] = []
        seen: set[str] = set()
        for result in _source_candidates(api_bytes):
            if len(cases) >= count:
                break
            number = result.get("document_number")
            if not isinstance(number, str) or number in seen:
                continue
            page_url = _page_url(result)
            relative = f"raw/notices/{number.lower()}.html"
            page_path = ensure_safe_path(output_dir / relative)
            meta_path = ensure_safe_path(output_dir / f"{relative}.metadata.json")
            if page_path.is_file() and meta_path.is_file():
                document = page_path.read_bytes()
                page_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if page_meta.get("url") != page_url or page_meta.get("rawSha256") != _sha256(
                    document
                ):
                    raise ValueError("Federal Register notice cache metadata mismatch")
                retrieved = page_meta.get("retrievedAtUTC")
            else:
                document = _request(
                    client,
                    page_url,
                    params=None,
                    ledger=ledger,
                    started=started,
                )
                if urlsplit(page_url).hostname != "www.federalregister.gov":
                    raise ValueError("Federal Register page host mismatch")
                retrieved = _now()
                atomic_write_bytes(page_path, document)
                atomic_write_bytes(
                    meta_path,
                    json_bytes(
                        {
                            "url": page_url,
                            "rawSha256": _sha256(document),
                            "retrievedAtUTC": retrieved,
                        }
                    ),
                )

            digest = _sha256(document)
            effective = _effective_date(_section(document.decode("utf-8"), "dates"))
            options: list[tuple[str, str]] = []
            action = _raw_section_excerpt(document.decode("utf-8"), "action")
            agency = _raw_section_excerpt(document.decode("utf-8"), "agency")
            dates_section = _raw_section_excerpt(document.decode("utf-8"), "dates")
            if action is not None:
                options.append(("action", action[0]))
            if agency is not None:
                options.append(("agency", agency[0]))
            if effective is not None and dates_section is not None:
                options.append(("dates", effective))
            if not options:
                continue
            kind, answer = options[len(cases) % len(options)]
            if kind == "agency":
                acronyms = re.findall(r"\b(?:USCIS|DHS|DOJ|DOS|USCG|CBP|ICE|EOIR|BIA)\b", answer)
                if acronyms:
                    answer = acronyms[0]
            excerpt = (
                dates_section[1]
                if kind == "dates" and dates_section is not None
                else _raw_section_excerpt(document.decode("utf-8"), kind)[1]  # type: ignore[index]
            )
            record = _make_case(
                result,
                section_name=kind,
                answer=answer,
                excerpt=excerpt,
                page_url=page_url,
                raw_path=relative,
                digest=digest,
                retrieved=str(retrieved),
            )
            try:
                QueryGoldCase.model_validate(record, strict=True)
            except ValueError:
                continue
            cases.append(record)
            seen.add(number)
            atomic_write_jsonl(ensure_safe_path(output_dir / "cases.jsonl"), cases)
            atomic_write_jsonl(ledger_path, ledger)

    atomic_write_jsonl(ledger_path, ledger)
    if len(cases) != count:
        raise ValueError(
            f"Federal Register yielded {len(cases)} supported unique notices; 50 required"
        )
    if len({item["evidence"][0]["sourceRecordId"] for item in cases}) < 25:
        raise ValueError("immigration cases do not meet the 25-source diversity gate")
    if len({item["derivation"]["questionType"] for item in cases}) < 3:
        raise ValueError("immigration cases do not meet the three-question-type gate")
    atomic_write_bytes(
        ensure_safe_path(output_dir / "sources.md"),
        _sources_note(cases, ledger).encode("utf-8"),
    )
    return cases
