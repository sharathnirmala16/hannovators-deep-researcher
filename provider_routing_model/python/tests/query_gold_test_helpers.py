"""Synthetic, offline-only fixtures for query/gold framework tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from query_gold.io import atomic_write_jsonl
from query_gold.models import QueryGoldCase
from query_gold.validation import CATEGORY_IDS

SOURCES_NOTE = """# Benchmark fit
Direct search-input relevance and benchmark fit.

## Rejected candidates
Rejected stale, vague, and API-only candidates.

## Construction method
Constructed from an answer-bearing source excerpt.

## License and source revision/snapshot
License recorded; revision/snapshot retained.

## Source and question-type concentration
Source concentration and question type mix reviewed.

## Manual sample review
Manual sample review completed for this synthetic fixture.

## Representativeness gaps
Representativeness limitations documented.

## Public answer-bearing page
Normal public page cited with the explicit answer.

## Search discoverability limitations
Search discoverability limitations are not a top-five guarantee.
"""


def make_case(category: str, index: int, output_dir: Path) -> dict[str, Any]:  # noqa: C901
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    record_id = f"record-{index:03d}"
    if category == "01_earnings_corporate_finance":
        entity = f"Acme{index:03d} Corp"
        query = f"What revenue did {entity} report for fiscal year 2025?"
        answer = "USD 10 million"
        excerpt = f"{entity} reported revenue of USD 10 million for fiscal year 2025."
        temporal = {
            "kind": "period",
            "precision": "year",
            "periodStart": "2025",
            "periodEnd": "2025",
        }
        gold = {
            "answer": answer,
            "value": 10_000_000,
            "acceptedAnswers": [],
            "units": "USD",
            "currency": "USD",
        }
        url = f"https://example.org/finance/{record_id}/2025-annual-report.html"
        family = "official_annual_filings"
        question_type = ("revenue", "cash_flow", "capital_structure")[index % 3]
    elif category == "02_biomedical_clinical_trials":
        entity = f"NCT{10000000 + index:08d}"
        query = f"What was the primary completion date for study {entity} in 2025?"
        answer = "2025-06-30"
        excerpt = f"The primary completion date for study {entity} was 2025-06-30."
        temporal = {"kind": "as_of", "precision": "year", "asOf": "2025"}
        gold = {"answer": answer, "acceptedAnswers": []}
        url = f"https://clinicaltrials.gov/study/{entity}"
        family = "public_trial_registry"
        question_type = ("completion_date", "trial_status", "primary_endpoint")[index % 3]
    elif category == "03_code_api_documentation":
        entity = f"SampleLib{index:03d}"
        query = f"What default timeout does {entity} use in version 1.2.0?"
        answer = "30 seconds"
        excerpt = f"In {entity} version 1.2.0, the default timeout is 30 seconds."
        temporal = {"kind": "version", "precision": "version", "version": "1.2.0"}
        gold = {"answer": answer, "acceptedAnswers": [], "units": "seconds"}
        url = f"https://docs.example.org/{entity.casefold()}/1.2.0/configuration.html"
        family = "versioned_official_documentation"
        question_type = ("default_value", "parameter", "return_contract")[index % 3]
    elif category == "04_venture_capital_funding_ma":
        entity = f"Acme Ventures{index:03d}"
        query = f"What funding round did {entity} announce in 2025?"
        answer = "Series B"
        excerpt = f"{entity} announced a Series B funding round in 2025."
        temporal = {"kind": "event", "precision": "year", "date": "2025"}
        gold = {"answer": answer, "acceptedAnswers": []}
        url = f"https://news.example.org/venture/{record_id}/funding-announcement.html"
        family = "company_press_release"
        question_type = ("funding_round", "transaction_date", "valuation")[index % 3]
    elif category == "05_government_courts_legal":
        entity = f"Example Safety Act {index:03d}"
        query = f"What effective date did Section 12 of the {entity} specify in 2025?"
        answer = "2025-01-01"
        excerpt = f"Section 12 of the {entity} took effect on 2025-01-01."
        temporal = {"kind": "event", "precision": "year", "date": "2025"}
        gold = {"answer": answer, "acceptedAnswers": []}
        url = f"https://www.congress.example.gov/acts/{record_id}/section-12.html"
        family = "official_legislation"
        question_type = ("effective_date", "statutory_text", "court_holding")[index % 3]
    elif category == "06_hardware_product_specifications":
        entity = f"ProcessorModel{index:03d}"
        query = f"What is the base clock frequency of {entity} in version 1.0?"
        answer = "3.5 GHz"
        excerpt = f"The base clock frequency of {entity} is 3.5 GHz in version 1.0."
        temporal = {"kind": "version", "precision": "version", "version": "1.0"}
        gold = {"answer": answer, "acceptedAnswers": [], "units": "GHz"}
        url = f"https://specs.example.org/hardware/{record_id}/specifications.html"
        family = "hardware_spec_sheet"
        question_type = ("clock_frequency", "tdp_rating", "pinout_specification")[index % 3]
    elif category == "07_static_mathematics_stem":
        entity = f"ConstantAlpha{index:03d}"
        query = f"What is the analytical constant value for {entity}?"
        answer = "1.4142"
        excerpt = f"The analytical constant value for {entity} is 1.4142."
        temporal = {"kind": "immutable", "precision": "immutable"}
        gold = {"answer": answer, "acceptedAnswers": [], "value": 1.4142}
        url = f"https://mathworld.example.org/constants/{record_id}.html"
        family = "mathematical_reference"
        question_type = ("analytical_constant", "theorem_bound", "physical_law")[index % 3]
    elif category == "08_sports_box_scores_game_stats":
        entity = f"PlayerAlpha{index:03d}"
        query = f"How many points did {entity} score in the game on 2025-05-10?"
        answer = "28 points"
        excerpt = f"In the game on 2025-05-10, {entity} scored 28 points."
        temporal = {"kind": "event", "precision": "day", "date": "2025-05-10"}
        gold = {"answer": answer, "acceptedAnswers": [], "units": "points"}
        url = f"https://stats.example.org/games/{record_id}/boxscore.html"
        family = "official_box_score"
        question_type = ("player_points", "game_box_score", "match_penalties")[index % 3]
    elif category == "09_real_estate_land_registries":
        entity = f"ParcelID{index:03d}"
        query = f"What was the assessed value of {entity} for tax year 2025?"
        answer = "USD 350,000"
        excerpt = f"For tax year 2025, the assessed value of {entity} was USD 350,000."
        temporal = {
            "kind": "period",
            "precision": "year",
            "periodStart": "2025",
            "periodEnd": "2025",
        }
        gold = {"answer": answer, "acceptedAnswers": [], "units": "USD", "currency": "USD"}
        url = f"https://registry.example.gov/parcels/{record_id}/valuation.html"
        family = "property_tax_registry"
        question_type = ("assessed_value", "sale_price", "lot_dimensions")[index % 3]
    elif category == "10_academic_literature_citations":
        entity = f"PaperCitation{index:03d}"
        query = f"Who was the primary author of the research paper {entity} in 2025?"
        answer = "Alice Smith"
        excerpt = (
            f"The primary author of the research paper {entity} published in 2025 was Alice Smith."
        )
        temporal = {"kind": "event", "precision": "year", "date": "2025"}
        gold = {"answer": answer, "acceptedAnswers": []}
        url = f"https://arxiv.example.org/abs/{record_id}.html"
        family = "academic_repository"
        question_type = ("primary_author", "publication_date", "benchmark_score")[index % 3]
    elif category == "11_cybersecurity_vulnerability_tracking":
        entity = f"CVE-2025-{10000 + index:05d}"
        query = f"What was the CVSS base score assigned to {entity} in 2025?"
        answer = "9.8"
        excerpt = f"In 2025, vulnerability {entity} was assigned a CVSS base score of 9.8."
        temporal = {"kind": "event", "precision": "year", "date": "2025"}
        gold = {"answer": answer, "acceptedAnswers": [], "value": 9.8}
        url = f"https://nvd.example.gov/vuln/detail/{record_id}.html"
        family = "vulnerability_database"
        question_type = ("cvss_score", "cve_identifier", "advisory_bulletin")[index % 3]
    elif category == "12_municipal_code_zoning_local_law":
        entity = f"CityZoneOrd{index:03d}"
        query = f"What is the minimum lot size required under zoning ordinance {entity} in 2025?"
        answer = "5000 square feet"
        excerpt = (
            f"Under zoning ordinance {entity} adopted in 2025, "
            "the minimum lot size is 5000 square feet."
        )
        temporal = {"kind": "event", "precision": "year", "date": "2025"}
        gold = {"answer": answer, "acceptedAnswers": [], "units": "square feet"}
        url = f"https://municode.example.gov/codes/{record_id}/zoning.html"
        family = "municipal_code"
        question_type = ("lot_size_ordinance", "building_setback", "parking_minimum")[index % 3]
    elif category == "13_logistics_freight_supply_chain":
        entity = f"Harbor Example{index:03d}"
        query = f"How many TEUs did {entity} handle in calendar year 2025?"
        answer = "10 TEU"
        excerpt = f"{entity} handled 10 TEU in calendar year 2025."
        temporal = {
            "kind": "period",
            "precision": "year",
            "periodStart": "2025",
            "periodEnd": "2025",
        }
        gold = {"answer": answer, "value": 10, "acceptedAnswers": [], "units": "TEU"}
        url = f"https://ports.example.org/throughput/{record_id}/2025.html"
        family = "synthetic_port_statistics"
        question_type = ("container_throughput", "vessel_capacity", "port_telemetry")[index % 3]
    elif category == "14_aerospace_telemetry_records":
        entity = f"Mission Example{index:03d}"
        query = f"What launch telemetry altitude did {entity} record on 2025-06-30?"
        answer = "500 km"
        excerpt = f"On 2025-06-30, {entity} recorded a launch telemetry altitude of 500 km."
        temporal = {"kind": "event", "precision": "day", "date": "2025-06-30"}
        gold = {"answer": answer, "value": 500, "acceptedAnswers": [], "units": "km"}
        url = f"https://missions.example.org/telemetry/{record_id}/2025-06-30.html"
        family = "synthetic_mission_telemetry"
        question_type = ("launch_telemetry", "orbital_altitude", "mission_milestone")[index % 3]
    elif category == "15_cloud_infrastructure_service_pricing":
        entity = f"Example Cloud Service{index:03d}"
        query = f"What cloud API token quota did {entity} document in version 1.2.0?"
        answer = "10,000 tokens per minute"
        excerpt = f"{entity} version 1.2.0 documents a cloud API quota of 10,000 tokens per minute."
        temporal = {"kind": "version", "precision": "version", "version": "1.2.0"}
        gold = {
            "answer": answer,
            "value": 10_000,
            "acceptedAnswers": [],
            "units": "tokens per minute",
        }
        url = f"https://cloud.google.com/fixtures/api/{record_id}/v1.2.0/quotas.html"
        family = "synthetic_cloud_api_documentation"
        question_type = ("token_quota", "api_limit", "service_pricing")[index % 3]
    elif category == "16_art_collectibles_auction_transactions":
        entity = f"Example Artwork{index:03d}"
        query = f"What hammer price did auction house Example sell {entity} for in 2025?"
        answer = "$10,000"
        excerpt = f"Example Artwork{index:03d} sold for a hammer price of $10,000 in 2025."
        temporal = {"kind": "event", "precision": "year", "date": "2025"}
        gold = {"answer": answer, "value": 10_000, "acceptedAnswers": [], "units": "USD"}
        url = f"https://auctions.example.org/lot/{record_id}.html"
        family = "synthetic_auction_catalog"
        question_type = ("hammer_price", "provenance", "catalog_identifier")[index % 3]
    elif category == "17_local_graph_municipal_pois_directory_lookups":
        entity = f"Example Cafe{index:03d}"
        query = f"What health inspection grade did {entity} receive in 2025?"
        answer = "A"
        excerpt = f"Example Cafe{index:03d} received health inspection grade A in 2025."
        temporal = {"kind": "event", "precision": "year", "date": "2025"}
        gold = {"answer": answer, "acceptedAnswers": []}
        url = f"https://city.example.gov/inspection/{record_id}.html"
        family = "synthetic_municipal_registry"
        question_type = ("inspection_grade", "business_registration", "official_address")[index % 3]
    elif category == "18_entertainment_box_office_media_registries":
        entity = f"Example Film{index:03d}"
        query = f"What opening-weekend domestic gross did {entity} earn in 2025?"
        answer = "$1,000,000"
        excerpt = (
            f"Example Film{index:03d} earned an opening-weekend domestic gross of "
            "$1,000,000 in 2025."
        )
        temporal = {"kind": "event", "precision": "year", "date": "2025"}
        gold = {"answer": answer, "value": 1_000_000, "acceptedAnswers": [], "units": "USD"}
        url = f"https://media.example.org/film/{record_id}.html"
        family = "synthetic_media_registry"
        question_type = ("opening_weekend_gross", "chart_position", "production_credit")[index % 3]
    elif category == "19_immigration_visa_bulletins_consular_policies":
        entity = f"Visa Bulletin Example{index:03d}"
        query = f"What priority date did the 2025 visa bulletin list for {entity}?"
        answer = "2025-01-01"
        excerpt = f"The 2025 Visa Bulletin Example{index:03d} lists priority date 2025-01-01."
        temporal = {"kind": "event", "precision": "year", "date": "2025"}
        gold = {"answer": answer, "acceptedAnswers": []}
        url = f"https://travel.state.example.gov/visa-bulletin/{record_id}.html"
        family = "synthetic_immigration_notice"
        question_type = ("priority_date", "consular_fee", "statutory_notice")[index % 3]
    elif category == "20_historical_meteorology_disaster_telemetry":
        entity = f"River Gauge Example{index:03d}"
        query = f"What river gauge annual peak discharge did {entity} record in water year 2025?"
        answer = "10 ft^3/s"
        excerpt = f"{entity} recorded annual peak discharge 10 ft^3/s in water year 2025."
        temporal = {"kind": "event", "precision": "year", "date": "2025"}
        gold = {"answer": answer, "acceptedAnswers": [], "units": "ft^3/s"}
        url = f"https://water.example.gov/gauges/{record_id}/2025.html"
        family = "synthetic_gauge_record"
        question_type = ("annual_peak_flow", "peak_height", "crest_date")[index % 3]
    elif category == "21_gaming_software_release_patch_telemetry":
        entity = f"Example Game{index:03d}"
        query = f"What cooldown adjustment did the official game patch 1.2.0 list for {entity}?"
        answer = "10 seconds"
        excerpt = (
            f"The official game patch 1.2.0 lists a cooldown adjustment of 10 seconds for {entity}."
        )
        temporal = {"kind": "version", "precision": "version", "version": "1.2.0"}
        gold = {"answer": answer, "acceptedAnswers": [], "units": "seconds"}
        url = f"https://game.example.com/patch-notes/1.2.0/{record_id}.html"
        family = "synthetic_game_patch_notes"
        question_type = ("cooldown_adjustment", "base_stat", "balance_change")[index % 3]
    elif category == "22_consumer_ecommerce_msrp_recall_notices":
        entity = f"Example Consumer Product{index:03d}"
        query = f"What CPSC recall campaign number was assigned to {entity} in the 2025 notice?"
        answer = f"25-{index:03d}"
        excerpt = f"The CPSC recall campaign number for {entity} is {answer}."
        temporal = {"kind": "event", "precision": "year", "date": "2025"}
        gold = {"answer": answer, "acceptedAnswers": []}
        url = f"https://www.cpsc.gov/Recalls/2025/{record_id}.html"
        family = "synthetic_consumer_recall"
        question_type = ("recall_id", "units_recalled", "manufacturer_model")[index % 3]
    elif category == "23_executive_directory_corporate_leadership":
        entity = f"Example Corporation{index:03d}"
        query = f"Which executive did {entity} appoint in its SEC Form 8-K filed on 2025-06-30?"
        answer = f"Person Example{index:03d}"
        excerpt = f"{answer} was appointed to an executive position at {entity} on 2025-06-30."
        temporal = {"kind": "event", "precision": "day", "date": "2025-06-30"}
        gold = {"answer": answer, "acceptedAnswers": []}
        url = f"https://www.sec.gov/Archives/edgar/data/{index:010d}/{record_id}.htm"
        family = "synthetic_sec_leadership_filing"
        question_type = (
            "executive_appointment",
            "executive_departure",
            "board_transition",
        )[index % 3]
    elif category == "24_standards_rfcs_technical_specifications":
        entity = f"RFC {9000 + index}"
        query = f"What publication month and year appear in the header of {entity}?"
        answer = "June 2025"
        excerpt = f"Request for Comments: {9000 + index}  {answer}"
        temporal = {
            "kind": "immutable",
            "precision": "immutable",
            "immutableReason": "RFC document identifier and publication date are fixed.",
        }
        gold = {"answer": answer, "acceptedAnswers": []}
        url = f"https://www.rfc-editor.org/rfc/rfc{9000 + index}.txt"
        family = "synthetic_rfc_document"
        question_type = ("publication_month", "rfc_number", "document_title")[index % 3]
    else:
        raise ValueError("unknown synthetic category")

    raw_path = raw_dir / f"{record_id}.txt"
    raw_bytes = excerpt.encode("utf-8")
    raw_path.write_bytes(raw_bytes)
    evidence = {
        "url": url,
        "title": f"Official answer-bearing record {record_id} for 2025",
        "retrievedAtUTC": "2026-10-17T12:00:00Z",
        "publishedAt": "2025-06",
        "effectiveDate": "2025-06-30",
        "sourceRecordId": record_id,
        "upstreamRevision": "v1.2.0"
        if category == "03_code_api_documentation"
        else "revision-2025",
        "license": "Synthetic test fixture",
        "rawSha256": hashlib.sha256(raw_bytes).hexdigest(),
        "rawPath": raw_path.relative_to(output_dir).as_posix(),
        "excerpt": excerpt,
    }
    return {
        "schemaVersion": "query-gold/v1",
        "id": f"{category[:2]}-{index:03d}",
        "categoryId": category,
        "query": query,
        "temporal": temporal,
        "gold": gold,
        "evidence": [evidence],
        "derivation": {
            "sourceFamily": family,
            "generatorVersion": "synthetic-test/1",
            "questionType": question_type,
        },
    }


def make_cases(
    root: Path,
    *,
    count_per_category: int = 5,
    categories: tuple[str, ...] = CATEGORY_IDS,
    write_files: bool = True,
) -> list[QueryGoldCase]:
    cases: list[QueryGoldCase] = []
    for category in categories:
        output_dir = root / "categories" / category
        output_dir.mkdir(parents=True, exist_ok=True)
        rows = [make_case(category, index, output_dir) for index in range(count_per_category)]
        if write_files:
            atomic_write_jsonl(output_dir / "cases.jsonl", rows)
            (output_dir / "sources.md").write_text(SOURCES_NOTE, encoding="utf-8")
        cases.extend(QueryGoldCase.model_validate(row, strict=True) for row in rows)
    return cases
