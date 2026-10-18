"""Focused tests for finance release extraction and offline dataset validation."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYTHON_ROOT / "src"))

from query_gold.categories import finance  # noqa: E402
from query_gold.categories.finance_facts import FACTS  # noqa: E402
from query_gold.models import QueryGoldCase  # noqa: E402
from query_gold.validation import ValidationPolicy, validate_records  # noqa: E402


class FinanceExtractionTests(unittest.TestCase):
    def test_wrong_table_period_column_is_rejected(self):
        root = finance._default_output_dir()
        if not (root / "raw" / "source_manifest.json").is_file():
            self.skipTest("private finance source snapshots are not available")

        fact = next(item for item in FACTS if item.case_id == "fin-jnj-q4-2022-reported-sales")
        manifest = finance._load_source_manifest(root)
        source = next(
            item
            for item in manifest["selectedRecords"]
            if item["sourceRecordId"] == fact.source_record_id
        )
        source_text = finance._source_bytes(
            root, source, "sourceTextPath", "sourceTextSha256"
        ).decode("utf-8", errors="strict")
        excerpt = finance._extract_excerpt(source_text, fact)
        anchor_line = next(line for line in source_text.splitlines() if fact.anchor in line)

        with self.assertRaisesRegex(ValueError, "requested period column"):
            finance._validate_source_excerpt(replace(fact, column_index=1), excerpt, anchor_line)

    def test_ultra_excerpt_keeps_quarter_and_ytd_period_headers(self):
        root = finance._default_output_dir()
        if not (root / "raw" / "source_manifest.json").is_file():
            self.skipTest("private finance source snapshots are not available")

        fact = next(item for item in FACTS if item.case_id == "fin-ulta-q2fy23-net-sales")
        manifest = finance._load_source_manifest(root)
        source = next(
            item
            for item in manifest["selectedRecords"]
            if item["sourceRecordId"] == fact.source_record_id
        )
        source_text = finance._source_bytes(
            root, source, "sourceTextPath", "sourceTextSha256"
        ).decode("utf-8", errors="strict")
        excerpt = finance._extract_excerpt(source_text, fact)

        self.assertIn("13 Weeks Ended", excerpt)
        self.assertIn("26 Weeks Ended", excerpt)
        self.assertIn(fact.value_token, excerpt)


class FinanceSnapshotIntegrationTests(unittest.TestCase):
    def test_all_fifty_cases_pass_the_shared_offline_quality_gate(self):
        root = finance._default_output_dir()
        if not (root / "raw" / "source_manifest.json").is_file():
            self.skipTest("private finance source snapshots are not available")

        rows = finance.collect(root, count=50)
        cases = [QueryGoldCase.model_validate(row, strict=True) for row in rows]
        report = validate_records(
            cases,
            category_dirs={finance.CATEGORY_ID: root},
            policy=ValidationPolicy(
                categories=(finance.CATEGORY_ID,),
                expected_count_per_category=50,
                min_distinct_source_ids=25,
                min_question_types=3,
                require_all_categories=False,
            ),
        )

        self.assertTrue(report.valid, [issue.message for issue in report.errors])
        self.assertEqual(report.categoryCounts[finance.CATEGORY_ID], 50)
        self.assertEqual(
            len({case.evidence[0].sourceRecordId for case in cases}),
            25,
        )
        self.assertGreaterEqual(len({case.derivation.questionType for case in cases}), 3)
        notes = finance.sources_markdown(root, rows)
        self.assertIn("No live search engine was queried", notes)
        self.assertIn("no acquisition or PDF-to-text bootstrap", notes)


if __name__ == "__main__":
    unittest.main()
