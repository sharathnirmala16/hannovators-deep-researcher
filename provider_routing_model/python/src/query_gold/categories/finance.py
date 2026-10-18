"""Curate direct-search finance questions from issuer earnings releases.

The cases are constructed factual questions, not reused FinanceBench QA pairs.
Each answer is a literal value in one pinned, public issuer release.  The local
source manifest and UTF-8 text-layer snapshots are private curation artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from query_gold.io import atomic_write_bytes, atomic_write_jsonl, ensure_safe_path

from .finance_facts import FACTS, FinanceFact

CATEGORY_ID = "01_earnings_corporate_finance"
SCHEMA_VERSION = "query-gold/v1"
GENERATOR_VERSION = "finance-collector/1"
SOURCE_FAMILY = "official_issuer_earnings_release"
UPSTREAM_REVISION = "cc39aeb4afdf33909ee1412188bf89035950c2eb"
MANIFEST_SHA256 = "2146e0c1aa52ecc880194dcd75603968520fca39d5e81705e0aad9776c63ca42"


_NUMBER = re.compile(
    r"(?<![A-Za-z0-9])(?:\$\s*)?(?P<open>\()?\s*"
    r"(?P<number>-?\d[\d,]*(?:\.\d+)?)\s*(?P<close>\))?%?"
)
_QUERY_RED_FLAGS = (
    "above document",
    "the company in question",
    "this company",
    "previously mentioned",
    "based on the above",
    "compare across documents",
    "calculate",
    "compute",
    "derive",
    "what is the difference",
)


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _numbers(value: str) -> list[Decimal]:
    found: list[Decimal] = []
    for match in _NUMBER.finditer(value):
        try:
            number = Decimal(match.group("number").replace(",", ""))
        except InvalidOperation as error:
            raise ValueError(f"invalid numeric source token: {value!r}") from error
        if match.group("open") or match.group("close"):
            number = -number
        found.append(number)
    if not found:
        raise ValueError(f"source token contains no numeric value: {value!r}")
    return found


def _gold_numbers(value: float | list[float]) -> list[Decimal]:
    values = value if isinstance(value, list) else [value]
    result = [Decimal(str(item)) for item in values]
    if any(not item.is_finite() for item in result):
        raise ValueError("gold values must be finite")
    return result


def _source_numeric_columns(line: str, field_token: str) -> list[Decimal]:
    start = line.casefold().find(field_token.casefold())
    if start < 0:
        raise ValueError("the selected source row does not contain its metric field")
    return _numbers(line[start + len(field_token) :])


def _validate_source_excerpt(fact: FinanceFact, excerpt: str, anchor_line: str) -> None:
    """Reject wrong fields, periods, units, or table columns before exporting."""
    if fact.field_token.casefold() not in anchor_line.casefold():
        raise ValueError(f"{fact.case_id}: selected source row has the wrong financial field")
    if fact.value_token not in anchor_line:
        raise ValueError(f"{fact.case_id}: selected source row does not state its gold value")
    if fact.period_token.casefold() not in excerpt.casefold():
        raise ValueError(f"{fact.case_id}: evidence does not state the requested period")
    if fact.unit_token.casefold() not in excerpt.casefold():
        raise ValueError(f"{fact.case_id}: evidence does not state the requested units")

    source_values = _numbers(fact.value_token)
    gold_values = _gold_numbers(fact.value)
    if source_values != gold_values:
        raise ValueError(
            f"{fact.case_id}: parsed source value {source_values!r} does not match "
            f"gold {gold_values!r}"
        )
    if fact.column_index is not None:
        columns = _source_numeric_columns(anchor_line, fact.field_token)
        if fact.column_index >= len(columns) or columns[fact.column_index] != gold_values[0]:
            raise ValueError(
                f"{fact.case_id}: selected value is not in the requested period column"
            )


def _extract_excerpt(source_text: str, fact: FinanceFact) -> str:
    """Return the exact source lines needed for field, period, unit, and value."""
    if fact.context_before < 0 or fact.context_after < 0:
        raise ValueError(f"{fact.case_id}: evidence context cannot be negative")
    lines = source_text.splitlines(keepends=True)
    candidates = [
        index
        for index, line in enumerate(lines)
        if fact.anchor in line
        and fact.field_token.casefold() in line.casefold()
        and fact.value_token in line
    ]
    if len(candidates) != 1:
        raise ValueError(f"{fact.case_id}: expected one anchor occurrence, found {len(candidates)}")
    anchor_index = candidates[0]
    start = max(0, anchor_index - fact.context_before)
    end = min(len(lines), anchor_index + fact.context_after + 1)
    excerpt = "".join(lines[start:end])
    _validate_source_excerpt(fact, excerpt, lines[anchor_index])
    return excerpt


def _validate_query(fact: FinanceFact, source: dict[str, Any]) -> None:
    query = _normalize(fact.query)
    version = _normalize(source["version"])
    entity = _normalize(source["queryEntity"])
    if version not in query:
        raise ValueError(f"{fact.case_id}: query must state the exact report-period version")
    if entity not in query:
        raise ValueError(f"{fact.case_id}: query must name the issuer")
    if _normalize(fact.answer) in query:
        raise ValueError(f"{fact.case_id}: query leaks its canonical answer")
    for red_flag in _QUERY_RED_FLAGS:
        if red_flag in query:
            raise ValueError(f"{fact.case_id}: query has a non-direct-search red flag: {red_flag}")


def _load_source_manifest(output_dir: Path) -> dict[str, Any]:
    category_dir = ensure_safe_path(output_dir, require_existing=True)
    manifest_path = ensure_safe_path(
        category_dir / "raw" / "source_manifest.json", require_existing=True
    )
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        raise ValueError("pinned finance source manifest checksum mismatch")
    manifest: object = json.loads(raw.decode("utf-8", errors="strict"))
    if not isinstance(manifest, dict):
        raise ValueError("source manifest must contain a JSON object")
    if manifest.get("schemaVersion") != "finance-source-snapshot/v1":
        raise ValueError("unsupported source manifest schema")
    if manifest.get("upstreamRevision") != UPSTREAM_REVISION:
        raise ValueError("source manifest upstream revision is not pinned")
    selected_records = manifest.get("selectedRecords")
    if (
        not isinstance(selected_records, list)
        or len(selected_records) != 25
        or not all(isinstance(record, dict) for record in selected_records)
    ):
        raise ValueError("expected 25 selected issuer source records")
    return cast(dict[str, Any], manifest)


def _source_bytes(output_dir: Path, source: dict[str, Any], path_key: str, hash_key: str) -> bytes:
    relative = source[path_key]
    if (
        not isinstance(relative, str)
        or not relative.startswith("raw/")
        or ".." in Path(relative).parts
    ):
        raise ValueError("source manifest contains an unsafe raw path")
    category_dir = ensure_safe_path(output_dir, require_existing=True)
    path = ensure_safe_path(category_dir / Path(*relative.split("/")), require_existing=True)
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != source[hash_key]:
        raise ValueError(f"source snapshot hash mismatch: {relative}")
    return data


def collect(output_dir: Path, count: int = 50) -> list[dict[str, Any]]:
    """Build direct-search query/gold records from the pinned local snapshots.

    Collection is deliberately offline and resumable: all selected source PDFs,
    extracted UTF-8 snapshots, and the pinned source manifest live under
    ``output_dir/raw``.  The returned evidence paths are relative to output_dir.
    """
    if not isinstance(count, int) or isinstance(count, bool) or count < 1 or count > len(FACTS):
        raise ValueError(f"count must be between 1 and {len(FACTS)}")
    output_dir = Path(output_dir)
    manifest = _load_source_manifest(output_dir)
    sources = {item["sourceRecordId"]: item for item in manifest["selectedRecords"]}
    facts = FACTS[:count]
    referenced_source_ids = {fact.source_record_id for fact in facts}
    if not referenced_source_ids.issubset(sources):
        raise ValueError("a case refers to a source absent from the pinned manifest")

    pdf_cache: set[str] = set()
    cases: list[dict[str, Any]] = []
    for fact in facts:
        source = sources[fact.source_record_id]
        _validate_query(fact, source)
        text_bytes = _source_bytes(output_dir, source, "sourceTextPath", "sourceTextSha256")
        text = text_bytes.decode("utf-8", errors="strict")
        excerpt = _extract_excerpt(text, fact)
        text_hash = hashlib.sha256(text_bytes).hexdigest()
        if fact.source_record_id not in pdf_cache:
            _source_bytes(output_dir, source, "sourcePdfPath", "sourcePdfSha256")
            pdf_cache.add(fact.source_record_id)

        evidence = {
            "url": source["officialUrl"],
            "title": source["title"],
            "retrievedAtUTC": source["retrievedAtUTC"],
            "publishedAt": source["publishedAt"],
            "sourceRecordId": fact.source_record_id,
            "upstreamRevision": UPSTREAM_REVISION,
            "license": "unknown",
            "rawSha256": text_hash,
            "rawPath": source["sourceTextPath"],
            "excerpt": excerpt,
        }
        case = {
            "schemaVersion": SCHEMA_VERSION,
            "id": fact.case_id,
            "categoryId": CATEGORY_ID,
            "query": fact.query,
            "temporal": {
                "kind": "version",
                "precision": "version",
                "version": source["version"],
            },
            "gold": {
                "answer": fact.value_token,
                "value": fact.value,
                "acceptedAnswers": [fact.value_token],
                "units": fact.units,
                **({"currency": fact.currency} if fact.currency is not None else {}),
            },
            "evidence": [evidence],
            "derivation": {
                "sourceFamily": SOURCE_FAMILY,
                "generatorVersion": GENERATOR_VERSION,
                "questionType": fact.question_type,
            },
        }
        cases.append(case)

    ids = [case["id"] for case in cases]
    query_keys = [_normalize(case["query"]) for case in cases]
    if len(ids) != len(set(ids)) or len(query_keys) != len(set(query_keys)):
        raise ValueError("finance category contains duplicate ids or normalized queries")
    if count == 50:
        source_ids = {case["evidence"][0]["sourceRecordId"] for case in cases}
        question_types = {case["derivation"]["questionType"] for case in cases}
        if len(source_ids) < 25 or len(question_types) < 3:
            raise ValueError("finance category does not meet its source/type diversity floor")
    atomic_write_bytes(
        output_dir / "sources.md",
        sources_markdown(output_dir, cases).encode("utf-8"),
    )
    return cases


def _markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _paragraph(*parts: str) -> str:
    return " ".join(part.strip() for part in parts)


def sources_markdown(output_dir: Path, cases: list[dict[str, Any]]) -> str:
    """Render provenance, selection counts, concentration, and limits for review."""
    manifest = _load_source_manifest(output_dir)
    source_counts = Counter(case["evidence"][0]["sourceRecordId"] for case in cases)
    question_counts = Counter(case["derivation"]["questionType"] for case in cases)
    selected = [
        source
        for source in manifest["selectedRecords"]
        if source["sourceRecordId"] in source_counts
    ]
    selected.sort(
        key=lambda source: (
            source["company"],
            source["publishedAt"],
            source["sourceRecordId"],
        )
    )
    upstream_documents = next(
        item["records"]
        for item in manifest["upstreamData"]
        if item["path"].endswith("financebench_document_information.jsonl")
    )
    upstream_qa = next(
        item["records"]
        for item in manifest["upstreamData"]
        if item["path"].endswith("financebench_open_source.jsonl")
    )
    company_counts = Counter(source["company"] for source in selected)
    lines = [
        "# Finance query/gold sources",
        "",
        "## Benchmark fit",
        "",
        _paragraph(
            "These are standalone direct-search questions for one answer-bearing issuer release.",
            "Each asks for one historical field and gives the issuer plus a report period or",
            "release date. They exercise earnings, revenue and sales, per-share results,",
            "comparable-sales changes, and company-issued guidance. The 50 questions were",
            "constructed from primary release text; no FinanceBench question/answer pair was",
            "reused.",
        ),
        "",
        "## Candidate selection and exclusions",
        "",
        _paragraph(
            f"The pinned FinanceBench catalog contains {upstream_documents} document-information",
            f"records and {upstream_qa} QA rows. This category selected {len(selected)} official",
            f"issuer-release records and {len(cases)} literal facts. The other",
            f"{upstream_documents - len(selected)} catalog records were outside this slice; the",
            "upstream QA rows were all excluded from query/gold reuse. The source snapshot",
            "does not include an itemized rejection ledger, so those unselected records are not",
            "characterized as individually reviewed or rejected.",
        ),
        "",
        _paragraph(
            "Selection criteria were: an issuer-hosted or issuer-authorized public earnings",
            "release; an answer explicitly present in the source text; a clearly scoped issuer,",
            "metric, and fiscal/reporting period; and an unambiguous unit or table column. Facts",
            "requiring arithmetic, hidden context, unsupported normalization, or a derived",
            "answer were excluded from case construction.",
        ),
        "",
        "## Construction method",
        "",
        _paragraph(
            "The hand-authored fact catalog names each entity, period, field, exact source value",
            "token, unit token, and source-line anchor. The collector checks the pinned source",
            "manifest, PDF/text SHA-256 values, UTF-8 decoding, literal excerpt membership, value",
            "parsing, requested table column, query scope, unique IDs, and normalized-query",
            "uniqueness before emitting strict query-gold records. Gold answers preserve the",
            "source's literal value token; numeric `gold.value` is a separately parsed",
            "representation. No arithmetic or language-model answer generation is used.",
        ),
        "",
        "## License and source revision/snapshot",
        "",
        _paragraph(
            f"Upstream repository: [{manifest['upstreamRepository']}]",
            f"({manifest['upstreamRepository']}) at commit `{manifest['upstreamRevision']}`",
            f"(commit date `{manifest['upstreamCommitDate']}`). The pinned upstream license",
            f"is `{manifest['sourceLicense']}`; item-level release license metadata is also",
            f"`{selected[0]['license'] if selected else 'unknown'}`. No license terms are inferred",
            f"from public accessibility. Manifest SHA-256: `{MANIFEST_SHA256}`. Each original",
            "PDF and UTF-8 text snapshot has its own SHA-256 in the private source manifest.",
        ),
        "",
        _paragraph(
            "The collector is offline and requires `raw/source_manifest.json` plus every",
            "referenced `raw/*.pdf` and `raw/*.txt` snapshot under this category directory.",
            "The `results/` tree is gitignored, so a clean clone does not contain them. Preserve",
            "or restore this exact private `raw/` directory before running",
            "`python -m query_gold.categories.finance --output-dir <category-directory>` from",
            "the `python/` project with its `src` package installed. This repository contains no",
            "acquisition or PDF-to-text bootstrap; a fresh PDF download alone does not",
            "reproduce the pinned text bytes.",
        ),
        "",
        "## Source and question-type concentration",
        "",
        _paragraph(
            f"The {len(cases)} cases use {len(selected)} release records across",
            f"{len(company_counts)} issuers. Source-record case counts range from",
            f"{min(source_counts.values(), default=0)} to",
            f"{max(source_counts.values(), default=0)}. Question-type counts:",
            ", ".join(f"`{name}` {count}" for name, count in sorted(question_counts.items())) + ".",
        ),
        "",
        "| Issuer | Published | Fiscal period | Source record | Cases | Answer-bearing page |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for source in selected:
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_cell(source["company"]),
                    _markdown_cell(source["publishedAt"]),
                    _markdown_cell(source["version"]),
                    f"`{source['sourceRecordId']}`",
                    str(source_counts[source["sourceRecordId"]]),
                    f"[{_markdown_cell(source['title'])}]({source['officialUrl']})",
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Manual sample review",
            "",
            _paragraph(
                "Automated source-text line and excerpt checks cover all 50 cases, including",
                "period headers, table columns, units, and literal answer tokens. Manual sampling",
                "covered multiple issuers and metric families, including table-based",
                "quarter-versus-year-to-date rows and EPS guidance labels. This is a text-snapshot",
                "review, not a visual audit of every PDF page or a live search-results review.",
            ),
            "",
            "## Normal public answer-bearing pages",
            "",
            _paragraph(
                "The table above links each case's normal public answer-bearing issuer release,",
                "generally a public PDF hosted on the issuer's investor-relations CDN. The PDF is",
                "the cited page; FinanceBench QA/document metadata are selection provenance only",
                "and are not evidence for any answer.",
            ),
            "",
            "## Direct-search discoverability limitations",
            "",
            _paragraph(
                "No live search engine was queried. These citations show where an answer appears,",
                "not whether the page is indexed, ranked, or returned in the first five results",
                "for a natural query. Investor-relations PDFs may have weaker indexing or may be",
                "superseded by later releases. The questions assess answer-bearing-source fit, not",
                "top-five search success.",
            ),
            "",
            "## Representativeness gaps",
            "",
            _paragraph(
                "This is a narrow, non-random slice of 12 U.S. publicly traded issuers and",
                "2022-2024 release periods. It overrepresents earnings-release highlights and",
                "per-share/revenue metrics; it does not cover a broad sample of 10-K/10-Q",
                "financial-statement line items, financial ratios, banks, insurers, private",
                "companies, non-U.S. reporting regimes, or multiple currencies. Source and",
                "question mix should not be generalized to corporate finance as a whole.",
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _default_output_dir() -> Path:
    repository_root = Path(__file__).resolve().parents[4]
    return (
        repository_root
        / "results/query-gold-curation/first-five-v1/categories/01_earnings_corporate_finance"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=_default_output_dir())
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args(argv)
    cases = collect(args.output_dir, args.count)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destination = args.output_dir / "cases.jsonl"
    atomic_write_jsonl(destination, cases)
    print(f"wrote {len(cases)} finance query/gold cases to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
