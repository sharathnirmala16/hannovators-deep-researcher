"""Curate consumer product recall facts from official CPSC announcement pages.

This module intentionally uses CPSC recall notices rather than search-result
snippets.  The listing CSV is used only for discovery; every case cites and
archives its normal public announcement page.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import re
import unicodedata
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from query_gold.io import ensure_safe_path

CATEGORY_ID = "22_consumer_ecommerce_msrp_recall_notices"
SCHEMA_VERSION = "query-gold/v1"
GENERATOR_VERSION = "consumer-recalls/1"
SOURCE_FAMILY = "cpsc_product_recall_announcement"
LISTING_URL = "https://www.cpsc.gov/s3fs-public/recall-data/recalls_recall_listing.csv"
ANNOUNCEMENT_ROOT = "https://www.cpsc.gov/Recalls/"
USER_AGENT = "query-gold-consumer-recalls/1.0 (public safety data curation)"
MAX_PHYSICAL_REQUESTS = 180
MAX_RETRIES = 1
_DATE_FORMAT = "%B %d, %Y"
_RETRYABLE = {408, 425, 429, 500, 502, 503, 504}
_MODEL = re.compile(
    r"\b(?:model\s+numbers?|sku(?:s)?|item\s+numbers?)\s*(?:include|are|:|of|number)?\s*[:#]?\s*([A-Z0-9][A-Z0-9./_-]{2,})",
    re.IGNORECASE,
)
_STOPWORDS = {"a", "an", "and", "at", "by", "for", "from", "in", "of", "or", "the", "to", "with"}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _slug(heading: str, year: int) -> str:
    text = unicodedata.normalize("NFKD", heading).encode("ascii", "ignore").decode()
    text = text.replace("&", " ").replace("'", "")
    words = re.findall(r"[A-Za-z0-9]+", text)
    slug_words = [word.lower() if word.lower() in _STOPWORDS else word for word in words]
    return f"{ANNOUNCEMENT_ROOT}{year}/" + "-".join(slug_words)


def _line_excerpt(raw_text: str, needle: str) -> str:
    """Return a short literal source substring containing a distinctive answer."""
    offset = raw_text.find(needle)
    if offset < 0:
        raise ValueError("answer text is absent from the official CPSC page bytes")
    start = max(0, offset - 220)
    end = min(len(raw_text), offset + len(needle) + 240)
    excerpt = raw_text[start:end]
    if len(excerpt) > 8000:
        raise ValueError("excerpt exceeds schema limit")
    return excerpt


def _fetch(client: httpx.Client, url: str, ledger: list[dict[str, Any]]) -> httpx.Response:
    for attempt in range(1, MAX_RETRIES + 2):
        if len(ledger) >= MAX_PHYSICAL_REQUESTS:
            raise RuntimeError("CPSC public-source request cap reached")
        started = _utc_now()
        entry: dict[str, Any] = {
            "url": url,
            "attempt": attempt,
            "startedAtUTC": started,
            "status": None,
            "responseBytes": None,
            "responseSha256": None,
            "errorType": None,
        }
        try:
            response = client.get(url)
            entry["status"] = response.status_code
            entry["responseBytes"] = len(response.content)
            entry["responseSha256"] = _digest(response.content)
            ledger.append(entry)
            if response.status_code in _RETRYABLE and attempt <= MAX_RETRIES:
                continue
            response.raise_for_status()
            return response
        except httpx.HTTPError as error:
            if not entry["status"]:
                entry["errorType"] = type(error).__name__
                ledger.append(entry)
            if attempt > MAX_RETRIES or (
                entry["status"] not in _RETRYABLE and entry["status"] is not None
            ):
                raise
    raise RuntimeError("CPSC request retries exhausted")


def _row_date(row: dict[str, str]) -> date | None:
    try:
        return datetime.strptime(row.get("Date", ""), _DATE_FORMAT).date()
    except ValueError:
        return None


def _model_from_description(description: str) -> str | None:
    text = html.unescape(re.sub(r"<[^>]*>", " ", description))
    match = _MODEL.search(text)
    if not match:
        return None
    candidate = match.group(1).strip(".,;:()")
    if candidate.casefold() in {"number", "numbers", "include", "are"}:
        return None
    return candidate


def _visible_field(raw_text: str, label: str) -> str | None:
    match = re.search(
        rf"{re.escape(label)}\s*</div>\s*<div class=\"padding-y-1 [^\"]*\">(.*?)</div>",
        raw_text,
        flags=re.DOTALL,
    )
    if match is None:
        return None
    visible = html.unescape(re.sub(r"<[^>]*>", " ", match.group(1)))
    return " ".join(visible.split())


def _case(
    *,
    row: dict[str, str],
    page_url: str,
    page_raw: bytes,
    raw_path: str,
    retrieved_at: str,
    question_type: str,
    answer: str,
    gold_units: str | None,
    query: str,
    excerpt_needle: str,
) -> dict[str, Any]:
    recall_id = row["Recall Number"].strip()
    date_value = _row_date(row)
    if date_value is None:
        raise ValueError("recall date is missing or cannot be parsed")
    page_text = page_raw.decode("utf-8", errors="strict")
    excerpt = _line_excerpt(page_text, excerpt_needle)
    product = row["Name of product"].strip()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "id": (f"consumer-recall-{recall_id.lower()}-{question_type.replace('_', '-')}"),
        "categoryId": CATEGORY_ID,
        "query": query,
        "temporal": {"kind": "event", "precision": "day", "date": date_value.isoformat()},
        "gold": {
            "answer": answer,
            "acceptedAnswers": [],
            "value": answer,
            "units": gold_units,
        },
        "evidence": [
            {
                "url": page_url,
                "title": row.get("Recall Heading", product).strip(),
                "retrievedAtUTC": retrieved_at,
                "publishedAt": date_value.isoformat(),
                "sourceRecordId": recall_id,
                "license": "U.S. government work; 17 U.S.C. § 105",
                "rawSha256": _digest(page_raw),
                "rawPath": raw_path,
                "excerpt": excerpt,
            }
        ],
        "derivation": {
            "sourceFamily": SOURCE_FAMILY,
            "generatorVersion": GENERATOR_VERSION,
            "questionType": question_type,
        },
    }


def _sources_markdown(
    records: list[dict[str, Any]], rejected: dict[str, int], request_count: int
) -> str:
    by_type: dict[str, int] = {}
    for record in records:
        qtype = record["derivation"]["questionType"]
        by_type[qtype] = by_type.get(qtype, 0) + 1
    return f"""# Consumer E-Commerce, MSRP & Recall Notices

