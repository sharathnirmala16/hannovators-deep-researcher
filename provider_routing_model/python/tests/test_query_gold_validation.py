"""Offline quality-gate tests for source evidence and direct-search queries."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from query_gold_test_helpers import make_cases

from query_gold.models import QueryGoldCase
from query_gold.validation import (
    CATEGORY_IDS,
    ValidationPolicy,
    ValidationReport,
    _currency_is_explicit,
    _gold_is_explicit,
    _report_answer_annotations,
    _units_are_explicit,
    validate_records,
)


def policy(count: int = 5) -> ValidationPolicy:
    return ValidationPolicy(
        expected_count_per_category=count,
        min_distinct_source_ids=count,
        min_question_types=3,
    )


class QueryGoldValidationTests(unittest.TestCase):
    def test_duration_unit_warning_applies_only_to_a_duration_value(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outcome = make_cases(
                root,
                count_per_category=1,
                categories=("02_biomedical_clinical_trials",),
                write_files=False,
            )[0]
            outcome.gold.answer = "Mean change from baseline at 12 months in the seizure score"
            report = ValidationReport()
            annotations = _report_answer_annotations(outcome, report)
            self.assertEqual(annotations[0], 0)
            self.assertFalse(any(issue.code == "duration_units_missing" for issue in report.issues))

            outcome.gold.answer = "12 months"
            report = ValidationReport()
            annotations = _report_answer_annotations(outcome, report)
            self.assertEqual(annotations[0], 1)
            self.assertTrue(any(issue.code == "duration_units_missing" for issue in report.issues))

    def test_source_markup_and_contextual_unit_terms_support_canonical_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row = make_cases(
                root,
                count_per_category=1,
                categories=("03_code_api_documentation",),
                write_files=False,
            )[0]

            marked_answer = row.model_copy(deep=True)
            marked_answer.gold.answer = "type, choices, and metavar"
            marked_answer.gold.value = "type, choices, and metavar"
            marked_answer.evidence[
                0
            ].excerpt = "The *type*, *choices*, and *metavar* parameters are deprecated."
            self.assertTrue(_gold_is_explicit(marked_answer))

            port_case = row.model_copy(deep=True)
            port_case.gold.answer = "8000"
            port_case.gold.value = 8000
            port_case.gold.units = "TCP port"
            port_case.evidence[0].excerpt = "@click.option('--port', default=8000)"
            self.assertTrue(_units_are_explicit(port_case))

            arity_case = row.model_copy(deep=True)
            arity_case.gold.answer = "1"
            arity_case.gold.value = "1"
            arity_case.gold.units = "option value per occurrence"
            arity_case.evidence[0].excerpt = (
                "Options accept a fixed number of arguments (defaults to 1), or may be "
                "specified multiple times."
            )
            self.assertTrue(_units_are_explicit(arity_case))

            duration_case = row.model_copy(deep=True)
            duration_case.gold.units = "years"
            duration_case.evidence[0].excerpt = "The rule must be issued not later than 1 year."
            self.assertTrue(_units_are_explicit(duration_case))

            eps_case = row.model_copy(deep=True)
            eps_case.gold.units = "USD per diluted share"
            eps_case.gold.currency = "USD"
            eps_case.evidence[
                0
            ].excerpt = "Reported Diluted EPS was $1.12 for the quarter ended June 30, 2025."
            self.assertTrue(_units_are_explicit(eps_case))
            self.assertTrue(_currency_is_explicit("USD", eps_case.evidence[0].excerpt))

            currency_only = row.model_copy(deep=True)
            currency_only.gold.units = "USD"
            currency_only.gold.currency = "USD"
            currency_only.evidence[0].excerpt = "The company reported $1.2 billion in revenue."
            self.assertTrue(_units_are_explicit(currency_only))
            currency_only.evidence[0].excerpt = "The company reported EUR 1.2 billion in revenue."
            self.assertFalse(_units_are_explicit(currency_only))

            percent_case = row.model_copy(deep=True)
            percent_case.gold.units = "%"
            percent_case.evidence[0].excerpt = "Comparable sales increased by 0.3 percent."
            self.assertTrue(_units_are_explicit(percent_case))

    def test_complete_synthetic_first_five_dataset_passes_offline_integrity_gates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = make_cases(root, count_per_category=5)
            report = validate_records(
                cases,
                category_dirs={
                    category: root / "categories" / category for category in CATEGORY_IDS
                },
                policy=policy(),
            )
            self.assertTrue(report.valid, report.to_dict())
            self.assertEqual(report.caseCount, 5 * len(CATEGORY_IDS))
            self.assertEqual(report.categoryCounts, {category: 5 for category in CATEGORY_IDS})
            self.assertEqual(report.quality["publicAnswerPageCoverage"], 1.0)
            self.assertEqual(report.quality["publicPageCompleteGoldSupportCoverage"], 1.0)
            self.assertEqual(
                report.sourceConcentration[CATEGORY_IDS[0]]["distinctSourceRecordIds"], 5
            )

    def test_raw_sha_and_literal_excerpt_are_both_verified_against_cached_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = make_cases(root, count_per_category=5)
            first = cases[0]
            evidence_path = root / "categories" / first.categoryId / first.evidence[0].rawPath
            evidence_path.write_text("changed source bytes", encoding="utf-8")

            report = validate_records(
                cases,
                category_dirs={
                    category: root / "categories" / category for category in CATEGORY_IDS
                },
                policy=policy(),
            )
            error_codes = {issue.code for issue in report.errors}
            self.assertIn("evidence_sha256_mismatch", error_codes)
            self.assertIn("evidence_excerpt_not_literal", error_codes)

    def test_api_only_source_and_nonliteral_gold_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = make_cases(root, count_per_category=5)
            bad_page = cases[0].model_copy(deep=True)
            bad_page.evidence[0].url = "https://api.example.org/v1/record.json"
            bad_answer = cases[1].model_copy(deep=True)
            bad_answer.gold.answer = "Gold phrase not found in source"
            changed = [
                bad_page
                if case.id == cases[0].id
                else bad_answer
                if case.id == cases[1].id
                else case
                for case in cases
            ]

            report = validate_records(
                changed,
                category_dirs={
                    category: root / "categories" / category for category in CATEGORY_IDS
                },
                policy=policy(),
            )
            codes = {issue.code for issue in report.errors}
            self.assertIn("public_answer_page_missing", codes)
            self.assertIn("gold_not_explicit_in_evidence", codes)

    def test_context_dependent_derived_compound_and_unbounded_time_queries_are_red_flags(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = make_cases(root, count_per_category=5)
            bad_rows = [case.model_dump(mode="python", exclude_none=True) for case in cases]
            bad_rows[0]["query"] = (
                "Using the above document, calculate the company's revenue and net income."
            )
            bad_rows[1]["query"] = "What is the latest value for Acme001 Corp revenue?"
            bad_cases = [QueryGoldCase.model_validate(row, strict=True) for row in bad_rows]

            report = validate_records(
                bad_cases,
                category_dirs={
                    category: root / "categories" / category for category in CATEGORY_IDS
                },
                policy=policy(),
            )
            codes = {issue.code for issue in report.errors}
            self.assertIn("query_context_dependent", codes)
            self.assertIn("query_derived_or_multi_hop", codes)
            self.assertIn("query_compound", codes)
            self.assertIn("temporal_scope_not_obvious_in_query", codes)
            self.assertIn("query_uses_unbounded_current_time", codes)

    def test_normalized_query_dedup_and_source_concentration_are_gated(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = make_cases(
                root,
                count_per_category=5,
                categories=(CATEGORY_IDS[0],),
            )
            duplicate = cases[1].model_copy(deep=True)
            duplicate.id = "duplicate-query-case"
            duplicate.query = f"  {cases[0].query.upper()}  "
            concentrated = cases[2:]
            for case in concentrated:
                case.evidence[0].sourceRecordId = "one-repeated-record"
            test_cases = [cases[0], duplicate, *concentrated]
            test_policy = ValidationPolicy(
                categories=(CATEGORY_IDS[0],),
                expected_count_per_category=5,
                min_distinct_source_ids=4,
                min_question_types=3,
            )
            report = validate_records(test_cases, policy=test_policy)
            codes = {issue.code for issue in report.errors}
            self.assertIn("duplicate_normalized_query", codes)
            self.assertIn("source_record_diversity_below_minimum", codes)

    def test_lexically_credential_path_is_rejected_before_stat_or_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases = make_cases(root, count_per_category=5, categories=(CATEGORY_IDS[0],))
            unsafe_evidence = cases[0].evidence[0].model_copy(update={"rawPath": ".env"})
            unsafe_case = cases[0].model_copy(update={"evidence": [unsafe_evidence]})
            test_policy = ValidationPolicy(
                categories=(CATEGORY_IDS[0],),
                expected_count_per_category=None,
                min_distinct_source_ids=0,
                min_question_types=0,
                require_all_categories=False,
            )
            with (
                patch.object(Path, "lstat") as lstat,
                patch.object(Path, "read_bytes") as read_bytes,
            ):
                report = validate_records(
                    [unsafe_case],
                    category_dirs={CATEGORY_IDS[0]: root / "categories" / CATEGORY_IDS[0]},
                    policy=test_policy,
                )
            self.assertIn("evidence_path_unsafe", {issue.code for issue in report.errors})
            lstat.assert_not_called()
            read_bytes.assert_not_called()


if __name__ == "__main__":
    unittest.main()
