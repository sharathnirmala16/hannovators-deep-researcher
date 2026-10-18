"""Focused offline checks for legal source selection and evidence boundaries."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from query_gold.categories import government_legal
from query_gold.categories.government_legal_facts import (
    FEDERAL_FACTS,
    STATUTE_FACTS,
    CourtFactSpec,
    FederalFactSpec,
    StatuteFactSpec,
)


class GovernmentLegalCurationTests(unittest.TestCase):
    def _api_record(self) -> dict[str, object]:
        return {
            "document_number": "2024-00001",
            "type": "Rule",
            "action": "Final Rule",
            "title": "Example Rule",
            "publication_date": "2024-01-02",
            "effective_on": "2024-02-03",
            "dates": "This rule is effective on February 3, 2024.",
            "abstract": "The rule has an example public answer.",
            "docket_ids": ["EOIR Docket No. EOIR 20-0010"],
            "regulation_id_numbers": ["1234-AB56"],
            "cfr_references": [{"title": 16, "part": 310}],
            "citation": "89 FR 12345",
            "html_url": (
                "https://www.federalregister.gov/documents/2024/01/02/2024-00001/example-rule"
            ),
        }

    def _page(self, body: str, title: str = "Example Rule") -> bytes:
        return (
            f"<html><head><title>{title}</title></head><body><h1>{title}</h1>{body}</body></html>"
        ).encode()

    def _write_metadata(self, source: Path, url: str, content: bytes) -> None:
        metadata = {
            "url": url,
            "rawSha256": hashlib.sha256(content).hexdigest(),
            "retrievedAtUTC": "2026-10-17T12:00:00Z",
            "retrievedAtBasis": "fixture",
        }
        source.with_name(f"{source.name}.metadata.json").write_text(
            json.dumps(metadata), encoding="utf-8"
        )

    def test_effective_date_comes_from_labeled_dates_field(self) -> None:
        record = self._api_record()
        spec = FederalFactSpec(
            id="fixture-effective-date",
            document_number="2024-00001",
            question_type="rule_effective_date",
            mode="effective_date",
            prompt="what effective date does the 2024 Example Rule state?",
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "page.html"
            page = self._page("<p>This rule is effective on February 3, 2024.</p>")
            source.write_bytes(page)
            self._write_metadata(
                source,
                "https://www.govinfo.gov/content/pkg/FR-2024-01-02/html/2024-00001.htm",
                page,
            )
            case = government_legal._fr_fact(
                spec,
                "raw/federal-register-pages/2024-00001.html",
                json.dumps(record).encode("utf-8"),
                page,
                source,
            )
        self.assertEqual(case["gold"]["answer"], "February 3, 2024")
        self.assertIn("2024-01-02", case["query"])
        self.assertEqual(case["evidence"][0]["publishedAt"], "2024-01-02")
        self.assertEqual(case["evidence"][0]["effectiveDate"], "2024-02-03")

    def test_publication_date_cannot_substitute_for_missing_effective_date(self) -> None:
        record = self._api_record()
        record["effective_on"] = None
        record["dates"] = "This rule was published on February 3, 2024."
        spec = FederalFactSpec(
            id="fixture-wrong-date-kind",
            document_number="2024-00001",
            question_type="rule_effective_date",
            mode="effective_date",
            prompt="what effective date does the 2024 Example Rule state?",
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "page.html"
            page = self._page("<p>This rule was published on February 3, 2024.</p>")
            source.write_bytes(page)
            self._write_metadata(
                source,
                "https://www.govinfo.gov/content/pkg/FR-2024-01-02/html/2024-00001.htm",
                page,
            )
            with self.assertRaisesRegex(ValueError, "effective_on must be"):
                government_legal._fr_fact(
                    spec,
                    "raw/federal-register-pages/2024-00001.html",
                    json.dumps(record).encode("utf-8"),
                    page,
                    source,
                )

    def test_docket_identifier_and_federal_register_citation_use_separate_fields(self) -> None:
        record = self._api_record()
        page = self._page(
            "<p>Docket: EOIR Docket No. EOIR 20-0010</p>"
            "<p>Federal Register citation: 89 FR 12345</p>"
        )
        docket_spec = FederalFactSpec(
            id="fixture-docket",
            document_number="2024-00001",
            question_type="rule_docket_identifier",
            mode="docket",
            prompt="what docket number does DOJ list for the 2024 Example Rule?",
            expected="EOIR Docket No. EOIR 20-0010",
        )
        citation_spec = FederalFactSpec(
            id="fixture-citation",
            document_number="2024-00001",
            question_type="rule_federal_register_citation",
            mode="citation",
            prompt="what Federal Register citation identifies the 2024 Example Rule?",
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "page.html"
            source.write_bytes(page)
            self._write_metadata(
                source,
                "https://www.govinfo.gov/content/pkg/FR-2024-01-02/html/2024-00001.htm",
                page,
            )
            api_bytes = json.dumps(record).encode("utf-8")
            docket = government_legal._fr_fact(
                docket_spec, "raw/page.html", api_bytes, page, source
            )
            citation = government_legal._fr_fact(
                citation_spec, "raw/page.html", api_bytes, page, source
            )
        self.assertEqual(docket["gold"]["answer"], "EOIR Docket No. EOIR 20-0010")
        self.assertEqual(citation["gold"]["answer"], "89 FR 12345")
        self.assertNotEqual(docket["gold"]["answer"], citation["gold"]["answer"])

    def test_proposed_rule_is_not_accepted_as_a_final_rule(self) -> None:
        record = self._api_record()
        record["action"] = "Proposed Rule"
        spec = FederalFactSpec(
            id="fixture-proposed-rule",
            document_number="2024-00001",
            question_type="rule_effective_date",
            mode="effective_date",
            prompt="what effective date does the 2024 Example Rule state?",
        )
        with self.assertRaisesRegex(ValueError, "proposed rules are not eligible"):
            government_legal._rule_context(
                spec,
                {key: (value, json.dumps({key: value})) for key, value in record.items()},
            )

    def test_numeric_statute_requires_units_supported_by_the_section(self) -> None:
        source = (
            "The amount of the credit allowed under this section shall not exceed "
            "$4,000 per vehicle."
        )
        missing_units = StatuteFactSpec(
            id="fixture-statute-units",
            law_key="ira",
            section="13402",
            question_type="statutory_credit_cap",
            prompt="what per-vehicle credit cap applies?",
            answer="$4,000",
            support="$4,000",
            value=4000,
            currency="USD",
        )
        with self.assertRaisesRegex(ValueError, "require explicit measurement units"):
            government_legal._validate_statute_fact(missing_units, source, "117-169")

        correct_units = replace(missing_units, units="USD per vehicle")
        government_legal._validate_statute_fact(correct_units, source, "117-169")
        wrong_units = replace(missing_units, units="USD per mile")
        with self.assertRaisesRegex(ValueError, "units are not supported"):
            government_legal._validate_statute_fact(wrong_units, source, "117-169")

    def test_cached_primary_html_is_the_evidence_source(self) -> None:
        spec = government_legal.FEDERAL_FACTS[0]
        record = {
            "document_number": spec.document_number,
            "type": "Rule",
            "action": "Final Rule",
            "title": "Carrier Automated Tariffs",
            "publication_date": "2024-01-02",
            "abstract": (
                "The final rule removes the option for common carriers to charge "
                "a fee to access their tariff."
            ),
            "html_url": (
                "https://www.federalregister.gov/documents/2024/01/02/"
                "2023-27783/carrier-automated-tariffs"
            ),
        }
        html = self._page(
            "<p>The final rule removes the option for common carriers to charge "
            "a fee to access their tariff.</p>",
            title="Carrier Automated Tariffs",
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            api_path = output / "raw/federal-register/2023-27783.json"
            page_path = output / "raw/federal-register-pages/2023-27783.htm"
            api_path.parent.mkdir(parents=True)
            page_path.parent.mkdir(parents=True)
            api_path.write_bytes(json.dumps(record).encode("utf-8"))
            page_path.write_bytes(html)
            page_url = "https://www.govinfo.gov/content/pkg/FR-2024-01-02/html/2023-27783.htm"
            self._write_metadata(page_path, page_url, html)
            run_state = {"client": None, "ledger": []}
            cached_path, cached_bytes = government_legal._ensure_source(
                output,
                "raw/federal-register-pages/2023-27783.htm",
                page_url,
                run_state=run_state,
            )
            case = government_legal._fr_fact(
                spec,
                "raw/federal-register-pages/2023-27783.htm",
                api_path.read_bytes(),
                cached_bytes,
                cached_path,
            )
            evidence = case["evidence"][0]
            raw = (output / evidence["rawPath"]).read_bytes()
        self.assertEqual(evidence["rawSha256"], hashlib.sha256(raw).hexdigest())
        self.assertIn(evidence["excerpt"].encode("utf-8"), raw)
        self.assertEqual(
            evidence["url"],
            "https://www.govinfo.gov/content/pkg/FR-2024-01-02/html/2023-27783.htm",
        )
        self.assertNotIn("/api/", evidence["url"])

    def test_official_court_sheet_scopes_majority_author_to_docket_and_date(self) -> None:
        spec = CourtFactSpec(
            id="fixture-wa-opinion-author",
            filename="test-sheet",
            docket="2024-12345",
            case_title="Example v. Agency",
            filed_date="2024-09-12",
            majority_author="A. Justice",
        )
        page = (
            b"<html><body><h1>Supreme Court of the State of Washington</h1>"
            b"<p>Docket Number: 2024-12345</p>"
            b"<p>Title of Case: Example v. Agency</p>"
            b"<p>File Date: 09/12/2024</p>"
            b"<p>A. Justice | Majority Author</p></body></html>"
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "court.html"
            path.write_bytes(page)
            self._write_metadata(
                path,
                "https://www.courts.wa.gov/opinions/index.cfm?fa=opinions.showOpinion&filename=test-sheet",
                page,
            )
            case = government_legal._court_fact(
                spec, "raw/washington-supreme/test-sheet.html", page, path
            )
        self.assertEqual(
            case["temporal"], {"kind": "event", "precision": "day", "date": "2024-09-12"}
        )
        self.assertIn("2024-12345", case["query"])
        self.assertEqual(case["gold"]["answer"], "A. Justice")

    def test_rule_questions_distinguish_eligibility_and_maintained_schedule(self) -> None:
        specs = {spec.id: spec for spec in FEDERAL_FACTS}
        representative = specs["legal-fr-2024-06572-walkaround-representative"]
        self.assertIn("besides an employee of the employer", representative.prompt.casefold())
        self.assertIn("whom may employees designate", representative.prompt)
        self.assertNotIn("in addition to", representative.prompt.casefold())
        self.assertNotIn("third party", representative.prompt.casefold())
        schedule = specs["legal-fr-2024-18087-zuranolone-schedule"]
        self.assertIn("maintain", schedule.prompt)
        self.assertIn("2024 final rule", schedule.prompt)

    def test_output_directory_is_validated_before_collection_creates_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            unsafe_output = Path(temporary) / "credentials"
            with self.assertRaisesRegex(ValueError, "credential"):
                government_legal.collect(unsafe_output, count=1)
            self.assertFalse(unsafe_output.exists())

    def test_fuel_volume_threshold_is_scoped_to_the_correct_statutory_clause(self) -> None:
        spec = next(item for item in STATUTE_FACTS if item.id.endswith("fuel-volume"))
        self.assertIn("30C(c)(1)(B)(i)", spec.prompt)
        self.assertEqual(spec.support, "at least 85 percent of the volume")
        section = (
            "(i) Any fuel at least 85 percent of the volume of which consists of "
            "ethanol, natural gas, compressed natural gas, liquified natural gas, "
            "liquefied petroleum gas, or hydrogen. (ii) Any mixture that contains "
            "at least 20 percent biodiesel."
        )
        government_legal._validate_statute_fact(spec, section, "117-169")


if __name__ == "__main__":
    unittest.main()