## Benchmark fit
The set contains official U.S. consumer product recall campaign identifiers,
recalled-unit counts, and manufacturer model/SKU identifiers. These are
time-scoped recall facts answerable from a single public CPSC announcement page.

## Candidate rejection criteria and counts
The CPSC official recall listing was filtered to dated product recalls published
in 2024-{date.today().year}, with a public announcement route. Non-product
safety warnings, missing dates/recall IDs, records without an answer-bearing
field, unavailable announcement pages, and duplicate recall IDs were rejected.
Rejection counts: {json.dumps(rejected, sort_keys=True)}.

## Construction method
The official CPSC listing CSV was used for discovery only. Every selected record
was independently fetched from its normal `cpsc.gov/Recalls/YYYY/...`
announcement page, cached as exact UTF-8 bytes, and cited using a literal
substring from those bytes. Each recall contributes one standalone field
question, for 50 records from 50 distinct recalls. Network attempts are archived
in `raw/network-attempts.jsonl` ({request_count} physical requests).

## License and source revision/snapshot policy
CPSC is a U.S. federal agency; public government-authored announcement content
is treated as public domain under 17 U.S.C. § 105. Each source page is pinned by
its SHA-256 digest and retrieval timestamp. CPSC may update notices after
publication; this snapshot retains the bytes retrieved during collection.

## Source/question-type concentration
All cases use the CPSC recall announcement source family. Question-type counts:
`{json.dumps(by_type, sort_keys=True)}`. Source-record concentration: 50 recall
IDs, one case per ID.

