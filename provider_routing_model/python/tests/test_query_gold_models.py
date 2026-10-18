"""Strict schema and precision tests for query/gold records."""

from __future__ import annotations

import copy
import math
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError
from query_gold_test_helpers import make_case

from query_gold.models import Evidence, QueryGoldCase, TemporalScope


class QueryGoldModelTests(unittest.TestCase):
    def make_row(self, folder: Path) -> dict[str, object]:
        return make_case("01_earnings_corporate_finance", 1, folder)

    def test_strict_schema_forbids_unknown_fields_and_requires_question_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            row = self.make_row(Path(temporary))
            QueryGoldCase.model_validate(row, strict=True)
            with self.assertRaises(ValidationError):
                QueryGoldCase.model_validate({**row, "answer": "leaked"}, strict=True)

            missing_subtype = copy.deepcopy(row)
            del missing_subtype["derivation"]["questionType"]  # type: ignore[index]
            with self.assertRaises(ValidationError):
                QueryGoldCase.model_validate(missing_subtype, strict=True)

    def test_mutable_scopes_require_kind_fields_with_matching_iso_precision(self):
        with self.assertRaises(ValidationError):
            TemporalScope.model_validate({"kind": "as_of", "precision": "year"}, strict=True)
        with self.assertRaises(ValidationError):
            TemporalScope.model_validate(
                {"kind": "as_of", "precision": "year", "asOf": "2025-01-01"},
                strict=True,
            )
        with self.assertRaises(ValidationError):
            TemporalScope.model_validate(
                {
                    "kind": "period",
                    "precision": "month",
                    "periodStart": "2025-03",
                    "periodEnd": "2025-02",
                },
                strict=True,
            )

        month = TemporalScope.model_validate(
            {"kind": "as_of", "precision": "month", "asOf": "2025-06"}, strict=True
        )
        self.assertEqual(month.asOf, "2025-06")
        immutable = TemporalScope.model_validate(
            {"kind": "immutable", "precision": "immutable", "immutableReason": "definition"},
            strict=True,
        )
        self.assertEqual(immutable.immutableReason, "definition")

    def test_source_dates_keep_partial_year_and_month_precision(self):
        with tempfile.TemporaryDirectory() as temporary:
            row = self.make_row(Path(temporary))
            evidence = row["evidence"][0]  # type: ignore[index]
            evidence["publishedAt"] = "2025"  # type: ignore[index]
            evidence["effectiveDate"] = "2025-06"  # type: ignore[index]
            case = QueryGoldCase.model_validate(row, strict=True)
            self.assertEqual(case.evidence[0].publishedAt, "2025")
            self.assertEqual(case.evidence[0].effectiveDate, "2025-06")

            evidence["publishedAt"] = "2025-06-01T00:00:00"  # type: ignore[index]
            with self.assertRaises(ValidationError):
                QueryGoldCase.model_validate(row, strict=True)

    def test_urls_and_raw_paths_reject_embedded_credentials_and_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            row = self.make_row(Path(temporary))
            evidence = row["evidence"][0]  # type: ignore[index]
            for bad_url in (
                "https://user:pass@example.org/record",
                "https://example.org/record?api_key=synthetic",
                "https://example.org/record#token=synthetic",
            ):
                evidence["url"] = bad_url  # type: ignore[index]
                with self.subTest(url=bad_url), self.assertRaises(ValidationError):
                    QueryGoldCase.model_validate(row, strict=True)

            evidence["url"] = "https://example.org/record"  # type: ignore[index]
            for bad_path in (
                "../outside.txt",
                "/absolute.txt",
                "C:/outside.txt",
                ".env",
                "raw\\secret.txt",
                "raw/file::$DATA",
                "raw/CON.txt",
                "raw/trailing.",
            ):
                evidence["rawPath"] = bad_path  # type: ignore[index]
                with self.subTest(path=bad_path), self.assertRaises(ValidationError):
                    QueryGoldCase.model_validate(row, strict=True)

    def test_evidence_excerpt_preserves_whitespace_and_value_rejects_non_finite_numbers(self):
        evidence = {
            "url": "https://example.org/record",
            "title": "source title",
            "retrievedAtUTC": "2026-10-17T12:00:00Z",
            "rawSha256": "a" * 64,
            "rawPath": "raw.txt",
            "excerpt": "  exact source excerpt  ",
        }
        parsed = Evidence.model_validate(evidence, strict=True)
        self.assertEqual(parsed.excerpt, "  exact source excerpt  ")
        for timestamp in ("2026-10-17T12:00Z", "2026-10-17T12:00+00:00"):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValidationError):
                Evidence.model_validate({**evidence, "retrievedAtUTC": timestamp}, strict=True)

        with tempfile.TemporaryDirectory() as temporary:
            row = self.make_row(Path(temporary))
            row["gold"]["value"] = {"nested": [1, math.nan]}  # type: ignore[index]
            with self.assertRaises(ValidationError):
                QueryGoldCase.model_validate(row, strict=True)


if __name__ == "__main__":
    unittest.main()
