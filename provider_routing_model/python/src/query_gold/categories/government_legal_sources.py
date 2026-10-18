"""Source and review notes for government/legal query-gold artifacts."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from query_gold.io import read_json


def _paragraph(*lines: str) -> str:
    """Join wrapped source-note lines into a single Markdown paragraph."""
    return " ".join(line.strip() for line in lines)


def sources_markdown(
    cases: list[dict[str, Any]], ledger: list[dict[str, Any]], output_dir: Path
) -> str:
    family_counts = Counter(case["derivation"]["sourceFamily"] for case in cases)
    question_counts = Counter(case["derivation"]["questionType"] for case in cases)
    source_counts = Counter(item["sourceRecordId"] for case in cases for item in case["evidence"])
    source_rows: dict[str, dict[str, Any]] = {}
    source_families_by_url: dict[str, str] = {}
    timestamp_bases: Counter[str] = Counter()
    for case in cases:
        evidence = case["evidence"][0]
        source_families_by_url[evidence["url"]] = case["derivation"]["sourceFamily"]
        row = source_rows.setdefault(
            evidence["url"],
            {
                "sourceRecordIds": set(),
                "family": case["derivation"]["sourceFamily"],
                "cases": 0,
            },
        )
        row["sourceRecordIds"].add(evidence["sourceRecordId"])
        row["cases"] += 1
    table = [
        "| Page record IDs | Family | Cases | Public answer page |",
        "|---|---|---:|---|",
    ]
    for url, row in sorted(source_rows.items()):
        record_ids = ", ".join(f"`{source_id}`" for source_id in sorted(row["sourceRecordIds"]))
        table.append(f"| {record_ids} | `{row['family']}` | {row['cases']} | <{url}> |")
    concentration = ", ".join(
        f"`{source_id}` {total}" for source_id, total in source_counts.most_common(8)
    )
    families = ", ".join(f"`{name}` {total}" for name, total in sorted(family_counts.items()))
    question_types = ", ".join(
        f"`{name}` {total}" for name, total in sorted(question_counts.items())
    )
    for case in cases:
        evidence = case["evidence"][0]
        metadata_path = output_dir / f"{evidence['rawPath']}.metadata.json"
        metadata = read_json(metadata_path)
        if isinstance(metadata, dict):
            timestamp_bases[str(metadata.get("retrievedAtBasis", "unknown"))] += 1
    federal_documents = sum(
        family == "federal_register_rule_document" for family in source_families_by_url.values()
    )
    court_documents = sum(
        family == "washington_supreme_court_opinion_sheet"
        for family in source_families_by_url.values()
    )
    public_law_documents = sum(
        family == "govinfo_public_law" for family in source_families_by_url.values()
    )
    statute_section_records = sum(
        case["derivation"]["sourceFamily"] == "govinfo_public_law" for case in cases
    )
    timestamp_summary = ", ".join(
        f"`{basis}` {total}" for basis, total in sorted(timestamp_bases.items())
    )
    sections = [
        "# Government, courts, and legal query-gold curation",
        "",
        "## Benchmark fit",
        "",
        _paragraph(
            "This is a constructed direct-search set from dated U.S. federal rule pages,",
            "enacted public-law sections, and Washington Supreme Court opinion information",
            "sheets. Queries name the legal entity or docket, the field being requested, and",
            "the published, enacted, or filed date. Court questions ask about one identified",
            "judicial decision; they do not ask for the current state of law or imply that a",
            "past holding remains controlling.",
        ),
        "",
        "## Candidate rejection and construction",
        "",
        _paragraph(
            "The pinned Federal Register candidate table contained 30 answerable records.",
            "Twenty were retained across distinct fields; 10 repetitive CFR-part, RIN,",
            "docket, and effective-date candidates were left out after those field types had",
            "adequate coverage. The Medicare Advantage rule question uses its page-listed",
            "docket identifiers because the GovInfo HTML does not explicitly state the",
            "Federal Register citation in canonical citation form. Twenty statutory facts",
            "were selected across 12 sections of two enacted public laws, and 10 Washington",
            "Supreme Court opinion sheets were selected for decision-specific majority-author",
            "facts. Candidate rejection criteria were proposed-rule status, API-only evidence,",
            "missing or ambiguous entity, date, docket, citation, or field, mismatch between",
            "publication, effective, applicability, or compliance date, answer absent from the",
            "normal public page, unsupported statutory units or currency, duplicate query, or",
            "compound or derived question. Retained records are fixed source-to-field mappings,",
            "not generated answer snippets.",
        ),
        "",
        "## License and source revision policy",
        "",
        _paragraph(
            "Federal Register and GovInfo HTML is recorded as public domain U.S. Government",
            "work under United States Code title 17, section 105. Washington court information",
            "sheets are official public records; no reuse license is asserted. Federal Register",
            "JSON snapshots select and cross-check structured fields only. Every selected rule",
            "case cites its corresponding GovInfo-hosted Federal Register issue HTML page and",
            "caches an answer-bearing excerpt. The canonical Federal Register document pages",
            "redirected this collector to an anti-bot interstitial, so the accessible GovInfo",
            "pages provide the cited HTML evidence. Each cited public page has a metadata",
            "sidecar with its URL, byte SHA-256, and retrieval timestamp basis. Fresh HTTP",
            "responses use response-received time; earlier successful responses are tied to the",
            "logged URL and response digest with their request-start time. Inherited Federal",
            "Register JSON used only for structured-field selection has no verified original",
            "retrieval time. Public-law revisions are pinned by public-law number, section, and",
            "enactment date. Court records are pinned by docket and filing date. An information",
            "sheet's majority-author field is case metadata, not a statement of current law.",
        ),
        "",
        "## Source and question-type concentration",
        "",
        _paragraph(
            f"Cases by source family: {families}.",
            f"Distinct sourceRecordIds: {len(source_counts)}; maximum cases on one source",
            f"record: {max(source_counts.values(), default=0)}.",
            f"Highest source counts: {concentration}.",
            f"Question types: {question_types}.",
        ),
        _paragraph(
            f"The {len(source_rows)} public URLs resolve to {federal_documents} Federal",
            f"Register documents, {court_documents} court information sheets, and",
            f"{public_law_documents} enacted public-law documents.",
            f"The {statute_section_records} statutory sourceRecordIds identify sections",
            "within the two public laws; they are not separate publisher documents.",
            "Retrieval timestamp bases across the cited evidence entries:",
            f"{timestamp_summary}.",
        ),
        "",
        "## Normal public answer-bearing pages",
        "",
        _paragraph(
            "The table lists every distinct public HTML page used as evidence. GovInfo's",
            "Federal Register issue pages contain rule abstracts, identifiers, and dates.",
            "GovInfo public-law pages contain the cited statute sections. Washington Supreme",
            "Court pages identify the case, docket, filing date, and majority author.",
        ),
        "",
        *table,
        "",
        "## Manual sample review",
        "",
        _paragraph(
            "Manual sample review checked the Federal Register effective date separately",
            "from publication date, a page-listed docket identifier, the EPA PFOA maximum",
            "contaminant level and ng/L units, a public-law joint-return income threshold and",
            "annual tax-year context, and two Washington Supreme Court docket sheets. Answers",
            "and relevant dates or units appear in the cited page excerpts. Statutes are",
            "versioned to enacted public-law sections and court records to filing dates.",
        ),
        _paragraph(
            "Category validation found 0 errors and 30 `query_metric_or_field_unclear`",
            "heuristic warnings. The generic detector does not recognize many legal-field",
            "nouns. These remain review flags; sample review confirmed the inspected questions",
            "identify one source field.",
        ),
        "",
        "## Direct-search discoverability limitations",
        "",
        _paragraph(
            "These sources use stable Federal Register document numbers, public-law sections,",
            "case names, and court dockets that can support direct web search. The data do not",
            "establish a search engine's ranking or guarantee that an answer page appears in",
            "a top-result set. The canonical Federal Register site presented an anti-bot",
            "redirect during collection; direct-search discoverability of the equivalent",
            "GovInfo pages was not measured. Washington docket sheets answer case-metadata",
            "questions; they are not a representative sample of judicial holdings.",
        ),
        "",
        "## Representativeness gaps",
        "",
        _paragraph(
            "Coverage is limited to U.S. federal rules, two public laws (the Inflation",
            "Reduction Act of 2022 and FAA Reauthorization Act of 2024), and 10 Washington",
            "Supreme Court cases filed in 2024. It omits other states and countries, federal",
            "and state trial courts, most court holdings, local ordinances, agency",
            "adjudications, and current-law questions. Repeated tax-credit provisions make",
            "statutory coverage denser than other legal subfamilies.",
        ),
        "",
        _paragraph(
            f"The collector logged {len(ledger)} physical public-source HTTP attempts,",
            "including redirects, retries, and errors. No paid retrieval provider or",
            "benchmark run was used.",
        ),
        "",
    ]
    return "\n".join(sections)