## Manual sample-review note
The collector checks that each cited answer token occurs in the exact cached
announcement bytes. This verifies provenance and literal support, not the
underlying product safety claim independently. Human review should check
entity-field matching and the interpretation of approximate unit counts.

## Normal public answer-bearing pages
Each evidence URL is a public CPSC recall announcement page. CPSC announcement
pages ordinarily state the recall number, recall date, unit count, product
description, remedy, and sold-at details.

## Direct-search discoverability limitations
Recall number and model-number questions are normally searchable by product and
campaign identifier. CPSC states approximate recalled-unit counts; questions
preserve the notice's approximation. Some pages provide historical sold-at
prices, but not necessarily manufacturer launch MSRP. This collection does not
claim that an announced sale price is MSRP.

## Representativeness gaps
The collection covers products in CPSC jurisdiction and does not cover
FDA-regulated food, drug, medical-device, or cosmetic recalls. It does not
establish manufacturer launch MSRP; product-model/SKU and recall facts dominate.
Retail availability and sales-price language vary by notice.
"""


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:  # noqa: C901
    """Fetch and cache up to ``count`` distinct public CPSC recall cases."""
    if count != 50:
        raise ValueError("this category is curated as exactly 50 cases")
    output_dir = ensure_safe_path(output_dir)
    raw_dir = ensure_safe_path(output_dir / "raw")
    raw_dir.mkdir(parents=True, exist_ok=True)
    ledger: list[dict[str, Any]] = []
    rejected = {
        "outside_date_window": 0,
        "missing_fields": 0,
        "not_online": 0,
        "page_unavailable": 0,
        "no_model": 0,
    }

    headers = {"User-Agent": USER_AGENT, "Accept": "text/csv,text/html;q=0.9,*/*;q=0.8"}
    with httpx.Client(
        timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True, headers=headers
    ) as client:
        listing = _fetch(client, LISTING_URL, ledger)
        listing_raw = listing.content
        (raw_dir / "cpsc-recall-listing.csv").write_bytes(listing_raw)
        rows = list(csv.DictReader(io.StringIO(listing_raw.decode("utf-8-sig", errors="strict"))))
        candidates: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        today = date.today()
        lower = date(today.year - 2, 1, 1)
        for row in rows:
            recall_id = row.get("Recall Number", "").strip()
            published = _row_date(row)
            if not recall_id or not row.get("Recall Heading", "").strip() or published is None:
                rejected["missing_fields"] += 1
                continue
            if published < lower or published > today:
                rejected["outside_date_window"] += 1
                continue
            if recall_id in seen_ids:
                continue
            seen_ids.add(recall_id)
            if "online" not in row.get("Sold At", "").casefold():
                rejected["not_online"] += 1
                continue
            if not row.get("Units", "").strip() or row["Units"].strip().casefold() in {
                "none",
                "n/a",
                "not reported",
            }:
                rejected["missing_fields"] += 1
                continue
            candidates.append(row)

        # Deterministically vary the dimensions while preserving one unique
        # source record per case and requiring evidence for the requested field.
        model_rows = [
            row
            for row in candidates
            if (model := _model_from_description(row.get("Description", "")))
            and model.casefold() not in row.get("Name of product", "").casefold()
        ]
        unit_rows = [r for r in candidates if re.search(r"\d", r.get("Units", ""))]
        id_rows = list(candidates)
        queues = [id_rows, unit_rows, model_rows]
        types = ["recall_campaign_id", "recalled_unit_count", "manufacturer_model_or_sku"]
        records: list[dict[str, Any]] = []
        used: set[str] = set()
        raw_files: dict[str, bytes] = {}
        retrieved_times: dict[str, str] = {}
        type_cursor = 0
        page_cache: dict[str, tuple[bytes, str, str]] = {}
        while len(records) < count:
            qtype = types[type_cursor % len(types)]
            queue = queues[type_cursor % len(queues)]
            type_cursor += 1
            selected = next((r for r in queue if r["Recall Number"].strip() not in used), None)
            if selected is None:
                raise RuntimeError(f"only {len(records)} suitable distinct CPSC recalls were found")
            recall_id = selected["Recall Number"].strip()
            pub_date = _row_date(selected)
            assert pub_date is not None
            product_label = re.sub(
                r"\band\b", "&", selected["Name of product"].strip(), flags=re.IGNORECASE
            )
            url = _slug(selected["Recall Heading"], pub_date.year)
            if url not in page_cache:
                try:
                    response = _fetch(client, url, ledger)
                    if "Recall number:" not in response.text or recall_id not in response.text:
                        raise ValueError("page did not visibly identify its CPSC recall number")
                    page_cache[url] = (response.content, str(response.url), _utc_now())
                except (httpx.HTTPError, ValueError, RuntimeError):
                    rejected["page_unavailable"] += 1
                    used.add(recall_id)
                    continue
            page_raw, final_url, retrieved = page_cache[url]
            page_text = page_raw.decode("utf-8", errors="strict")

            if qtype == "recall_campaign_id":
                answer = recall_id
                gold_units = None
                needle = recall_id
                query = (
                    f"What CPSC recall campaign number was assigned to "
                    f"{product_label} in the recall "
                    f"notice dated {pub_date.isoformat()}?"
                )
            elif qtype == "recalled_unit_count":
                raw_units = selected["Units"].replace("\xa0", " ").strip()
                match = re.search(r"(?:about\s+)?([\d,]+)", raw_units, re.IGNORECASE)
                unit_text = _visible_field(page_text, "Units:")
                if not match or unit_text is None:
                    rejected["missing_fields"] += 1
                    used.add(recall_id)
                    continue
                number = match.group(1)
                if number not in unit_text:
                    rejected["missing_fields"] += 1
                    used.add(recall_id)
                    continue
                answer_match = re.search(
                    rf"(?:About\s+)?{re.escape(number)}(?:\s+units)?",
                    unit_text,
                    flags=re.IGNORECASE,
                )
                if answer_match is None:
                    rejected["missing_fields"] += 1
                    used.add(recall_id)
                    continue
                answer = number
                gold_units = None
                needle = number
                query = (
                    f"How many units did the CPSC report as recalled for "
                    f"{product_label} in its "
                    f"{pub_date.isoformat()} notice?"
                )
            else:
                model = _model_from_description(selected.get("Description", ""))
                if model is None:
                    rejected["no_model"] += 1
                    used.add(recall_id)
                    continue
                if model not in page_text:
                    model_search = re.search(re.escape(model), page_text, re.IGNORECASE)
                    if not model_search:
                        rejected["no_model"] += 1
                        used.add(recall_id)
                        continue
                    needle = page_text[model_search.start() : model_search.end()]
                else:
                    needle = model
                answer = model
                gold_units = None
                query = (
                    f"What model number or SKU does the CPSC identify for "
                    f"{product_label} in the "
                    f"{pub_date.isoformat()} recall notice?"
                )

            raw_path = f"raw/recall-{recall_id.lower()}.html"
            if raw_path not in raw_files:
                raw_files[raw_path] = page_raw
                retrieved_times[raw_path] = retrieved
            record = _case(
                row=selected,
                page_url=final_url,
                page_raw=page_raw,
                raw_path=raw_path,
                retrieved_at=retrieved,
                question_type=qtype,
                answer=answer,
                gold_units=gold_units,
                query=query,
                excerpt_needle=needle,
            )
            records.append(record)
            used.add(recall_id)

    for relative, raw in raw_files.items():
        target = ensure_safe_path(output_dir / relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (raw_dir / "network-attempts.jsonl").write_text(
        "".join(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n" for entry in ledger),
        encoding="utf-8",
    )
    (raw_dir / "cpsc-recall-listing.csv.metadata.json").write_text(
        json.dumps(
            {
                "url": LISTING_URL,
                "retrievedAtUTC": ledger[0]["startedAtUTC"],
                "rawSha256": _digest(listing_raw),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "cases.jsonl").write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
        ),
        encoding="utf-8",
    )
    (output_dir / "sources.md").write_text(
        _sources_markdown(records, rejected, len(ledger)), encoding="utf-8"
    )
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args(argv)
    records = collect(args.output_dir, count=args.count)
    print(f"Collected {len(records)} {CATEGORY_ID} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
